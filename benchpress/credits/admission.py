# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Admission: the concurrency and credit decision, taken as a write that can fail.

Counting running instances and comparing cannot refuse anything, and neither can reading a
balance. Two requests that arrive together read the same count and the same figure, and
`api.create_bench` writes its row as `Draft` for the two minutes a deploy takes, so an in-flight
deploy is invisible to whatever is counting deploys.

So a slot is a row, and the credits it will spend are held on that row. `Bench Admission`
autonames on the bench, which puts the claim on a primary key, and every read and write happens
under `SELECT ... FOR UPDATE` on the caller's `Credit Account` - the one row every contender for
that caller has to take. The loser waits there and then reads what the winner wrote.

A hold is **not** a charge. It moves no balance, writes no `Credit Ledger Entry` and appears in
no statement; the row and its `held_credits` are the whole record that a hold exists. The charge
is `metering.on_bench_running`, which ends the hold in the same locked transaction that debits
the lease.

The lock order is fixed everywhere in this app: `Bench Instance`, then `Credit Account`, then
`Bench Admission`. Nothing here locks an instance, so admission cannot close that cycle. There
is deliberately no locking count over `tabBench Instance`: it has no index on `owner`, so the
count would walk the `status` index and next-key-lock other tenants' rows.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from benchpress.credits import account, config

ADMISSION = "Bench Admission"

# Stable identifier for the instance-count refusal, independent of the human-readable
# message below. A future decision-envelope record should cite this, not the message
# string, so a wording change to the throw never reads as a different rule in an audit.
# Semantic revision suffix: bump to _v2 if the predicate itself ever changes.
RULE_ID_INSTANCE_COUNT_CAP = "instance_count_cap_v1"

DENIAL = "Admission Denial"


def claim(user: str, bench_name: str | None, limit: int, cost: float = 0.0) -> bool:
	"""Take a slot and hold `cost` for `bench_name`, or refuse by name. True when this call took it.

	Returns False without refusing when the bench already holds a slot, which is what makes a
	redeploy, a restart and a retry free: the cap forbids new instances, not touching existing
	ones. Such a call is still priced, because the start it asks for will still be charged.

	Raises `frappe.ValidationError` when the caller is at `limit` (`0` means unlimited), when the
	account is suspended, or when the cost is more than the account can still commit.
	"""
	if not bench_name:
		return False
	acct = account.locked(user)
	# A hold is money, and a site with credits off has none. Normalised here rather than at the
	# call site so no caller can reserve credits that do not exist.
	hold = flt(cost) if config.credits_enabled() else 0.0
	# Also a locking read: this session is REPEATABLE READ, where a plain read after the lock
	# still answers from the snapshot the request opened.
	claimed = frappe.db.get_value(
		ADMISSION, bench_name, ["name", "held_credits"], as_dict=True, for_update=True
	)
	if claimed:
		_require_affordable(acct, hold - flt(claimed.held_credits))
		return False
	if limit and cint(acct.active_instances) >= limit:
		_record_denial(RULE_ID_INSTANCE_COUNT_CAP, limit=limit, count=cint(acct.active_instances))
		frappe.throw(
			_(
				"You have {0} instances running, the most your plan allows. Stop one, or buy credits at {1} to raise the limit."
			).format(limit, config.TOP_UP_ROUTE)
		)
	_require_affordable(acct, hold)
	if not _insert(acct.name, bench_name, hold):
		return False
	acct.active_instances = cint(acct.active_instances) + 1
	acct.reserved_credits = flt(flt(acct.reserved_credits) + hold, account.PRECISION)
	account.save_account(acct)
	return True


