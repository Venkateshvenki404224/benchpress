# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from benchpress import lifecycle
from benchpress.docker_manager import container_is_down, get_container_health, get_container_stats

DEFAULT_POLL_MAX_BENCHES = 50


def enqueue_stats_sweep() -> None:
	"""Sampling cron: hand the Docker polling to `queue-long`."""
	# The enqueuer, never `collect_bench_stats` itself — see the rule above `scheduler_events`
	# in `hooks.py`. Deduplicated: a sweep still running when the next tick fires keeps the slot.
	frappe.enqueue(
		"benchpress.stats_collector.collect_bench_stats",
		queue="long",
		job_id="bench_stats_sweep",
		deduplicate=True,
	)


def collect_bench_stats() -> None:
	"""Poll Docker for every Running bench: resource usage, health, and reconciliation.

	`status` drives billing, so a bench whose container died must be stopped,
	not just marked unhealthy.
	"""
	for bench in _benches_to_poll():
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

	frappe.db.commit()  # nosemgrep -- a background sweep has no request boundary to commit at


def _benches_to_poll() -> list[dict]:
	"""The Running benches this pass samples, least recently checked first.

	Bounded because Docker's stats endpoint samples twice a second apart: at 1.7 s a bench, an
	unbounded pass over a large fleet cannot finish inside its own minute, and a `*/1` job that
	overruns stacks up behind itself. The stalest benches go first so a bounded pass still
	reaches every one of them, just over more ticks.
	"""
	return frappe.get_all(
		"Bench Instance",
		filters={"status": "Running", "container_id": ["is", "set"]},
		fields=["name", "container_id", "owner"],
		order_by="last_health_check asc",
		limit_page_length=_poll_max_benches(),
	)


def _poll_max_benches() -> int:
	"""Benches one pass may sample; 0 removes the bound, which is what `get_all` reads it as."""
	limit = frappe.get_cached_doc("BenchPress Settings").get("stats_poll_max_benches")
	return DEFAULT_POLL_MAX_BENCHES if limit is None else cint(limit)


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
	"""Stop a bench whose container is no longer running.

	Acted on only when Docker positively reports the container down — an inspect error must
	never stop a bench, and neither must an unhealthy site: `Unhealthy` now also means the site
	stopped answering inside a container that is running perfectly well, which is a thing to
	report and route around, not a reason to stop a bench and take the tenant's work with it.
	"""
	if health == "Healthy":
		return
	if not container_is_down(bench["container_id"]):
		return

	from benchpress.notifications import notify_owner

	lifecycle.stopped(bench["name"])
	notify_owner(
		bench["owner"],
		_("Bench {0} was stopped: its container is no longer running.").format(bench["name"]),
		"Bench Instance",
		bench["name"],
	)
