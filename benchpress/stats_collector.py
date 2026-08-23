# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime

from benchpress.docker_manager import container_is_gone, get_container_health, get_container_stats


def collect_bench_stats() -> None:
	"""Poll Docker for every Running bench: resource usage, health, and drift.

	Health is not just a badge. `status` is what the page shows and what the
	credit sweep bills, so a container that crashed while its bench still said
	Running would burn the owner's credits for nothing. This poll is the
	reconciler: Docker is the truth, the doctype follows.
	"""
	running_benches = frappe.get_all(
		"Bench Instance",
		filters={"status": "Running", "container_id": ["is", "set"]},
		fields=["name", "container_id", "owner"],
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

		try:
			health = _update_bench_health(bench)
			_stop_if_dead(bench, health)
		except Exception:
			frappe.log_error(
				title=f"Health reconciliation failed for {bench['name']}",
				message=frappe.get_traceback(),
			)

	frappe.db.commit()


def _update_bench_health(bench: dict) -> str:
	"""Record the container health and check timestamp; returns the health label."""
	health = get_container_health(bench["container_id"])
	frappe.db.set_value(
		"Bench Instance",
		bench["name"],
		{
			"container_health": health,
			"last_health_check": now_datetime(),
		},
		update_modified=False,
	)
	return health


def _stop_if_dead(bench: dict, health: str) -> None:
	"""Route a bench whose container died through the one stop path.

	Unhealthy is a container Docker can see and reports as not running — a
	crash, an OOM kill, a `docker stop` behind our back. Unknown is acted on
	only when the container is positively gone: an inspect error must never
	stop anyone's bench.
	"""
	if health == "Healthy":
		return
	if health == "Unknown" and not container_is_gone(bench["container_id"]):
		return

	from benchpress.deploy_manager import stop_bench
	from benchpress.notifications import notify_owner

	stop_bench(bench["name"])
	notify_owner(
		bench["owner"],
		_("Bench {0} was stopped: its container is no longer running.").format(bench["name"]),
		"Bench Instance",
		bench["name"],
	)
