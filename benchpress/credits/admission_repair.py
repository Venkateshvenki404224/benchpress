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

It is pure database work: a handful of grouped reads, no Docker call anywhere, which is why it is safe
on `queue-short` for exactly the reason `sweep.enforce_limits` is.

Five rules, in order. Expiring first and healing last is what makes a double release harmless:
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
SITE = "Bench Site"

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
	"""Expire stranded claims, retire stranded sites, adopt orphans, re-key misattributions, heal the counters."""
	released = _release_stranded()
	retired = _retire_stranded_sites()
	adopted = _adopt_orphans()
	rekeyed = _rekey_misattributed()
	healed = _heal_counters()
	if released or retired or adopted or rekeyed or healed:
		frappe.logger("benchpress").warning(
			f"admission drift: released {len(released)}, retired {len(retired)}, "
			f"adopted {len(adopted)}, rekeyed {len(rekeyed)}, healed {len(healed)}"
		)
	return {
		"released": released,
		"retired": retired,
		"adopted": adopted,
		"rekeyed": rekeyed,
		"healed": healed,
	}


def _retire_stranded_sites() -> list[str]:
	"""Deactivate every site name claimed for a deploy that never arrived.

	`api.create_bench` claims the name as `Creating` and a worker sets it `Active`, so a claim
	still `Creating` after the deploy window belongs to a job that no longer exists. Deactivated
	and never deleted: an `Inactive` row can still own a live database, and the bench that
	claimed the name keeps it - a redeploy reactivates the same row.

	`patches.retire_orphaned_creating_sites` did this once for a removed endpoint; a claim in
	the request makes `Creating` a state a dead worker can reach again, so it is a standing rule.
	"""
	cutoff = add_to_date(now_datetime(), hours=-STALE_DEPLOY_HOURS)
	stranded = frappe.get_all(SITE, filters={"status": "Creating", "modified": ("<", cutoff)}, pluck="name")
	for name in stranded:
		frappe.db.set_value(SITE, name, "status", "Inactive", update_modified=False)
	return stranded


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


def _rekey_misattributed() -> list[str]:
	"""Move every claim held against somebody other than its bench's owner onto that owner.

	The rest of this pass cannot see the drift: `_heal_counters` sums rows by their own `account`,
	so a claim on the wrong account and the wrong counter that follows from it agree with each
	other forever. Only the rows move here, and the heal that runs next is what makes both
	accounts' counters right — which is why this rule cannot be the last one.

	`claimed_at` is left alone. The grace period in `_release_stranded` is about how long the
	deploy has had, not about when the repair noticed.
	"""
	claims = frappe.get_all(ADMISSION, fields=["bench", "account"])
	if not claims:
		return []
	owners = _bench_owners([claim.bench for claim in claims])
	rekeyed = []
	for claim in claims:
		owner = owners.get(claim.bench)
		if not owner or owner == claim.account:
			continue
		# The link needs somewhere to point, exactly as adoption opens one for a bench it finds.
		account.ensure_account(owner)
		frappe.db.set_value(ADMISSION, claim.bench, "account", owner, update_modified=False)
		rekeyed.append(claim.bench)
	return rekeyed


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


def _bench_owners(bench_names: list[str]) -> dict[str, str]:
	rows = frappe.get_all(BENCH, filters={"name": ("in", bench_names)}, fields=["name", "owner"])
	return {row.name: row.owner for row in rows}


def _claims_by_account() -> dict[str, dict]:
	table = DocType(ADMISSION)
	rows = (
		frappe.qb.from_(table)
		.select(table.account, Count("*").as_("slots"), Sum(table.held_credits).as_("credits"))
		.groupby(table.account)
		.run(as_dict=True)
	)
	return {row.account: {"slots": row.slots, "credits": flt(row.credits, account.PRECISION)} for row in rows}
