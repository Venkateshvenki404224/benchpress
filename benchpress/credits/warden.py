# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The lease warden: a long-lived loop that claims a due lease within seconds of its deadline.

The scheduler cannot do this. `DEFAULT_SCHEDULER_TICK` is four minutes on this deployment and a
cron entry is evaluated once per tick, so a countdown that promises a minute gives away up to
four — 13% of a thirty-minute lease, silently, on every lease.

It runs on **every** node and the conditional claim arbitrates: all wardens see the same due set
and exactly one gets `rowcount == 1` per row. Leaderless on purpose — an election would add a
window in which nothing is sweeping, and the claim already does that work.

**The Frappe cron stays.** This process restarts, and the cron is the net under it while it
does. Two mechanisms, one claim protocol; deleting the cron because the warden is faster removes
the thing that makes restarting the warden safe.
"""

import time

import frappe
from frappe.query_builder.functions import Min

from benchpress.credits import config, drain, lease

POLL_FLOOR = 1
POLL_CEILING = 15
ERROR_BACKOFF = 30


def run() -> None:
	"""The service entry point. Never returns; the container's restart policy is the recovery."""
	while True:
		try:
			time.sleep(tick())
		except Exception:
			# A failure that reaches this far and cannot even be logged should exit, so the
			# restart policy rebuilds the connection rather than a loop retrying a dead one.
			frappe.log_error(title="Lease warden")
			time.sleep(ERROR_BACKOFF)


def tick() -> int:
	"""One pass over the fleet. Returns how long it is safe to sleep afterwards."""
	frappe.db.rollback()  # a long-lived connection would otherwise sweep one frozen snapshot
	if not config.credits_enabled():
		return POLL_CEILING
	drain.sweep_expired_leases()
	return sleep_for(next_deadline(), lease.now_ts())


def sleep_for(deadline: int | None, now: int) -> int:
	"""Sleep until the next deadline, bounded both ways.

	The floor stops a deadline already past from spinning the loop against the database. The
	ceiling stops a quiet fleet from becoming a long blind spot, because a lease armed after
	this pass is invisible to it.
	"""
	if deadline is None:
		return POLL_CEILING
	return max(min(deadline - now, POLL_CEILING), POLL_FLOOR)


def next_deadline() -> int | None:
	"""The earliest deadline still running, or `None` when nothing is leased."""
	instance = frappe.qb.DocType(lease.BENCH)
	rows = (
		frappe.qb.from_(instance)
		.select(Min(instance.expires_at_ts))
		.where(instance.lease_state == lease.ACTIVE)
		.where(instance.expires_at_ts > 0)
	).run()
	return int(rows[0][0]) if rows and rows[0][0] else None
