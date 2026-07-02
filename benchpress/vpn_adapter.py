# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The single integration seam between Benchpress and the vpn_management app.

Benchpress generates the container keypair locally and registers only the
public key as a VPN Peer — the insert claims the tunnel IP atomically from the
server's pool. The interface is converged synchronously because deploys run on
queue-long, which mounts the wg-agent socket. The container's private key is
written into the container and never persisted anywhere.
"""

import ipaddress

import frappe

DEFAULT_INTERFACE = "wg0"
CONTAINER_KEEPALIVE_SECONDS = 25


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
