# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The single integration seam between Benchpress and the vpn_management app.

Benchpress generates the container keypair locally and registers only the
public key as a VPN Peer — the insert claims the tunnel IP atomically from the
server's pool. The interface is converged synchronously because deploys run on
queue-long, which mounts the wg-agent socket. The container's private key is
written into the container and never persisted anywhere.

User devices are VPN Peers too: the device functions below keep the legacy
device API contract (field names, reply shapes) so Devices.vue ships
unchanged, and let the peer's own hooks drive allocation and reconciliation.
"""

import ipaddress
import re

import frappe
from frappe import _
from frappe.utils.data import cint, now_datetime, time_diff_in_seconds

DEFAULT_INTERFACE = "wg0"
CONTAINER_KEEPALIVE_SECONDS = 25
# Fallback when VPN Settings has never been saved; matches its own default.
DEFAULT_STATUS_POLL_MINUTES = 5
DEVICE_TYPES = ["Mobile", "Laptop", "Desktop", "Tablet", "Server", "IoT", "Embedded"]
DEVICE_PEER_PATTERN = re.compile(r"^\[(?P<device_type>[A-Za-z]+)\] (?P<device_name>.+)$")
# Mirrors vpn_management.api.peers.get_peer_status, which builds the same set
# inline. test_device_wrappers asserts the two still agree.
PEER_STATUS_FIELDS = (
	"name",
	"status",
	"assigned_ip",
	"endpoint",
	"last_handshake",
	"rx_bytes",
	"tx_bytes",
)


def create_container_peer(bench) -> dict:
	"""Claim a tunnel IP for a bench container by registering a VPN Peer."""
	from vpn_management import crypto, tasks

	private_key, public_key = crypto.generate_keypair()
	peer = frappe.get_doc(
		{
			"doctype": "VPN Peer",
			"peer_name": bench.bench_name or bench.name,
			"owner_user": bench.owner,
			"server": DEFAULT_INTERFACE,
			"public_key": public_key,
		}
	)
	peer.insert(ignore_permissions=True)  # deploy job acts as the system, not the bench owner
	bench.vpn_peer = peer.name
	tasks.reconcile_interface(DEFAULT_INTERFACE)
	return {
		"peer": peer.name,
		"assigned_ip": peer.assigned_ip,
		"private_key": private_key,
		"public_key": public_key,
	}


def remove_bench_peer(bench) -> None:
	"""Delete the bench's linked VPN Peer so its IP allocation is freed.

	The peer's own on_trash releases the allocation and enqueues a deduped
	reconcile on queue-long — the only worker that mounts both the agent
	socket and the wireguard conf volume — so this is safe to call from web
	requests too. No-ops cleanly when no peer is linked, and clears a
	dangling link if the peer is already gone.
	"""
	if not bench.vpn_peer:
		return
	if frappe.db.exists("VPN Peer", bench.vpn_peer):
		frappe.delete_doc("VPN Peer", bench.vpn_peer, ignore_permissions=True)
	bench.vpn_peer = None


def configure_container(container_id: str, private_key: str, assigned_ip: str) -> None:
	"""Write the client conf into the container and bring its tunnel up."""
	from benchpress.docker_manager import exec_in_container, write_file_to_container

	config = render_container_config(private_key, assigned_ip)
	write_file_to_container(container_id, config, "/etc/wireguard/wg0.conf")
	exec_in_container(container_id, "chmod 600 /etc/wireguard/wg0.conf", user="root")
	exit_code, output = exec_in_container(container_id, "wg-quick up wg0", user="root")
	if exit_code != 0:
		raise Exception(f"wg-quick up failed inside container: {output}")


def render_container_config(private_key: str, assigned_ip: str) -> str:
	"""Client conf for a bench container: it reaches wg0 via the Docker gateway."""
	server = frappe.get_cached_doc("WireGuard Server", DEFAULT_INTERFACE)
	pool_network = ipaddress.ip_network(server.address_cidr, strict=False)
	return (
		"[Interface]\n"
		f"PrivateKey = {private_key}\n"
		f"Address = {assigned_ip}/32\n"
		"\n"
		"[Peer]\n"
		f"PublicKey = {server.server_public_key}\n"
		f"AllowedIPs = {pool_network}\n"
		f"Endpoint = {_get_docker_gateway()}:{server.listen_port}\n"
		f"PersistentKeepalive = {CONTAINER_KEEPALIVE_SECONDS}\n"
	)


def _get_docker_gateway() -> str:
	"""The host's gateway IP on the benchpress Docker network."""
	from benchpress.docker_manager import get_client

	client = get_client()
	try:
		network = client.networks.get("benchpress")
		ipam = network.attrs.get("IPAM", {})
		configs = ipam.get("Config", [])
		if configs and "Gateway" in configs[0]:
			return configs[0]["Gateway"]
	except Exception:
		pass  # best-effort
	return "172.30.0.1"


def register_device(device_name: str, device_type: str, public_key: str | None = None) -> dict:
	"""Register a personal device as a VPN Peer, keeping the legacy device reply shape."""
	if device_type not in DEVICE_TYPES:
		frappe.throw(_("Invalid device type: {0}").format(device_type))
	peer = frappe.get_doc(
		{
			"doctype": "VPN Peer",
			"peer_name": f"[{device_type}] {device_name}",
			"owner_user": frappe.session.user,
			"server": DEFAULT_INTERFACE,
			"public_key": public_key,  # blank → vpn_management generates the keypair server-side
			"client_allowed_ips": _device_allowed_ips(),
		}
	)
	peer.insert(ignore_permissions=True)  # users hold no VPN roles; ownership lives in owner_user
	return {"name": peer.name, "wg_ip": peer.assigned_ip, "wg_config": _render_device_config(peer)}


