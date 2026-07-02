# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime

from benchpress.docker_manager import get_container_health, get_container_stats


def collect_bench_stats() -> None:
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

		_update_bench_health(bench)

	frappe.db.commit()


def _update_bench_health(bench: dict) -> None:
	"""Record the container health and check timestamp for a single bench."""
	frappe.db.set_value(
		"Bench Instance",
		bench["name"],
		{
			"container_health": get_container_health(bench["container_id"]),
			"last_health_check": now_datetime(),
		},
		update_modified=False,
	)
