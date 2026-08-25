# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The lease: what a deploy buys, when it runs out, and who is allowed to end it.

A deploy spends credits once and buys a fixed window. The bench stops when the window closes.
There is no accrual, no settle and no reconciler — the whole clock is one indexed column swept
periodically, and the browser renders that column rather than deciding anything from it.

**The deadline is an epoch integer and the cutoff is bound in Python.** `frappe` writes every
Datetime naive in the site timezone while the database session may be in another; on this
deployment the two are 5h30m apart, so `expires_at <= NOW()` in SQL is five and a half hours of
free compute per lease. `now_ts` is the only clock this module reads.

**The claim protocol is the part that must not go wrong.** The sweep moves a due row to
`Stopping` with a conditional update, commits, and hands the stop to `queue-long`. The job then
re-reads under `SELECT ... FOR UPDATE` before it touches Docker, because the sweep's read was
true when it ran and a renew may have committed since. Deciding from an unlocked read stops a
bench somebody has paid for, and every ambiguity here resolves toward never stopping early.

The commit is per claim rather than per batch: one transaction around the whole sweep holds
every claimed row's lock for its duration, and a renew touching one of them fails on the
50-second lock wait — a paying customer blocked by our own bookkeeping.
"""

import time

import frappe
from frappe.utils import cint, flt, get_datetime, now_datetime, time_diff_in_seconds

from benchpress.credits import account, config

BENCH = "Bench Instance"
LAB = "Lab"
PLAN = "Lease Plan"

ACTIVE = "Active"
STOPPING = "Stopping"

EXPIRED_EVENT = "benchpress:lease_expired"
RENEWED_EVENT = "benchpress:lease_renewed"
SWEEP_INDEX = "lease_state_expires_at_ts_index"

STOP_TIMEOUT = 600
DEFAULT_SWEEP_BATCH = 200

# Failed stops park the row instead of taking a sweep slot every tick. Docker being down is not
# a reason to keep re-queueing the same job for a week.
MAX_EXPIRY_ATTEMPTS = 5

PLAN_FIELDS = ["name", "plan_label", "minutes", "credits"]
LEASE_FIELDS = ["lease_state", "expires_at_ts"]


def now_ts() -> int:
	"""The one clock in this module. Never SQL `NOW()` — see the module docstring."""
	return int(time.time())


def now_ms() -> int:
	"""The same clock at the resolution a countdown anchors on.

	Deadlines are whole seconds; the anchor is not. Rounding the sample down puts the browser
	up to a second behind the server, and `leaseFor` rounds the remainder up again.
	"""
	return int(time.time() * 1000)


# --- Pricing and configuration -------------------------------------------------


def plan_for(lab) -> dict | None:
	"""The lease plan a lab deploys at: its own, else its size's, else the default.

	The same precedence rule as `config.size_for_lab`, for the same reason — what the author
	chose wins over what their resources imply.
	"""
	size = config.size_for_lab(lab)
	chosen = (
		lab.get("default_lease_plan")
		or (size.get("default_lease_plan") if size else None)
		or config.settings().default_lease_plan
	)
	if not chosen:
		return None
	return frappe.db.get_value(PLAN, chosen, PLAN_FIELDS, as_dict=True)


def minutes_for(lab, plan) -> int:
	"""The plan's minutes, clipped to the lab's ceiling. `0` on the ceiling means unlimited."""
	minutes = cint(plan.get("minutes"))
	ceiling = cint(lab.get("max_lease_minutes"))
	return min(minutes, ceiling) if ceiling else minutes


def cost_of(lab, plan) -> float:
	"""`plan.credits x size.price_multiplier`, unless the lab prices its own deploys."""
	override = flt(lab.get("deploy_credits"))
	if override:
		return override
	size = config.size_for_lab(lab)
	multiplier = flt(size.price_multiplier) if size else 1.0
	return flt(flt(plan.get("credits")) * multiplier, account.PRECISION)


def active_plans() -> list[dict]:
	"""The duration catalog in display order, for the picker and the pricing page."""
	return frappe.get_all(
		PLAN,
		filters={"is_active": 1},
		fields=["name", "plan_label", "minutes", "credits"],
		order_by="sort_order asc, minutes asc",
	)


# --- Arming and clearing the clock ---------------------------------------------


def arm(bench, lab, plan) -> int:
	"""Set the deadline and mark the lease `Active`. Returns the deadline.

	Written before the caller saves `status`, so the two land in one transaction. A `Running`
	row carrying a deadline that has already passed is the resurrection bug: the next sweep
	claims it and the bench dies seconds after the user started it.
	"""
	return _arm_at(bench, now_ts() + minutes_for(lab, plan) * 60)


def extend(bench, plan) -> int:
	"""Push the deadline out by the plan's minutes, from the later of now and the deadline.

	Extending from now would silently burn whatever time was left, which is a refund
	conversation. A bench stopped in its grace window has no time to preserve — `disarm` cleared
	the deadline when it stopped — so `now` is what it extends from.
	"""
	base = max(now_ts(), cint(bench.get("expires_at_ts")))
	return _arm_at(bench, base + cint(plan.get("minutes")) * 60)


def _arm_at(bench, deadline: int) -> int:
	_write(
		bench,
		{
			"expires_at_ts": deadline,
			"lease_state": ACTIVE,
			"stop_claimed_at": None,
			"expiry_attempts": 0,
		},
	)
	return deadline


def remaining(bench) -> int:
	"""Seconds still on the clock, never negative."""
	return max(cint(bench.get("expires_at_ts")) - now_ts(), 0)


def ceiling_seconds(lab) -> int:
	"""How long one lease on this lab may run in total. `0` is unlimited, here as everywhere."""
	return cint(lab.get("max_lease_minutes")) * 60


def grace_ends_at(bench) -> int | None:
	"""When the reaper will take this stopped bench, or `None` when nothing reaps it.

	The last moment a renew can still bring the container back rather than rebuild it. The reaper
	measures from `modified`, which the stop wrote, so the elapsed part is a difference between
	two site-local datetimes and the result is anchored on `now_ts` — no timezone reaches the
	arithmetic. See the module docstring for why that matters here.
	"""
	days = cint(config.settings().reap_after_days)
	if not days:
		return None
	stopped_for = time_diff_in_seconds(now_datetime(), get_datetime(bench.get("modified")))
	return now_ts() + days * 86400 - int(stopped_for)


def disarm(bench) -> None:
	"""Clear the clock on a bench that has stopped. Free on a row that never held a lease."""
	if not bench.get("lease_state") and not cint(bench.get("expires_at_ts")):
		return
	_write(
		bench,
		{"expires_at_ts": 0, "lease_state": "", "stop_claimed_at": None, "expiry_attempts": 0},
	)


def _write(bench, values: dict) -> None:
	"""Write the row and the in-memory document together, without touching `modified`.

	Both halves matter. The row so the lease is durable even if the caller never saves; the
	document so the caller's own `save()` writes the same values back rather than the stale
	`None` it was loaded with — which is also what keeps the permlevel check quiet, since it
	compares against what is stored.
	"""
	frappe.db.set_value(BENCH, bench.name, values, update_modified=False)
	for field, value in values.items():
		setattr(bench, field, value)  # a Document or the dict an indexed read returns


# --- The sweep -----------------------------------------------------------------


def sweep_expired_leases() -> dict:
	"""The cron entry. Decides only — the stop itself goes to `queue-long`."""
	if not config.credits_enabled():
		return {"claimed": []}
	return {"claimed": claim_due()}


def claim_due(limit: int | None = None) -> list[str]:
	"""Claim up to `limit` expired leases, committing each. Returns what was claimed."""
	cutoff = now_ts()
	claimed = []
	for name in _due(cutoff, limit or cint(config.settings().lease_sweep_batch) or DEFAULT_SWEEP_BATCH):
		if not _claim(name, cutoff):
			continue
		# Registered before the commit, not after: `enqueue_after_commit` hangs the job off the
		# next commit, and that commit is also what releases the claimed row's lock.
		_enqueue_stop(name)
		frappe.db.commit()  # nosemgrep -- per claim, so no renew waits behind the whole sweep
		claimed.append(name)
	return claimed


def _due(cutoff: int, limit: int) -> list[str]:
	"""Due rows, oldest deadline first, on the `(lease_state, expires_at_ts)` index."""
	instance = frappe.qb.DocType(BENCH)
	return (
		frappe.qb.from_(instance)
		.select(instance.name)
		.where(instance.lease_state == ACTIVE)
		.where(instance.expires_at_ts > 0)
		.where(instance.expires_at_ts <= cutoff)
		.where(instance.expiry_attempts < MAX_EXPIRY_ATTEMPTS)
		.orderby(instance.expires_at_ts)
		.limit(limit)
	).run(pluck=True)


def _claim(bench_name: str, cutoff: int) -> bool:
	"""Move one row to `Stopping`, conditionally. `False` means another sweep got there first."""
	instance = frappe.qb.DocType(BENCH)
	(
		frappe.qb.update(instance)
		.set(instance.lease_state, STOPPING)
		.set(instance.stop_claimed_at, now_datetime())
		.where(instance.name == bench_name)
		.where(instance.lease_state == ACTIVE)
		.where(instance.expires_at_ts <= cutoff)
	).run()
	return frappe.db._cursor.rowcount == 1


def _enqueue_stop(bench_name: str) -> None:
	frappe.enqueue(
		"benchpress.deploy_manager.stop_bench",
		bench_name=bench_name,
		queue="long",
		timeout=STOP_TIMEOUT,
		job_id=f"stop_bench:{bench_name}",
		deduplicate=True,
		enqueue_after_commit=True,  # the job re-reads the claim, so it must not start before it commits
	)


# --- The stop job's half of the protocol ---------------------------------------


def confirm_expiry(bench_name: str) -> bool:
	"""Whether a claimed stop should still go ahead, decided under the lock renew takes.

	Returns `False`, and hands the claim back, when the deadline moved after the sweep claimed
	the row. A bench with no claim on it is not this protocol's business and always goes ahead.

	The lock is released before the caller returns: a container stop can take thirty seconds,
	and holding a row lock across it would make a renew wait for the bench it is trying to save.
	"""
	if frappe.db.get_value(BENCH, bench_name, "lease_state") != STOPPING:
		return True
	row = frappe.db.get_value(BENCH, bench_name, LEASE_FIELDS, as_dict=True, for_update=True)
	renewed = cint(row.expires_at_ts) > now_ts()
	if renewed:
		release(bench_name)
	frappe.db.commit()  # nosemgrep -- releases the row lock before Docker is touched
	return not renewed


def release(bench_name: str, failed: bool = False) -> None:
	"""Hand a claim back — the deadline moved, or the stop failed and should be retried."""
	values = {"lease_state": ACTIVE, "stop_claimed_at": None}
	if failed:
		values["expiry_attempts"] = cint(frappe.db.get_value(BENCH, bench_name, "expiry_attempts")) + 1
	frappe.db.set_value(BENCH, bench_name, values, update_modified=False)


def announce_expired(bench) -> None:
	"""Tell this owner's open tabs that the window closed, and only this owner's."""
	_announce(EXPIRED_EVENT, bench, "lease_expired")


def announce_renewed(bench) -> None:
	"""Tell this owner's open tabs that the deadline moved."""
	_announce(RENEWED_EVENT, bench, "lease_renewed")


def _announce(event: str, bench, reason: str) -> None:
	"""Push reconcilable state to one owner.

	Full state rather than a delta, and never `bench.as_dict()` — this doctype holds three
	passwords. `revision` is a millisecond stamp so a tab that receives two events out of order
	can keep the later one.
	"""
	frappe.publish_realtime(
		event,
		{
			"bench": bench.name,
			"lab_id": frappe.db.get_value(LAB, bench.lab, "lab_id"),
			"state": bench.status,
			"expires_at_ts": cint(bench.get("expires_at_ts")),
			"server_now_ms": now_ms(),
			"revision": now_ms(),
			"reason": reason,
		},
		user=bench.owner,
		after_commit=True,
	)
