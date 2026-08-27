# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The reaper: stopped is free, but not forever.

"Stopped costs nothing" is only honest if a stopped instance eventually stops costing *us*
something too — a container, a volume and a site database sit on disk whether or not anything is
running in them. So an instance that has sat `Stopped` past `reap_after_days` is torn down, with
an email two days before so nobody loses work to a rule they had forgotten.

**The `Lab` survives.** Its apps, branches, version and size are all intact, so "reaped" means one
click to rebuild rather than lost work — which is exactly what lets us keep saying stopped is free.
Teardown is `lifecycle.torn_down`, the same path a redeploy takes; there is deliberately no
second teardown in this app.

Both queries filter on `status` and `modified`, so neither scans the table. As with the enforcement
sweep, the scheduler decides and `queue-long` acts: this worker has no Docker socket.
"""

import frappe
from frappe.utils import add_days, cint, get_datetime, now_datetime, time_diff_in_hours

from benchpress import lifecycle
from benchpress.credits import config, notify

BENCH = "Bench Instance"
REAP_FIELDS = ["name", "owner", "lab", "modified", "reap_warned_at"]

WARNING_LEAD_DAYS = 2
REAP_TIMEOUT = 900


def reap_stopped_instances() -> dict:
	"""Tear down what has sat stopped too long, and email whoever is two days from that."""
	if not config.credits_enabled():
		return _nothing_to_do()
	days = cint(config.settings().reap_after_days)
	if not days:
		return _nothing_to_do()
	return {"reaped": _reap_overdue(days), "warned": _warn_the_nearly_reaped(days)}


def reap_bench(bench_name: str) -> None:
	"""Tear one instance down on `queue-long` — the only worker that can reach Docker."""
	bench = frappe.get_doc(BENCH, bench_name)
	if bench.status != "Stopped":
		return  # started again between the decision and this job; it has earned another window
	lifecycle.torn_down(bench)
	notify.announce_reap(bench)


def _reap_overdue(days: int) -> list[str]:
	overdue = frappe.get_all(
		BENCH,
		filters={"status": "Stopped", "modified": ("<", add_days(now_datetime(), -days))},
		fields=REAP_FIELDS,
	)
	for bench in overdue:
		_enqueue_reap(bench.name)
	return [bench.name for bench in overdue]


def _warn_the_nearly_reaped(days: int) -> list[str]:
	"""One email per stopped period, sent inside the last two days of the window."""
	window = _warning_window(days)
	if not window:
		return []
	warned = []
	for bench in frappe.get_all(BENCH, filters={"status": "Stopped", "modified": window}, fields=REAP_FIELDS):
		if notify.already_warned(bench.reap_warned_at, bench.modified):
			continue
		notify.warn_reap(bench, _days_left(bench, days))
		notify.stamp_warning(bench.name, "reap_warned_at")
		warned.append(bench.name)
	return warned


def _warning_window(days: int) -> tuple | None:
	"""Stopped long enough to be near the end of the window, but not yet past it.

	A reap window shorter than the lead time has no room for a warning inside it: the teardown
	notice is the only notice there is, and inventing an earlier one would mean warning about a
	deletion before the instance had even settled.
	"""
	lead = days - WARNING_LEAD_DAYS
	if lead <= 0:
		return None
	now = now_datetime()
	return ("between", [add_days(now, -days), add_days(now, -lead)])


def _days_left(bench, days: int) -> int:
	"""Whole days until this instance is due, never fewer than one — "in 0 days" says nothing."""
	stopped_days = time_diff_in_hours(now_datetime(), get_datetime(bench.modified)) / 24.0
	return max(round(days - stopped_days), 1)


def _enqueue_reap(bench_name: str) -> None:
	frappe.enqueue(
		"benchpress.credits.reaper.reap_bench",
		bench_name=bench_name,
		queue="long",
		timeout=REAP_TIMEOUT,
		job_id=f"reap_bench:{bench_name}",
		deduplicate=True,
	)


def _nothing_to_do() -> dict:
	return {"reaped": [], "warned": []}
