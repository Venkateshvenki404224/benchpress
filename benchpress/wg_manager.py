# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import subprocess

import frappe
from frappe import _

WG_INTERFACE = "wg0"


def generate_keypair() -> dict:
	private = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True).stdout.strip()
	public = subprocess.run(
		["wg", "pubkey"], input=private, capture_output=True, text=True, check=True
	).stdout.strip()
	return {"private_key": private, "public_key": public}


def allocate_ip() -> str:
	settings = frappe.get_doc("BenchPress Settings", for_update=True)
	next_ip = settings.next_wg_ip or 2
	if next_ip > 254:
		frappe.throw(_("WireGuard IP pool exhausted (max 254 peers)"))
	ip = f"10.10.0.{next_ip}"
	settings.next_wg_ip = next_ip + 1
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return ip


def generate_peer_config(
	private_key: str,
	peer_ip: str,
	server_public_key: str,
	server_endpoint: str,
	server_port: int,
) -> str:
	return f"""[Interface]
PrivateKey = {private_key}
Address = {peer_ip}/32

[Peer]
PublicKey = {server_public_key}
AllowedIPs = 10.10.0.0/24
Endpoint = {server_endpoint}:{server_port}
PersistentKeepalive = 30
"""


def add_peer_to_server(public_key: str, allowed_ip: str) -> None:
	subprocess.run(
		["sudo", "wg", "set", WG_INTERFACE, "peer", public_key, "allowed-ips", f"{allowed_ip}/32"],
		check=True,
		capture_output=True,
	)


def remove_peer_from_server(public_key: str) -> None:
	subprocess.run(
		["sudo", "wg", "set", WG_INTERFACE, "peer", public_key, "remove"],
		check=True,
		capture_output=True,
	)


# --- Host WireGuard Server Management ---


@frappe.whitelist()
def setup_wg_server() -> dict:
	settings = frappe.get_doc("BenchPress Settings")

	if not settings.wg_server_private_key:
		keys = generate_keypair()
		settings.wg_server_private_key = keys["private_key"]
		settings.wg_server_public_key = keys["public_key"]
	else:
		public = subprocess.run(
			["wg", "pubkey"],
			input=settings.get_password("wg_server_private_key"),
			capture_output=True,
			text=True,
			check=True,
		).stdout.strip()
		settings.wg_server_public_key = public

	private_key = settings.get_password("wg_server_private_key")
	port = settings.wg_server_port or 51820
	server_ip = settings.wg_server_ip or "10.10.0.1"

	config = (
		f"[Interface]\n"
		f"Address = {server_ip}/24\n"
		f"ListenPort = {port}\n"
		f"PrivateKey = {private_key}\n"
		f"PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; "
		f"iptables -t nat -A POSTROUTING -s 10.10.0.0/24 -j MASQUERADE\n"
		f"PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; "
		f"iptables -t nat -D POSTROUTING -s 10.10.0.0/24 -j MASQUERADE\n"
	)

	subprocess.run(
		["sudo", "tee", "/etc/wireguard/wg0.conf"],
		input=config,
		capture_output=True,
		text=True,
		check=True,
	)
	subprocess.run(["sudo", "chmod", "600", "/etc/wireguard/wg0.conf"], check=True, capture_output=True)
	subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], check=True, capture_output=True)
	subprocess.run(["sudo", "wg-quick", "up", WG_INTERFACE], check=True, capture_output=True)

	settings.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- must persist keys before running wg-quick on host

	return {"public_key": settings.wg_server_public_key, "status": "active"}


def ensure_wg_running() -> bool:
	result = subprocess.run(["sudo", "wg", "show", WG_INTERFACE], capture_output=True)
	if result.returncode != 0:
		subprocess.run(["sudo", "wg-quick", "up", WG_INTERFACE], check=True, capture_output=True)
	return True


def sync_wg_config() -> None:
	subprocess.run(["sudo", "bash", "-c", f"wg-quick save {WG_INTERFACE}"], capture_output=True)


# --- Inside-Container VPN Setup ---


def _get_container_ip(container_id: str) -> str:
	from benchpress.docker_manager import get_client

	client = get_client()
	container = client.containers.get(container_id)
	networks = container.attrs["NetworkSettings"]["Networks"]
	if "benchpress" in networks:
		return networks["benchpress"]["IPAddress"]
	return container.attrs["NetworkSettings"]["IPAddress"]


def _get_docker_gateway() -> str:
	"""Get the host's gateway IP on the benchpress Docker network."""
	from benchpress.docker_manager import get_client

	client = get_client()
	try:
		network = client.networks.get("benchpress")
		ipam = network.attrs.get("IPAM", {})
		configs = ipam.get("Config", [])
		if configs and "Gateway" in configs[0]:
			return configs[0]["Gateway"]
	except Exception:
		pass
	return "172.30.0.1"


def setup_container_vpn(
	container_id: str,
	private_key: str,
	peer_ip: str,
	server_public_key: str,
	server_port: int,
) -> None:
	"""Write WireGuard config into the container and bring up wg0 inside it."""
	from benchpress.docker_manager import exec_in_container, write_file_to_container

	gateway = _get_docker_gateway()

	config = (
		f"[Interface]\n"
		f"PrivateKey = {private_key}\n"
		f"Address = {peer_ip}/32\n"
		f"\n"
		f"[Peer]\n"
		f"PublicKey = {server_public_key}\n"
		f"Endpoint = {gateway}:{server_port}\n"
		f"AllowedIPs = 10.10.0.0/24\n"
		f"PersistentKeepalive = 25\n"
	)

	exec_in_container(container_id, "mkdir -p /etc/wireguard", user="root")
	write_file_to_container(container_id, config, "/etc/wireguard/wg0.conf")
	exec_in_container(container_id, "chmod 600 /etc/wireguard/wg0.conf", user="root")

	exit_code, output = exec_in_container(container_id, "wg-quick up wg0", user="root")
	if exit_code != 0:
		raise Exception(f"wg-quick up failed inside container: {output}")
