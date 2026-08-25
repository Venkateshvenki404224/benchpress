# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The repair pass for admission, because what a claim holds is denormalised twice over.

Named for admission and not for reconciliation: `credits.reconcile` was the burn-rate meter's
repair pass, `test_meter_gone` asserts that name never comes back, and this repairs a count of
rows rather than a rate.

`Bench Admission` rows are the truth. `Credit Account.active_instances` counts them and
`reserved_credits` sums their holds, and every one of the three is written by a worker that can
be killed between them. A worker killed mid-deploy leaks a slot and the credits it reserved
forever, and a caller with a cap of two is then locked out until somebody notices - so this runs
on the `*/5` cron beside the balance sweep, not on the daily list.

It is pure database work: three grouped reads, no Docker call anywhere, which is why it is safe
on `queue-short` for exactly the reason `sweep.enforce_limits` is.

Three rules, in order. Expiring first and healing last is what makes a double release harmless:
the counter follows the rows, so it cannot be driven negative by a release that ran twice.
"""

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_to_date, cint, flt, now_datetime

from benchpress.credits import account, admission

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"

HOLDING_STATUSES = ("Deploying", "Running")

# `DEPLOY_JOB_TIMEOUT` is 7200 seconds, and this is that plus a margin. A claim older than this
# whose bench is still `Deploying` belongs to a job that no longer exists.
STALE_DEPLOY_HOURS = 3

# Both aggregates are floats at precision 6, so they are compared with a tolerance rather than
# for equality. Anything larger than this is drift, not arithmetic.
TOLERANCE = 1e-6

# A claim is taken in the request; the bench only leaves `Draft` when a worker picks the deploy
# up. Releasing on status alone would take the slot back from a deploy that is merely queued,
# which is exactly what happens whenever `queue-long` is behind.
CLAIM_GRACE_MINUTES = 15


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
	now = now_datetime()
	settled = add_to_date(now, minutes=-CLAIM_GRACE_MINUTES)
	abandoned = add_to_date(now, hours=-STALE_DEPLOY_HOURS)
	released = []
	for claim in claims:
		status = statuses.get(claim.bench)
		if status == "Deploying" and _older_than(claim.claimed_at, abandoned):
			# A bench nobody is deploying is not deploying.
			frappe.db.set_value(BENCH, claim.bench, "status", "Error")
		elif status in HOLDING_STATUSES or not _older_than(claim.claimed_at, settled):
			continue
		admission.release(claim.bench)
		released.append(claim.bench)
	return released


def _older_than(claimed_at, cutoff) -> bool:
	return bool(claimed_at) and claimed_at < cutoff


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
	"""Set every account's slot count and hold to what its own rows add up to."""
	held = _claims_by_account()
	healed = []
	for row in frappe.get_all(ACCOUNT, fields=["name", "active_instances", "reserved_credits"]):
		totals = held.get(row.name) or {"slots": 0, "credits": 0.0}
		slots_agree = cint(row.active_instances) == totals["slots"]
		credits_agree = abs(flt(row.reserved_credits) - totals["credits"]) <= TOLERANCE
		if slots_agree and credits_agree:
			continue
		frappe.db.set_value(
			ACCOUNT,
			row.name,
			{"active_instances": totals["slots"], "reserved_credits": totals["credits"]},
			update_modified=False,
		)
		healed.append(row.name)
	return healed


def _bench_statuses(bench_names: list[str]) -> dict[str, str]:
	rows = frappe.get_all(BENCH, filters={"name": ("in", bench_names)}, fields=["name", "status"])
	return {row.name: row.status for row in rows}


def _claims_by_account() -> dict[str, dict]:
	table = DocType(ADMISSION)
	rows = (
		frappe.qb.from_(table)
		.select(table.account, Count("*").as_("slots"), Sum(table.held_credits).as_("credits"))
		.groupby(table.account)
		.run(as_dict=True)
	)
	return {row.account: {"slots": row.slots, "credits": flt(row.credits, account.PRECISION)} for row in rows}
