# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Admission: the concurrency decision, taken as a write that can fail.

Counting running instances and comparing cannot refuse anything. Two requests that arrive
together read the same count, and `api.create_bench` writes its row as `Draft` for the two
minutes a deploy takes, so an in-flight deploy is invisible to whatever is counting deploys.

So a slot is a row. `Bench Admission` autonames on the bench, which puts the claim on a primary
key, and both the read and the write happen under `SELECT ... FOR UPDATE` on the caller's
`Credit Account` - the one row every contender for that caller has to take. The loser waits
there and then reads the count the winner wrote.

The lock order is fixed everywhere in this app: `Bench Instance`, then `Credit Account`, then
`Bench Admission`. Nothing here locks an instance, so admission cannot close that cycle. There
is deliberately no locking count over `tabBench Instance`: it has no index on `owner`, so the
count would walk the `status` index and next-key-lock other tenants' rows.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from benchpress.credits import account, config

ADMISSION = "Bench Admission"


def claim(user: str, bench_name: str | None, limit: int) -> bool:
	"""Take a slot for `bench_name`, or refuse by name. True when this call took it.

	Returns False without refusing when the bench already holds a slot, which is what makes a
	redeploy, a restart and a retry free: the cap forbids new instances, not touching existing
	ones. Raises `frappe.ValidationError` when the caller is at `limit`; `0` means unlimited.
	"""
	if not bench_name:
		return False
	acct = account.locked(user)
	# Also a locking read: this session is REPEATABLE READ, where a plain read after the lock
	# still answers from the snapshot the request opened.
	if frappe.db.get_value(ADMISSION, bench_name, "name", for_update=True):
		return False
	if limit and cint(acct.active_instances) >= limit:
		frappe.throw(
			_(
				"You have {0} instances running, the most your plan allows. Stop one, or buy credits at {1} to raise the limit."
			).format(limit, config.TOP_UP_ROUTE)
		)
	if not _insert(acct.name, bench_name):
		return False
	acct.active_instances = cint(acct.active_instances) + 1
	account.save_account(acct)
	return True


def release(bench_name: str | None) -> None:
	"""Give a slot back. Idempotent: a bench holding none releases nothing and says nothing."""
	if not bench_name:
		return
	user = frappe.db.get_value(ADMISSION, bench_name, "account")
	if not user:
		return
	acct = account.locked(user)
	if not frappe.db.get_value(ADMISSION, bench_name, "name", for_update=True):
		return
	frappe.delete_doc(ADMISSION, bench_name, force=True, ignore_permissions=True)
	acct.active_instances = _decremented(acct)
	account.save_account(acct)


def _insert(account_name: str, bench_name: str) -> bool:
	row = frappe.new_doc(ADMISSION)
	row.bench = bench_name
	row.account = account_name
	row.claimed_at = now_datetime()
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
