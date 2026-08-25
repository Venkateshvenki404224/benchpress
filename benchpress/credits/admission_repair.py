# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The repair pass for admission, because a slot is denormalised twice over.

Named for admission and not for reconciliation: `credits.reconcile` was the burn-rate meter's
repair pass, `test_meter_gone` asserts that name never comes back, and this repairs a count of
rows rather than a rate.

`Bench Admission` rows are the truth, `Credit Account.active_instances` is a count of them, and
both are written by workers that can be killed between the two. A worker killed mid-deploy leaks
a slot forever, and a caller with a cap of two is then locked out until somebody notices - so
this runs on the `*/5` cron beside the balance sweep, not on the daily list.

It is pure database work: three grouped reads, no Docker call anywhere, which is why it is safe
on `queue-short` for exactly the reason `sweep.enforce_limits` is.

Three rules, in order. Expiring first and healing last is what makes a double release harmless:
the counter follows the rows, so it cannot be driven negative by a release that ran twice.
"""

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count
from frappe.utils import add_to_date, cint, now_datetime

from benchpress.credits import admission

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"

HOLDING_STATUSES = ("Deploying", "Running")

# `DEPLOY_JOB_TIMEOUT` is 7200 seconds, and this is that plus a margin. A claim older than this
# whose bench is still `Deploying` belongs to a job that no longer exists.
STALE_DEPLOY_HOURS = 3


def reconcile_admissions() -> dict:
	"""Expire stranded claims, adopt orphaned instances, then heal the counters."""
	released = _release_stranded()
	adopted = _adopt_orphans()
	healed = _heal_counters()
	if released or adopted or healed:
		frappe.logger("benchpress").warning(
			f"admission drift: released {len(released)}, adopted {len(adopted)}, healed {len(healed)}"
		)
	return {"released": released, "adopted": adopted, "healed": healed}


def _release_stranded() -> list[str]:
	"""Drop every claim whose bench is no longer deploying or running, or has stopped trying."""
	claims = frappe.get_all(ADMISSION, fields=["bench", "claimed_at"])
	if not claims:
		return []
	statuses = _bench_statuses([claim.bench for claim in claims])
	cutoff = add_to_date(now_datetime(), hours=-STALE_DEPLOY_HOURS)
	released = []
	for claim in claims:
		status = statuses.get(claim.bench)
		if status in HOLDING_STATUSES and not _deploy_abandoned(status, claim.claimed_at, cutoff):
			continue
		if status == "Deploying":
			# A bench nobody is deploying is not deploying.
			frappe.db.set_value(BENCH, claim.bench, "status", "Error")
		admission.release(claim.bench)
		released.append(claim.bench)
	return released


def _deploy_abandoned(status: str, claimed_at, cutoff) -> bool:
	return status == "Deploying" and bool(claimed_at) and claimed_at < cutoff


def _adopt_orphans() -> list[str]:
	"""Claim a slot for every live instance that holds none, so the counts start honest.

	The twin of the stranded rule, and what makes the feature safe to switch on with instances
	already running: those benches predate the first claim and would otherwise be free.
	"""
	held = set(frappe.get_all(ADMISSION, pluck="bench"))
	live = frappe.get_all(BENCH, filters={"status": ("in", HOLDING_STATUSES)}, fields=["name", "owner"])
	adopted = []
	for bench in live:
		if bench.name in held:
			continue
		# No limit: adoption records what is already running, and must never refuse it.
		if admission.claim(bench.owner, bench.name, 0):
			adopted.append(bench.name)
	return adopted


def _heal_counters() -> list[str]:
	"""Set every `active_instances` to the number of rows that account actually holds."""
	held = _claims_by_account()
	healed = []
	for row in frappe.get_all(ACCOUNT, fields=["name", "active_instances"]):
		expected = held.get(row.name, 0)
		if cint(row.active_instances) == expected:
			continue
		frappe.db.set_value(ACCOUNT, row.name, "active_instances", expected, update_modified=False)
		healed.append(row.name)
	return healed


def _bench_statuses(bench_names: list[str]) -> dict[str, str]:
	rows = frappe.get_all(BENCH, filters={"name": ("in", bench_names)}, fields=["name", "status"])
	return {row.name: row.status for row in rows}


def _claims_by_account() -> dict[str, int]:
	table = DocType(ADMISSION)
	rows = (
		frappe.qb.from_(table)
		.select(table.account, Count("*").as_("total"))
		.groupby(table.account)
		.run(as_dict=True)
	)
	return {row.account: row.total for row in rows}
