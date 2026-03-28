# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

from benchpress.docker_manager import get_container_stats


def collect_all_stats() -> None:
	"""Poll Docker stats and WireGuard transfer stats."""
	_collect_bench_stats()
	_collect_device_stats()


def _collect_bench_stats() -> None:
	"""Poll Docker stats for all running benches and update their resource usage fields."""
	running_benches = frappe.get_all(
		"Bench Instance",
		filters={"status": "Running", "container_id": ["is", "set"]},
		fields=["name", "container_id"],
	)

	for bench in running_benches:
		try:
			stats = get_container_stats(bench["container_id"])
			frappe.db.set_value(
				"Bench Instance",
				bench["name"],
				{
					"cpu_usage": stats["cpu_percent"],
					"memory_usage": stats["memory_percent"],
				},
				update_modified=False,
			)
		except Exception:
			frappe.log_error(
				title=f"Stats collection failed for {bench['name']}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()


def _collect_device_stats() -> None:
	"""Poll WireGuard transfer stats and update Bench Device records."""
	from benchpress.wg_manager import get_peer_transfer_stats

	try:
		stats = get_peer_transfer_stats()
	except Exception:
		return

	if not stats:
		return

	devices = frappe.get_all(
		"Bench Device",
		filters={"status": "Active", "wg_public_key": ["is", "set"]},
		fields=["name", "wg_public_key"],
	)

	for device in devices:
		peer_stats = stats.get(device["wg_public_key"])
		if peer_stats:
			frappe.db.set_value(
				"Bench Device",
				device["name"],
				{
					"wg_rx_bytes": peer_stats["rx_bytes"],
					"wg_tx_bytes": peer_stats["tx_bytes"],
				},
				update_modified=False,
			)

	frappe.db.commit()