def unregister_device(device_docname: str) -> bool:
	"""Delete an owned device peer; its on_trash frees the IP and reconciles."""
	peer = _owned_device_peer(device_docname)
	frappe.delete_doc("VPN Peer", peer.name, ignore_permissions=True)
	return True


def list_devices() -> list[dict]:
	"""The session user's device peers, mapped to the legacy device field names."""
	peers = frappe.get_all(
		"VPN Peer",
		filters=_device_peer_filters(),
		fields=[
			"name",
			"peer_name",
			"status",
			"assigned_ip",
			"public_key",
			"rx_bytes",
			"tx_bytes",
			"last_handshake",
			"creation",
		],
		order_by="creation desc",
		limit=100,
	)
	return [_as_device_row(peer) for peer in peers]


def count_devices() -> int:
	"""How many device peers the session user holds — one count, not a fetch-and-len.

	Lives here so the device cap and the device list agree on what a device *is*: the filters
	exclude bench container peers, and that definition should exist once.
	"""
	return frappe.db.count("VPN Peer", _device_peer_filters())


def get_device_peer_status(device_docname: str) -> dict:
	"""Live tunnel status for an owned device peer.

	The reply is `vpn_management.api.peers.get_peer_status`' own shape, but not
	its guard: that endpoint gates on the VPN DocPerms, which only
	`System Manager`, `VPN Admin` and `BenchPress Admin` hold, so a
	`BenchPress User` cannot call it for their own peer. Devices are authorized
	by `owner_user` here, the same rule every other device wrapper uses.
	"""
	peer = _owned_device_peer(device_docname)
	return {field: peer.get(field) for field in PEER_STATUS_FIELDS}


def get_device_vpn_status() -> dict:
	"""Whether the session user has a device peer with a fresh handshake.

	"Fresh" is one status poll old: `VPN Settings.status_poll_interval_min`,
	the same interval vpn_management writes handshakes on. Inventing a second
	threshold here would make the UI disagree with the poller.
	"""
	peers = frappe.get_all(
		"VPN Peer",
		filters=_device_peer_filters(),
		fields=["name", "status", "last_handshake"],
		order_by="last_handshake desc",
		limit=100,
	)
	last_handshake = peers[0].last_handshake if peers else None
	stale_after_seconds = handshake_stale_seconds()
	return {
		"connected": is_handshake_fresh(last_handshake, stale_after_seconds),
		"last_handshake": last_handshake,
		"peer_count": len(peers),
		"stale_after_seconds": stale_after_seconds,
	}


def is_handshake_fresh(last_handshake, stale_after_seconds: int) -> bool:
	"""The one definition of a live tunnel — never re-decided anywhere else."""
	if not last_handshake:
		return False
	return time_diff_in_seconds(now_datetime(), last_handshake) <= stale_after_seconds


def handshake_stale_seconds() -> int:
	minutes = cint(frappe.db.get_single_value("VPN Settings", "status_poll_interval_min"))
	return (minutes or DEFAULT_STATUS_POLL_MINUTES) * 60


def get_device_config(device_docname: str) -> str:
	"""Render the client conf for an owned device peer."""
	return _render_device_config(_owned_device_peer(device_docname))


def _device_peer_filters() -> dict:
	"""Everything the user owns except the peers that belong to bench containers.

	The bench sweep is one unbounded `get_all` per call. Left as it is: the
	whole fleet is 4 Bench Instances, so it reads one short indexed column.
	Batch or cache it when the fleet reaches the hundreds.
	"""
	filters = {"owner_user": frappe.session.user}
	bench_peers = frappe.get_all("Bench Instance", filters={"vpn_peer": ("is", "set")}, pluck="vpn_peer")
	if bench_peers:
		filters["name"] = ("not in", bench_peers)
	return filters


def _as_device_row(peer) -> dict:
	device_type, device_name = _split_device_peer_name(peer.peer_name)
	return {
		"name": peer.name,
		"device_name": device_name,
		"device_type": device_type,
		"status": peer.status,
		"wg_ip": peer.assigned_ip,
		"wg_public_key": peer.public_key,
		"wg_rx_bytes": peer.rx_bytes,
		"wg_tx_bytes": peer.tx_bytes,
		"last_handshake": peer.last_handshake,
		"registered_on": peer.creation,
	}


def _split_device_peer_name(peer_name: str) -> tuple[str, str]:
	# register_device encodes the type as a "[Laptop] " prefix — VPN Peer has no such field.
	match = DEVICE_PEER_PATTERN.match(peer_name or "")
	if match and match["device_type"] in DEVICE_TYPES:
		return match["device_type"], match["device_name"]
	return "Device", peer_name


def _device_allowed_ips() -> str:
	# Route only the VPN pool through the device's tunnel (the old device contract),
	# not the VPN Peer full-tunnel default of 0.0.0.0/0.
	server = frappe.get_cached_doc("WireGuard Server", DEFAULT_INTERFACE)
	return str(ipaddress.ip_network(server.address_cidr, strict=False))


def _owned_device_peer(device_docname: str):
	from benchpress.permissions import is_admin

	peer = frappe.get_doc("VPN Peer", device_docname)
	if peer.owner_user != frappe.session.user and not is_admin():
		frappe.throw(_("You do not have permission to access this device."), frappe.PermissionError)
	return peer


def _render_device_config(peer) -> str:
	from vpn_management.api.client_config import _render_client_config

	return _render_client_config(peer)
