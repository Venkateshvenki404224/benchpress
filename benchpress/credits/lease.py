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

**The claim protocol is the part that must not go wrong.** A sweep — the cron's or the
warden's — moves a due row to `Stopping` with a conditional update, commits, and hands the stop
to the stop queue. The job then re-reads under `SELECT ... FOR UPDATE` before it touches Docker,
because the sweep's read was true when it ran and a renew may have committed since. Deciding
from an unlocked read stops a bench somebody has paid for, and every ambiguity here resolves
toward never stopping early.

The commit is per claim rather than per batch: one transaction around the whole sweep holds
every claimed row's lock for its duration, and a renew touching one of them fails on the
50-second lock wait — a paying customer blocked by our own bookkeeping.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_datetime, now_datetime, time_diff_in_seconds

from benchpress.credits import account, config

BENCH = "Bench Instance"
LAB = "Lab"
PLAN = "Lease Plan"

ACTIVE = "Active"
STOPPING = "Stopping"
FAILED = "Failed"

EXPIRED_EVENT = "benchpress:lease_expired"
RENEWED_EVENT = "benchpress:lease_renewed"
SWEEP_INDEX = "lease_state_expires_at_ts_index"

STOP_TIMEOUT = 600
DEFAULT_SWEEP_BATCH = 200
DEFAULT_MAX_ATTEMPTS = 5

# Its own queue, never `long`: that one carries `deploy_bench` with a two-hour timeout and a
# single worker, so a stop behind a cold build waits for the build.
STOP_QUEUE = "stops"

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


def plan_for_size(size) -> dict | None:
	"""The lease plan a size deploys at: its own, else the site default."""
	chosen = (size.get("default_lease_plan") if size else None) or config.settings().default_lease_plan
	return frappe.db.get_value(PLAN, chosen, PLAN_FIELDS, as_dict=True) if chosen else None


def priced_sizes() -> list[dict]:
	"""Every `Instance Size` carrying what one lease on it costs — the number the picker shows.

	A size is chosen before a lab exists, so the price cannot come from `cost_of`: there is no
	`deploy_credits` override to honour yet, only the plan and the size's own multiplier.
	"""
	return [{**size, **_size_price(size)} for size in config.instance_sizes()]


def _size_price(size) -> dict:
	plan = plan_for_size(size)
	if not plan:
		return {"lease_credits": None, "lease_label": ""}
	credits = flt(flt(plan.get("credits")) * flt(size.price_multiplier or 1.0), account.PRECISION)
	return {"lease_credits": credits, "lease_label": plan.plan_label}


def batch_cap() -> int:
	"""Most expired leases one sweep may claim. The stop queue, not the SQL, is what this caps."""
	return cint(config.settings().lease_sweep_batch) or DEFAULT_SWEEP_BATCH


def max_attempts() -> int:
	"""Failed stops before a lease parks. Docker being down must not re-queue a job for a week."""
	return cint(config.settings().lease_max_attempts) or DEFAULT_MAX_ATTEMPTS


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
	return arm_at(bench, now_ts() + minutes_for(lab, plan) * 60)


def extend(bench, plan) -> int:
	"""Push the deadline out by the plan's minutes, from the later of now and the deadline.

	Extending from now would silently burn whatever time was left, which is a refund
	conversation. A bench stopped in its grace window has no time to preserve — `disarm` cleared
	the deadline when it stopped — so `now` is what it extends from.
	"""
	base = max(now_ts(), cint(bench.get("expires_at_ts")))
	return arm_at(bench, base + cint(plan.get("minutes")) * 60)


def arm_at(bench, deadline: int) -> int:
	"""Write one deadline and clear whatever the last claim left behind. Returns the deadline."""
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


OWNED_FIELDS = ("expires_at_ts", "lease_state", "stop_claimed_at", "expiry_attempts")


def refresh_into(bench) -> None:
	"""Re-read the lease fields from the row into a document that may be stale.

	`_write` is the only writer of these fields and it bypasses `save()`, so a long-running job
	holding a document loaded before a renewal would write its stale copy back and revert it.
	Observed live: a 162-second redeploy reverted an 8-hour renewal bought 25 seconds before it
	finished, and the ledger kept the 60 credits.
	"""
	stored = frappe.db.get_value(BENCH, bench.name, OWNED_FIELDS, as_dict=True)
	if not stored:
		return
	for field, value in stored.items():
		setattr(bench, field, value)


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


# --- The claim ----------------------------------------------------------------


def claim_due(limit: int | None = None) -> list[str]:
	"""Claim up to `limit` expired leases, committing each. Returns what was claimed."""
	cutoff = now_ts()
	claimed = []
	for row in _due(cutoff, limit or batch_cap()):
		if not _claim(row.name, cutoff):
			continue
		# Registered before the commit, not after: `enqueue_after_commit` hangs the job off the
		# next commit, and that commit is also what releases the claimed row's lock.
		enqueue_stop(row.name, row.node)
		frappe.db.commit()  # nosemgrep -- per claim, so no renew waits behind the whole sweep
		claimed.append(row.name)
	return claimed


