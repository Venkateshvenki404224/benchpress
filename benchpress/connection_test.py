# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The connection test behind "A site will not open?" on the Devices screen.

`run_diagnostics` is admin-only and probes shared infrastructure — Docker,
MariaDB, Redis. A `BenchPress User` still has to be able to answer why nothing
resolves, so this covers only what is theirs: the WireGuard server their tunnel
terminates on, whether this account has a device at all, and that device's own
live peer state. No admin-only check can reach the result, because none is run.

Rows come back in the display shape the Overview infrastructure card already
renders, so one component draws both. Like `run_diagnostics`, nothing here
throws: a failure is a fail row with a hint, never an exception.
"""

import frappe
from frappe.utils.data import get_datetime, now_datetime, time_diff_in_seconds

from benchpress.diagnostics import check_row, check_vpn_server, display_row
from benchpress.vpn_adapter import (
	get_device_peer_status,
	handshake_stale_seconds,
	is_handshake_fresh,
	list_devices,
)

CHECK_LABELS = {
	"vpn_server": "WireGuard server",
	"device_registered": "Device registered",
	"peer_active": "Peer enabled on the server",
	"handshake": "Recent handshake",
}

# What each non-Active peer status means for the person reading it.
PEER_STATUS_HINTS = {
	"Pending": "{device} has never connected. Import its config into WireGuard and turn the tunnel on.",
	"Stale": "{device} has stopped talking to the server. Turn its tunnel on again.",
	"Disabled": "{device} is disabled on the server. An administrator has to re-enable it.",
	"Revoked": "{device} was revoked. Register the machine again to get a fresh config.",
}


def run_connection_test() -> list[dict]:
	"""Ordered checks, each with a pass or fail and a hint. Never raises."""
	devices = list_devices()
	device = _device_under_test(devices)
	checks = [
		check_vpn_server(),
		_registration_check(devices),
		_peer_check(device),
		_handshake_check(device),
	]
	return [display_row(check, CHECK_LABELS[check["check"]]) for check in checks]


def _device_under_test(devices: list[dict]) -> dict | None:
	"""The device with the newest handshake — the machine the user is on.

	Falls back to the most recently registered one so a never-connected device
	still gets named in the hints instead of the test going quiet.
	"""
	shaken = [device for device in devices if device["last_handshake"]]
	if shaken:
		return max(shaken, key=lambda device: get_datetime(device["last_handshake"]))
	return devices[0] if devices else None


def _registration_check(devices: list[dict]) -> dict:
	if not devices:
		return check_row(
			"device_registered",
			False,
			"This account has no device. Add this machine to get a WireGuard config.",
		)
	return check_row("device_registered", True, f"{_device_count(devices)} registered.")


def _device_count(devices: list[dict]) -> str:
	return f"{len(devices)} machine" if len(devices) == 1 else f"{len(devices)} machines"


def _peer_check(device: dict | None) -> dict:
	if not device:
		return check_row("peer_active", False, "No device to test — register this machine first.")
	try:
		peer = get_device_peer_status(device["name"])
	except Exception:
		frappe.log_error(title="Connection test could not read a device peer")
		return check_row("peer_active", False, f"Could not read the peer for {device['device_name']}.")
	if peer["status"] == "Active":
		return check_row("peer_active", True, _active_peer_hint(device, peer))
	hint = PEER_STATUS_HINTS.get(peer["status"], "{device} is not active on the server.")
	return check_row("peer_active", False, hint.format(device=device["device_name"]))


def _active_peer_hint(device: dict, peer: dict) -> str:
	endpoint = peer["endpoint"] or "no endpoint seen yet"
	return f"{device['device_name']} holds {peer['assigned_ip']} from {endpoint}."


def _handshake_check(device: dict | None) -> dict:
	if not device:
		return check_row("handshake", False, "No handshake to check — this account has no device.")
	stale_after = handshake_stale_seconds()
	if not device["last_handshake"]:
		return check_row(
			"handshake",
			False,
			f"The server has never heard from {device['device_name']}. "
			"Turn the tunnel on in your WireGuard client.",
		)
	age = int(time_diff_in_seconds(now_datetime(), device["last_handshake"]))
	if is_handshake_fresh(device["last_handshake"], stale_after):
		return check_row("handshake", True, f"Last handshake {age}s ago.")
	return check_row(
		"handshake",
		False,
		f"Last handshake was {age // 60}m ago, past the {stale_after // 60}m window. "
		"Turn the tunnel on again — WireGuard rekeys about every two minutes.",
	)
