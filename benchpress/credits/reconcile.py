# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The daily drift check: does each account's burn rate match what is actually running?

Transition-based metering is exact as long as every transition is observed. A worker killed
mid-session leaves `burn_since` stale, which is self-correcting — the next settle simply charges
the full elapsed span. A container that died *without* a `stop_burn` is not: its rate keeps
burning against a machine that no longer exists, and only a sweep can notice.

Two rules shape it, both learned the hard way:

- **Zero Docker calls.** Hours are `now - burn_since`, never `docker inspect`. The `*/1` stats
  cron already spends ~2s per container and blows its window past ~25 benches; this must not add
  to that, and the scheduler's own worker (`queue-short`) has no Docker socket anyway.
- **O(N), no N+1.** Two plucks and a dict — one query for the running instances, one for the labs
  they point at, one for the accounts. Never a `get_doc` per bench.
"""

import frappe
from frappe.utils import flt, now_datetime

from benchpress.credits import account, config, passes

# Floats accrue rounding; a difference smaller than this is arithmetic noise, not drift.
TOLERANCE = 0.000001

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
LAB = "Lab"


def reconcile_burn_rates() -> dict:
	"""Correct every account whose burn rate no longer matches its running instances."""
	if not config.credits_enabled():
		return {"checked": 0, "corrected": []}
	expected = expected_burn_rates()
	accounts = frappe.get_all(ACCOUNT, fields=["name", "burn_rate"])
	corrected = [row.name for row in accounts if _correct_if_drifted(row, expected)]
	clear_stale_flags()
	resume_unmetered_instances()
	return {"checked": len(accounts), "corrected": corrected}


def _correct_if_drifted(row, expected: dict) -> bool:
	want = flt(expected.get(row.name, 0.0))
	if abs(want - flt(row.burn_rate)) <= TOLERANCE:
		return False
	charged = account.correct_burn_rate(row.name, want)
	frappe.logger("benchpress").warning(
		f"Credit burn drift for {row.name}: {flt(row.burn_rate)} -> {want} credits/hour, "
		f"settled {charged} credits"
	)
	return True


def expected_burn_rates() -> dict:
	"""`{user: credits_per_hour}` summed over the instances that are actually running.

	Instances holding an `Always On Pass` contribute nothing: `metering` never starts a meter for
	them, so counting them here would invent drift and "correct" a rate into existence.
	"""
	benches = frappe.get_all(BENCH, filters={"status": "Running"}, fields=["name", "owner", "lab"])
	if not benches:
		return {}
	exempt = passes.active_pass_benches([bench.name for bench in benches])
	rates = lab_rates({bench.lab for bench in benches})
	totals: dict[str, float] = {}
	for bench in benches:
		rate = 0.0 if bench.name in exempt else flt(rates.get(bench.lab, 0.0))
		totals[bench.owner] = flt(totals.get(bench.owner, 0.0)) + rate
	return totals


def lab_rates(lab_names: set) -> dict:
	"""Each lab's rate, in one query plus the request-scoped `Instance Size` index."""
	labs = frappe.get_all(
		LAB,
		filters={"name": ("in", list(lab_names))},
		fields=["name", "instance_size", "memory_limit", "cpu_cores"],
	)
	return {lab.name: _rate_for(lab) for lab in labs}


def _rate_for(lab) -> float:
	size = config.size_for_lab(lab)
	return flt(size.credits_per_hour) if size else 0.0


def resume_unmetered_instances() -> None:
	"""Arm the burn flag on running instances that carry none — the pass-expiry repair.

	`metering` never starts a meter for a prepaid instance, so when its `Always On Pass` lapses
	nothing on the bench says it should be billed again. The *account* rate is already right by
	this point: `expected_burn_rates` counts a lapsed pass at the full lab rate and
	`correct_burn_rate` has just adopted it. Only the flags disagree, and a stop that finds no flag
	withdraws nothing — so the account would keep burning for a container that is gone.

	The same repair covers an instance that was already running when credits were switched on.
	"""
	unmetered = frappe.get_all(
		BENCH,
		filters={"status": "Running", "credit_burn_started": ("is", "not set")},
		fields=["name", "lab"],
	)
	if not unmetered:
		return
	exempt = passes.active_pass_benches([bench.name for bench in unmetered])
	billable = [bench for bench in unmetered if bench.name not in exempt]
	if not billable:
		return
	rates = lab_rates({bench.lab for bench in billable})
	for bench in billable:
		frappe.db.set_value(
			BENCH,
			bench.name,
			{"credit_burn_rate": flt(rates.get(bench.lab, 0.0)), "credit_burn_started": now_datetime()},
			update_modified=False,
		)


def clear_stale_flags() -> None:
	"""Drop the burning flag from instances that are not running.

	The rates were just re-derived from `status`, so a flag on anything else now describes a
	contribution no account is carrying — and left in place it would make the next `stop` charge
	a session that was already settled.
	"""
	stale = frappe.get_all(
		BENCH,
		filters={"credit_burn_started": ("is", "set"), "status": ("!=", "Running")},
		pluck="name",
	)
	for name in stale:
		frappe.db.set_value(
			BENCH,
			name,
			{"credit_burn_rate": 0.0, "credit_burn_started": None},
			update_modified=False,
		)