def _due(cutoff: int, limit: int) -> list[dict]:
	"""Due rows, oldest deadline first, on the `(lease_state, expires_at_ts)` index.

	`node` rides along so the hand-off needs no second read per row, and parked rows are out of
	the range entirely rather than filtered out of it.
	"""
	instance = frappe.qb.DocType(BENCH)
	return (
		frappe.qb.from_(instance)
		.select(instance.name, instance.node)
		.where(instance.lease_state == ACTIVE)
		.where(instance.expires_at_ts > 0)
		.where(instance.expires_at_ts <= cutoff)
		.orderby(instance.expires_at_ts)
		.limit(limit)
	).run(as_dict=True)


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


def enqueue_stop(bench_name: str, node: str | None = None) -> None:
	frappe.enqueue(
		"benchpress.lifecycle.stopped",
		bench_name=bench_name,
		queue=stop_queue_for(node),
		timeout=STOP_TIMEOUT,
		job_id=f"stop_bench:{bench_name}",
		deduplicate=True,
		from_claim=True,
		enqueue_after_commit=True,  # the job re-reads the claim, so it must not start before it commits
	)


def local_node() -> str:
	"""Which host's Docker daemon this process can reach. Empty means there is only one."""
	return cstr(frappe.conf.get("benchpress_node"))


def stop_queue_for(node: str | None) -> str:
	"""The stop queue whose worker holds this bench's daemon.

	Empty — every row until there is a second host — is the local queue, so routing changes
	nothing today. A named node that is not this one gets its own queue rather than a shared
	one, because a stop run against the wrong daemon reports success: see `assert_local`.
	"""
	node = cstr(node)
	return f"{STOP_QUEUE}_{node}" if node and node != local_node() else STOP_QUEUE


def assert_local(bench) -> None:
	"""Refuse a stop for a container this daemon does not hold.

	`docker_manager.stop_container` swallows `NotFound` as success, so a stop that reaches the
	wrong node marks the row `Stopped` while the container keeps running elsewhere — compute
	nobody is billed for, recorded as billed and stopped, and invisible in every log.
	"""
	node = cstr(bench.get("node"))
	if node and node != local_node():
		frappe.throw(
			_("Bench {0} runs on node {1}, not on {2}.").format(
				bench.name, node, local_node() or _("this one")
			)
		)


# --- The stop job's half of the protocol ---------------------------------------


def confirm_expiry(bench_name: str, from_claim: bool = False) -> bool:
	"""Whether a claimed stop should still go ahead, decided under the lock renew takes.

	Returns `False`, and hands the claim back, when the deadline moved after the sweep claimed
	the row.

	`from_claim` is what tells the two callers apart on a row carrying no claim, because they
	look identical from the row alone. A user pressing Stop always goes ahead. A queued expiry
	whose claim has gone does not: a queued stop can sit for as long as the stop queue is busy,
	and by the time it runs the bench may have been stopped, started and paid for again.

	The lock is released before the caller returns: a container stop can take thirty seconds,
	and holding a row lock across it would make a renew wait for the bench it is trying to save.
	"""
	if frappe.db.get_value(BENCH, bench_name, "lease_state") != STOPPING:
		return not from_claim
	row = frappe.db.get_value(BENCH, bench_name, LEASE_FIELDS, as_dict=True, for_update=True)
	renewed = cint(row.expires_at_ts) > now_ts()
	if renewed:
		release(bench_name)
	frappe.db.commit()  # nosemgrep -- releases the row lock before Docker is touched
	return not renewed


def release(bench_name: str, failed: bool = False) -> None:
	"""Hand a claim back — the deadline moved, or the stop failed and should be retried.

	A stop that has failed `max_attempts` times parks instead of returning to the sweep, so it
	stops taking a batch slot from the leases queued behind it.
	"""
	values = {"lease_state": ACTIVE, "stop_claimed_at": None}
	if failed:
		values["expiry_attempts"] = cint(frappe.db.get_value(BENCH, bench_name, "expiry_attempts")) + 1
		if values["expiry_attempts"] >= max_attempts():
			values["lease_state"] = FAILED
	frappe.db.set_value(BENCH, bench_name, values, update_modified=False)


def park(bench_name: str) -> None:
	"""Take a lease out of the sweep for good. An error state, deliberately, rather than a skip."""
	frappe.db.set_value(
		BENCH, bench_name, {"lease_state": FAILED, "stop_claimed_at": None}, update_modified=False
	)


def record_stop_started(bench_name: str) -> None:
	"""Stamp when the job picked the stop up, so queue time and Docker time can be told apart."""
	frappe.db.set_value(BENCH, bench_name, "stop_started_at", now_datetime(), update_modified=False)


def record_stopped(bench, expired: bool) -> None:
	"""Stamp when the container stopped, and for an expiry how late that was.

	`container_stopped_at - expires_at_ts` is the SLO for this whole feature. Clamped at zero:
	the platform does not stop a lease early, and a clock that moved must not be able to report
	that it did.
	"""
	values = {"container_stopped_at": now_datetime()}
	if expired:
		values["expiry_lateness"] = max(now_ts() - cint(bench.get("expires_at_ts")), 0)
	_write(bench, values)


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
