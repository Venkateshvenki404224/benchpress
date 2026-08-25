# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The enforcement sweep: which running instances have to stop, and who should be warned first.

Its own cron, never folded into `collect_bench_stats`. That job already spends ~2s per container
on `stats(stream=False)` and exceeds its own window past ~25 benches; an enforcement decision that
queues behind Docker I/O is an enforcement decision that arrives late, and a TTL that fires late
is a TTL nobody trusts.

So this makes **no Docker calls at all**. Hours are `now - started_at`, balances are arithmetic on
the burn rate, and everything it loads it loads for the whole fleet at once: one query for the
running instances, one for their labs, one for their owners' accounts, one for the passes. The
grouping is a dict, so the pass is O(N) in running instances.

**Deciding is not acting.** Scheduled jobs run on `queue-short`, which has no Docker socket
mounted — the same constraint that makes the stats cron write `Unknown`. The sweep therefore
decides, then hands each stop to `queue-long`, the only worker that can reach a container.

It warns before it acts: once per run before a TTL stop, and once per depletion before credits run
out. A limit that arrives without warning reads as a fault.
"""

import frappe
from frappe.utils import cint, flt, get_datetime, now_datetime, time_diff_in_seconds

from benchpress.credits import account, config, notify, passes

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
LAB = "Lab"

RUNNING_FIELDS = ["name", "owner", "lab", "started_at", "ttl_warned_at"]
ACCOUNT_FIELDS = ["name", *account.BALANCE_FIELDS, "lifetime_purchased", "low_balance_warned"]

TTL_WARNING_MINUTES = 15
STOP_TIMEOUT = 600


def enforce_limits() -> dict:
	"""One indexed query, pure datetime math, zero Docker calls."""
	if not config.credits_enabled():
		return _nothing_to_do()
	running = frappe.get_all(BENCH, filters={"status": "Running"}, fields=RUNNING_FIELDS)
	if not running:
		return _nothing_to_do()
	return LimitSweep(running).run()


class LimitSweep:
	"""One pass over the running fleet, with everything it needs already loaded."""

	def __init__(self, running: list):
		self.running = running
		self.settings = config.settings()
		self.exempt = passes.active_pass_benches([bench.name for bench in running])
		self.lab_ids = _lab_ids({bench.lab for bench in running})
		self.accounts = _accounts({bench.owner for bench in running})
		self.stopped: list[str] = []
		self.warned: list[str] = []

	def run(self) -> dict:
		for owner, benches in self._by_owner().items():
			self._enforce_for_owner(owner, benches)
		return {"checked": len(self.running), "stopped": self.stopped, "warned": self.warned}

	def _by_owner(self) -> dict:
		"""Group once into a dict: the balance is per owner, the TTL is per instance."""
		grouped: dict[str, list] = {}
		for bench in self.running:
			grouped.setdefault(bench.owner, []).append(bench)
		return grouped

	def _enforce_for_owner(self, owner: str, benches: list) -> None:
		row = self.accounts.get(owner)
		out_of_credits = self._out_of_credits(row)
		for bench in benches:
			if bench.name not in self.exempt:
				self._enforce_one(bench, out_of_credits)
		self._settle_low_balance_warning(owner, row)

	def _enforce_one(self, bench, out_of_credits: bool) -> None:
		bench.lab_id = self.lab_ids.get(bench.lab)
		minutes_left = self._minutes_left(bench)
		reason = self._stop_reason(minutes_left, out_of_credits)
		if reason:
			self._stop(bench, reason)
		elif minutes_left is not None and minutes_left <= TTL_WARNING_MINUTES:
			self._warn_ttl(bench, minutes_left)

	# --- Deciding -------------------------------------------------------------

	def _minutes_left(self, bench) -> float | None:
		"""Minutes before this run hits the TTL, or `None` when there is no TTL to hit."""
		max_hours = cint(self.settings.max_run_hours)
		if not max_hours or not bench.started_at:
			return None
		ran_minutes = time_diff_in_seconds(now_datetime(), get_datetime(bench.started_at)) / 60.0
		return max_hours * 60 - ran_minutes

	def _stop_reason(self, minutes_left: float | None, out_of_credits: bool) -> str | None:
		"""A code, not a sentence — `notify` owns every word a user reads."""
		if minutes_left is not None and minutes_left <= 0:
			return notify.TTL_REACHED
		if out_of_credits:
			return notify.OUT_OF_CREDITS
		return None

	def _out_of_credits(self, row) -> bool:
		"""No account row means no balance to be out of — credits were only just switched on."""
		return bool(row) and account.available(row) <= 0

	# --- Acting ---------------------------------------------------------------

	def _stop(self, bench, reason: str) -> None:
		_enqueue_stop(bench.name)
		notify.announce_stop(bench, reason)
		self.stopped.append(bench.name)

	def _warn_ttl(self, bench, minutes_left: float) -> None:
		if notify.already_warned(bench.ttl_warned_at, bench.started_at):
			return
		notify.warn_ttl(bench, max(int(minutes_left), 0))
		notify.stamp_warning(bench.name, "ttl_warned_at")
		self.warned.append(bench.name)

	def _settle_low_balance_warning(self, owner: str, row) -> None:
		"""Warn once per depletion, and re-arm the warning when the balance recovers."""
		threshold = self._warn_threshold(row)
		if not row or not threshold:
			return
		available = account.available(row)
		if available > threshold:
			self._clear_low_balance_flag(owner, row)
		elif not row.low_balance_warned:
			notify.warn_low_balance(owner, available, threshold)
			_set_low_balance_flag(owner, 1)
			self.warned.append(owner)

	def _clear_low_balance_flag(self, owner: str, row) -> None:
		if row.low_balance_warned:
			_set_low_balance_flag(owner, 0)

	def _warn_threshold(self, row) -> float:
		"""`low_balance_warn_percent` of what this account last put in.

		Purchases are the reference once there have been any; until then the signup grant is, so a
		free user is warned against the only number they were ever given.
		"""
		percent = cint(self.settings.low_balance_warn_percent)
		if not percent or not row:
			return 0.0
		reference = flt(row.lifetime_purchased) or flt(self.settings.signup_grant_credits)
		return flt(reference * percent / 100.0)


# --- The loads, one query each -----------------------------------------------


def _lab_ids(lab_names: set) -> dict:
	"""`{lab: lab_id}` — the readable name every notice uses instead of an md5."""
	rows = frappe.get_all(LAB, filters={"name": ("in", sorted(lab_names))}, fields=["name", "lab_id"])
	return {row.name: row.lab_id for row in rows}


def _accounts(owners: set) -> dict:
	"""Every relevant account in one indexed query — never a `get_doc` per owner."""
	rows = frappe.get_all(ACCOUNT, filters={"name": ("in", sorted(owners))}, fields=ACCOUNT_FIELDS)
	return {row.name: row for row in rows}


# --- The writes ---------------------------------------------------------------


def _enqueue_stop(bench_name: str) -> None:
	"""Deduplicated, so a sweep that overlaps the previous one cannot stop the same bench twice."""
	frappe.enqueue(
		"benchpress.deploy_manager.stop_bench",
		bench_name=bench_name,
		queue="long",
		timeout=STOP_TIMEOUT,
		job_id=f"stop_bench:{bench_name}",
		deduplicate=True,
		enqueue_after_commit=True,  # the job re-reads `status`, so it must not start before the commit
	)


def _set_low_balance_flag(owner: str, value: int) -> None:
	frappe.db.set_value(ACCOUNT, owner, "low_balance_warned", value, update_modified=False)


def _nothing_to_do() -> dict:
	return {"checked": 0, "stopped": [], "warned": []}
