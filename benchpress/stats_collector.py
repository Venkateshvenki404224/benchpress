# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

from benchpress.docker_manager import get_container_stats


def collect_all_stats() -> None:
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
