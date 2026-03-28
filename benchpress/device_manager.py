# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from benchpress.permissions import is_admin

DEVICE_TYPES = ["Mobile", "Laptop", "Desktop", "Tablet", "Server", "IoT", "Embedded"]


def register_device(device_name: str, device_type: str, public_key: str | None = None) -> dict:
	if device_type not in DEVICE_TYPES:
		frappe.throw(_("Invalid device type: {0}").format(device_type))

	from benchpress.wg_manager import (
		add_peer_to_server,
		allocate_ip,
		generate_keypair,
		generate_peer_config,
		sync_wg_config,
	)

	settings = frappe.get_cached_doc("BenchPress Settings")
	if not settings.wg_server_public_key or not settings.wg_server_endpoint:
		frappe.throw(_("WireGuard is not configured on this server."))

	private_key = None
	if not public_key:
		keypair = generate_keypair()
		private_key = keypair["private_key"]
		public_key = keypair["public_key"]

	wg_ip = allocate_ip()
	add_peer_to_server(public_key, wg_ip)

	wg_config = generate_peer_config(
		private_key=private_key or "{private_key}",
		peer_ip=wg_ip,
		server_public_key=settings.wg_server_public_key,
		server_endpoint=settings.wg_server_endpoint,
		server_port=settings.wg_server_port or 51820,
	)

	sync_wg_config()

	doc = frappe.get_doc(
		{
			"doctype": "Bench Device",
			"device_name": device_name,
			"device_type": device_type,
			"status": "Active",
			"wg_ip": wg_ip,
			"wg_public_key": public_key,
			"wg_config": wg_config,
		}
	)
	if private_key:
		doc.wg_private_key = private_key

	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"name": doc.name, "wg_ip": wg_ip, "wg_config": wg_config}


def unregister_device(device_name: str) -> bool:
	doc = frappe.get_doc("Bench Device", device_name)

	if doc.owner != frappe.session.user and not is_admin():
		frappe.throw(_("You do not have permission to remove this device."), frappe.PermissionError)

	if doc.wg_public_key:
		from benchpress.wg_manager import remove_peer_from_server, sync_wg_config

		try:
			remove_peer_from_server(doc.wg_public_key)
			sync_wg_config()
		except Exception:
			frappe.log_error(
				title=f"Device WG peer removal failed: {device_name}",
				message=frappe.get_traceback(),
			)

	frappe.delete_doc("Bench Device", device_name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


def list_devices() -> list[dict]:
	return frappe.get_all(
		"Bench Device",
		filters={"owner": frappe.session.user},
		fields=["name", "device_name", "device_type", "status", "wg_ip", "wg_public_key"],
		order_by="creation desc",
		limit_page_length=100,
	)


def get_device_config(device_name: str) -> str:
	doc = frappe.get_doc("Bench Device", device_name)

	if doc.owner != frappe.session.user and not is_admin():
		frappe.throw(_("You do not have permission to access this device."), frappe.PermissionError)

	if not doc.wg_config:
		frappe.throw(_("WireGuard config not yet generated for this device."))

	return doc.wg_config
