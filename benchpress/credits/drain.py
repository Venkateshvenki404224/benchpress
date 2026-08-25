# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Whether the fleet's expiries actually land, and how late they were when they did.

`lease` decides what a lease is and holds the claim protocol. This module runs that protocol
over the whole fleet, on the cron and in the warden, and answers the three questions a claim
alone cannot.

**Is the drain keeping up?** If leases fall due faster than `batch cap x cadence`, every one of
them overruns, forever, and nothing is written to any log. There is no error to find because
each individual sweep succeeded. The backlog gauge is the only alarm there can be.

**Did anything get stranded?** A worker killed mid-batch leaves its rows in `Stopping`. The
claim succeeded, so no later sweep can see them — they sit there until somebody notices a bench
that will not die. The reclaim re-queues them, and parks the ones no retry will fix.

**How late is late?** `container_stopped_at - expires_at_ts` per stop is the SLO for the whole
feature, and `stop_slo` is where it is read back as a histogram rather than a claim.

Every cutoff here is built in Python, for the reason `lease` documents: the app clock and the
database clock on this deployment are 5h30m apart.
"""

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import add_to_date, cint, now_datetime

from benchpress.credits import config, lease

DEFAULT_RECLAIM_SECONDS = 300

# The streak lives in the cache, not a column: it describes the sweep, not any one bench.
OVERFLOW_STREAK_KEY = "benchpress:lease_overflow_streak"

# One tick behind is a burst. Two in a row is arrivals outrunning the drain, which is the
# failure that is otherwise completely silent.
OVERFLOW_ALARM_STREAK = 2

SLO_BUCKETS = (5, 15, 60, 300, 900)


def sweep_expired_leases() -> dict:
	"""The cron entry and the warden's one pass. Decides only — stops go to the stop queue."""
	if not config.credits_enabled():
		return {"due": 0, "cap": 0, "overflow": 0, "claimed": [], "reclaimed": []}
	cap = lease.batch_cap()
	due = backlog()
	overflow = _record_overflow(due, cap)
	return {
		"due": due,
		"cap": cap,
		"overflow": overflow,
		"claimed": lease.claim_due(cap),
		"reclaimed": reclaim_stalled(cap),
	}


def backlog(cutoff: int | None = None) -> int:
	"""Leases past their deadline and still claimable.

	Measured before the claim, or a full batch would always report a clear backlog. Parked rows
	are excluded: they are not coming back, and counting them would leave the alarm on forever.
	"""
	instance = frappe.qb.DocType(lease.BENCH)
	return (
		frappe.qb.from_(instance)
		.select(Count("*"))
		.where(instance.lease_state == lease.ACTIVE)
		.where(instance.expires_at_ts > 0)
		.where(instance.expires_at_ts <= (lease.now_ts() if cutoff is None else cutoff))
	).run()[0][0]


def reclaim_stalled(limit: int | None = None) -> list[str]:
	"""Re-queue stops whose claim went stale, and park the ones no retry will fix.

	Committed per row for the same reason the claim is: one transaction across the batch holds
	every row's lock for the whole reclaim, and a renew touching one of them waits behind it.
	"""
	attempts_limit = lease.max_attempts()
	reclaimed = []
	for row in _stalled(limit or lease.batch_cap()):
		attempts = cint(row.expiry_attempts) + 1
		if attempts >= attempts_limit:
			lease.park(row.name)
		else:
			_reclaim(row, attempts)
			reclaimed.append(row.name)
		frappe.db.commit()  # nosemgrep -- per row, so no renew waits behind the whole reclaim
	return reclaimed


def stop_slo(hours: int = 24) -> dict:
	"""How late expired leases actually stopped, over the last `hours`.

	The reported histogram is the SLO for this feature. A user-pressed stop records no lateness
	and is absent here — nothing was due, so a zero would flatter the numbers.
	"""
	rows = sorted(_lateness(hours))
	if not rows:
		return {"count": 0, "p50": 0, "p90": 0, "max": 0, "buckets": _empty_buckets()}
	return {
		"count": len(rows),
		"p50": _percentile(rows, 50),
		"p90": _percentile(rows, 90),
		"max": rows[-1],
		"buckets": _bucketed(rows),
	}


