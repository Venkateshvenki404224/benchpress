# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import subprocess

import frappe
from frappe import _


def generate_keypair() -> dict:
	private = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True).stdout.strip()
	public = subprocess.run(
		["wg", "pubkey"], input=private, capture_output=True, text=True, check=True
	).stdout.strip()
	return {"private_key": private, "public_key": public}


def allocate_ip() -> str:
	"""Reads and increments the next_wg_ip counter in BenchPress Settings."""
	settings = frappe.get_doc("BenchPress Settings")
	ip = f"10.10.0.{settings.next_wg_ip}"
	settings.next_wg_ip = settings.next_wg_ip + 1
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
Address = {peer_ip}/24
DNS = 1.1.1.1

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}:{server_port}
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
"""


def add_peer_to_server(public_key: str, allowed_ip: str) -> None:
	subprocess.run(
		["sudo", "wg", "set", "wg0", "peer", public_key, "allowed-ips", f"{allowed_ip}/32"],
		check=True,
		capture_output=True,
	)


def remove_peer_from_server(public_key: str) -> None:
	subprocess.run(
		["sudo", "wg", "set", "wg0", "peer", public_key, "remove"],
		check=True,
		capture_output=True,
	)