def _record_denial(rule_id: str, limit: int, count: int) -> None:
	"""Write the decision envelope BEFORE the throw that cites it.

	Minimal shape agreed with umiXBT on Moltbook (post `5a411cda-...`, comment `c3c9bd93`):
	a stable rule id (not the human-readable message, which can be reworded), the redacted
	inputs the refusal was judged against (`limit`/`count`, both already computed locally,
	no new lookup), and a correlation id -- reused from the request's own `X-Frappe-Request-Id`
	header when the caller sent one, so this row joins to the request that triggered it rather
	than minting an identity nobody outside this function will ever see again.

	Committed explicitly right after the insert: `frappe.throw()` runs immediately after this
	call returns, and the request's own error handler rolls back the transaction the throw's
	exception unwinds through -- a row written in that same transaction and never committed
	would vanish with it, which defeats the entire point of recording the refusal.

	Safe to commit here specifically because this is the LAST thing `claim()` does on the
	refusal path -- the `SELECT ... FOR UPDATE` on the caller's `Credit Account` has already
	done its only job (deciding the refusal) and nothing after this call still needs that lock
	held. A commit inside any other locked section of this module would release the lock
	early and reopen the race the lock exists to close; this one does not, because there is no
	"after" on this path.
	"""
	correlation_id = None
	try:
		correlation_id = frappe.request.headers.get("X-Frappe-Request-Id")
	except Exception:
		correlation_id = None
	frappe.get_doc(
		{
			"doctype": DENIAL,
			"correlation_id": correlation_id or frappe.generate_hash(length=16),
			"rule_id": rule_id,
			"denied_at": now_datetime(),
			"limit": limit,
			"count": count,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- must survive the throw's own rollback, see docstring


def release(bench_name: str | None) -> None:
	"""Give a slot and its hold back. Idempotent: a bench holding none releases nothing and says nothing."""
	if not bench_name:
		return
	user = frappe.db.get_value(ADMISSION, bench_name, "account")
	if not user:
		return
	acct = account.locked(user)
	held = frappe.db.get_value(ADMISSION, bench_name, "held_credits", as_dict=True, for_update=True)
	if not held:
		return
	frappe.delete_doc(ADMISSION, bench_name, force=True, ignore_permissions=True)
	acct.active_instances = _decremented(acct)
	acct.reserved_credits = _unreserved(acct, held.held_credits)
	account.save_account(acct)


def release_hold(bench_name: str | None) -> float:
	"""End the reservation a start made, keeping the slot. Returns what came back.

	Called beside the charge the hold was taken for, so the two land under one lock: the credits
	stop being reserved at the moment they are spent. Free on a bench holding nothing, which is
	every renewal and every start already inside a window somebody paid for.
	"""
	if not bench_name:
		return 0.0
	user = frappe.db.get_value(ADMISSION, bench_name, "account")
	if not user:
		return 0.0
	acct = account.locked(user)
	row = frappe.db.get_value(ADMISSION, bench_name, "held_credits", as_dict=True, for_update=True)
	held = flt(row.held_credits) if row else 0.0
	if not held:
		return 0.0
	# A billing flag, not a user edit — the same discipline `lease._write` keeps.
	frappe.db.set_value(ADMISSION, bench_name, "held_credits", 0.0, update_modified=False)
	acct.reserved_credits = _unreserved(acct, held)
	account.save_account(acct)
	return held


def _require_affordable(acct, cost: float) -> None:
	"""Refuse a caller who cannot commit `cost` on top of what they have already reserved.

	`cost` is what this call adds, so a bench that already holds part of it is judged on the
	difference. Nothing to decide on a site with credits off: there is no money there.
	"""
	if not config.credits_enabled():
		return
	if acct.is_suspended:
		frappe.throw(_("This account is suspended, so nothing new can be started."))
	spendable = account.spendable(acct)
	if flt(cost) > spendable:
		frappe.throw(account.shortfall_message(flt(cost), spendable))


def _insert(account_name: str, bench_name: str, cost: float) -> bool:
	row = frappe.new_doc(ADMISSION)
	row.bench = bench_name
	row.account = account_name
	row.claimed_at = now_datetime()
	row.held_credits = cost
	try:
		row.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Unreachable under the account lock. It is what keeps this correct if a later change
		# drops the lock, and the message would otherwise reach the user as a second sentence.
		frappe.clear_last_message()
		return False
	return True


def _decremented(acct) -> int:
	remaining = cint(acct.active_instances) - 1
	if remaining < 0:
		# Never throw on a release path: this is reached from teardown and from stop, and the
		# reconciler heals the counter from the rows within one tick.
		frappe.logger("benchpress").warning(f"admission: {acct.name} released a slot it did not hold")
		return 0
	return remaining


def _unreserved(acct, held) -> float:
	remaining = flt(flt(acct.reserved_credits) - flt(held), account.PRECISION)
	if remaining < 0:
		frappe.logger("benchpress").warning(f"admission: {acct.name} returned a hold it did not have")
		return 0.0
	return remaining