def reclaim_seconds() -> int:
	"""How long a claimed stop may sit before another sweep assumes its worker is gone."""
	return cint(config.settings().lease_reclaim_seconds) or DEFAULT_RECLAIM_SECONDS


# --- The gauge -----------------------------------------------------------------


def _record_overflow(due: int, cap: int) -> int:
	"""What the cap left behind, and an alarm once arrivals have outrun the drain.

	Logged on the transition into a second consecutive overflow rather than on every sweep after
	it: an episode is one entry in the Error Log, not one every five minutes until somebody
	looks.
	"""
	overflow = max(due - cap, 0) if cap else 0
	cache = frappe.cache()
	if not overflow:
		cache.delete_value(OVERFLOW_STREAK_KEY)
		return 0
	streak = cint(cache.get_value(OVERFLOW_STREAK_KEY)) + 1
	cache.set_value(OVERFLOW_STREAK_KEY, streak)
	if streak == OVERFLOW_ALARM_STREAK:
		frappe.log_error(
			title="Lease sweep backlog",
			message=f"{due} leases due against a batch cap of {cap}: "
			f"{overflow} left behind for {streak} consecutive sweeps.",
		)
	return overflow


# --- The reclaim ---------------------------------------------------------------


def _stalled(limit: int) -> list[dict]:
	"""Claims older than the reclaim window, oldest first.

	A `Stopping` row with no stamp is included. Nothing writes one, so a row that has none is
	stranded for good rather than merely late.
	"""
	cutoff = add_to_date(now_datetime(), seconds=-reclaim_seconds())
	instance = frappe.qb.DocType(lease.BENCH)
	return (
		frappe.qb.from_(instance)
		.select(instance.name, instance.node, instance.expiry_attempts)
		.where(instance.lease_state == lease.STOPPING)
		.where(instance.stop_claimed_at.isnull() | (instance.stop_claimed_at <= cutoff))
		.orderby(instance.stop_claimed_at)
		.limit(limit)
	).run(as_dict=True)


def _reclaim(row, attempts: int) -> None:
	"""Take the claim over and queue the stop again.

	The stamp is refreshed first: without it the next interval reclaims the same row while the
	job this one queued is still in flight.
	"""
	frappe.db.set_value(
		lease.BENCH,
		row.name,
		{"stop_claimed_at": now_datetime(), "expiry_attempts": attempts},
		update_modified=False,
	)
	lease.enqueue_stop(row.name, row.node)


# --- The histogram -------------------------------------------------------------


def _lateness(hours: int) -> list[int]:
	since = add_to_date(now_datetime(), hours=-hours)
	instance = frappe.qb.DocType(lease.BENCH)
	return (
		frappe.qb.from_(instance)
		.select(instance.expiry_lateness)
		.where(instance.expiry_lateness.isnotnull())
		.where(instance.container_stopped_at >= since)
	).run(pluck=True)


def _percentile(rows: list[int], percent: int) -> int:
	return rows[min(len(rows) * percent // 100, len(rows) - 1)]


def _bucketed(rows: list[int]) -> dict:
	buckets = _empty_buckets()
	for value in rows:
		buckets[_bucket_label(value)] += 1
	return buckets


def _empty_buckets() -> dict:
	return dict.fromkeys([_bucket_label(bound) for bound in SLO_BUCKETS] + [_overflow_label()], 0)


def _bucket_label(value: int) -> str:
	for bound in SLO_BUCKETS:
		if value <= bound:
			return f"<={bound}s"
	return _overflow_label()


def _overflow_label() -> str:
	return f">{SLO_BUCKETS[-1]}s"
