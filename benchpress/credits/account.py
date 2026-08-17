# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Transitions, not ticks — the accounting core.

A running instance is billed by recording the *changes* to its user's burn rate, not by writing a
row every minute. One row per state change, two per session. At 1,000 instances per-minute rows
would be ~43M a year; transitions are ~60k for identical information at identical accuracy, and
the hot-path balance check becomes arithmetic instead of an aggregate:

    available = balance - burn_rate * (now - burn_since)

`balance` is therefore the *settled* balance, and every transition settles first: it folds the
accrued burn in, writes what it folded to the ledger, and only then changes `burn_rate`. Because
the settle and the rate change happen under `for_update` on one row, two parallel deploys cannot
both read the same balance — that lock is the double-spend guard.

`credits_enabled()` is checked once at the top of each public function, never at the call sites,
so a self-hoster with the switch off gets no accounts, no ledger rows and no extra queries.

Nothing here calls Docker, and nothing sums the ledger to derive a balance.
"""

import frappe
from frappe.utils import cint, flt, now_datetime, time_diff_in_hours

from benchpress.credits import config

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"

# Matches the `precision` on both doctypes: a minute of a 1 credit/hour instance is 0.0167
# credits, and rounding that to two places at every settle would leak the difference.
PRECISION = 6

BALANCE_FIELDS = ["balance", "burn_rate", "burn_since", "is_suspended"]
STATEMENT_FIELDS = ["name", "entry_type", "credits", "balance_after", "description", "creation"]
DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 100

USAGE = "Usage"
GRANT = "Grant"


# --- Reads: O(1), and never a write ------------------------------------------


def available(account) -> float:
	"""Live balance in O(1). No scan, no SUM over the ledger.

	Takes anything with the three balance fields — a document, or the dict a single indexed read
	returns — so the hot path never has to build a document.
	"""
	return flt(flt(account.balance) - accrued(account), PRECISION)


def accrued(account) -> float:
	"""Credits burnt since the rate last changed, and not yet folded into `balance`."""
	if not account.burn_since or not flt(account.burn_rate):
		return 0.0
	hours = max(time_diff_in_hours(now_datetime(), account.burn_since), 0.0)
	return flt(flt(account.burn_rate) * hours, PRECISION)


def summary(user: str) -> dict:
	"""What the balance chip renders: one indexed read plus arithmetic.

	A read never opens an account — a user who has done nothing has no row, and reporting zero is
	cheaper and more honest than writing one to find out.
	"""
	if not config.credits_enabled():
		return {"enabled": False}
	row = frappe.db.get_value(ACCOUNT, user, BALANCE_FIELDS, as_dict=True)
	if not row:
		return {"enabled": True, "balance": 0.0, "burn_rate": 0.0, "is_suspended": False}
	return {
		"enabled": True,
		"balance": available(row),
		"burn_rate": flt(row.burn_rate),
		"is_suspended": bool(row.is_suspended),
	}


def statement(user: str, limit_start=0, limit_page_length=DEFAULT_PAGE_LENGTH) -> dict:
	"""One page of the ledger, newest first, on the `(account, creation)` index."""
	if not config.credits_enabled():
		return {"enabled": False, "rows": [], "total": 0, "summary": {"enabled": False}}
	page_length = min(max(cint(limit_page_length), 1), MAX_PAGE_LENGTH)
	filters = {"account": user}
	return {
		"enabled": True,
		"rows": frappe.get_all(
			LEDGER,
			filters=filters,
			fields=STATEMENT_FIELDS,
			order_by="creation desc",
			limit_start=cint(limit_start),
			limit_page_length=page_length,
		),
		"total": frappe.db.count(LEDGER, filters),
		"summary": summary(user),
	}


# --- Transitions: each one settles, under a row lock -------------------------


def start_burn(user: str, bench_name: str, rate_per_hour, label: str | None = None) -> None:
	"""Row-lock, settle, raise `burn_rate`, write one Usage-start row.

	`label` is what the statement calls the instance. `bench_name` is `md5(user + lab)` — a stable
	key, and unreadable — so the row links to it but describes itself by the lab, the same way
	every other surface names a bench.
	"""
	if not config.credits_enabled():
		return
	account = _locked(user)
	charged = settle(account)
	account.burn_rate = flt(flt(account.burn_rate) + flt(rate_per_hour), PRECISION)
	_save(account)
	_write_entry(
		account,
		USAGE,
		-charged,
		f"Started {label or bench_name} at {flt(rate_per_hour)} credits/hour",
		("Bench Instance", bench_name),
	)


def stop_burn(user: str, bench_name: str, rate_per_hour, label: str | None = None) -> None:
	"""Row-lock, settle (this is where the session is charged), lower `burn_rate`.

	The rate to withdraw is passed in rather than re-derived: the size the instance started on is
	what it must be billed at, even if an operator retuned that size while it ran.
	"""
	if not config.credits_enabled():
		return
	account = _locked(user)
	charged = settle(account)
	account.burn_rate = max(flt(flt(account.burn_rate) - flt(rate_per_hour), PRECISION), 0.0)
	_save(account)
	_write_entry(
		account,
		USAGE,
		-charged,
		f"Stopped {label or bench_name}",
		("Bench Instance", bench_name),
	)


def settle(account) -> float:
	"""Fold accrued burn into the stored balance. Caller holds the row lock.

	Returns what it folded, which is what the caller records in the ledger — so the signed sum of
	an account's entries stays exactly its settled balance. Idempotent: a second call in the same
	instant finds nothing left to accrue.
	"""
	charged = accrued(account)
	account.balance = flt(flt(account.balance) - charged, PRECISION)
	account.lifetime_spent = flt(flt(account.lifetime_spent) + charged, PRECISION)
	account.burn_since = now_datetime()
	return charged


def correct_burn_rate(user: str, rate_per_hour) -> float:
	"""Settle at the rate believed so far, then adopt the reconciled one.

	The daily sweep's repair path: a container that died without a `stop_burn` leaves a rate that
	no running instance justifies, and everything already accrued at it is still owed.
	"""
	if not config.credits_enabled():
		return 0.0
	account = _locked(user)
	charged = settle(account)
	previous = flt(account.burn_rate)
	account.burn_rate = flt(rate_per_hour, PRECISION)
	_save(account)
	_write_entry(
		account,
		USAGE,
		-charged,
		f"Reconciled burn rate {previous} -> {flt(rate_per_hour)} credits/hour",
	)
	return charged


# --- Balance changes that leave the burn rate alone --------------------------


def charge(user: str, credits, description: str, reference=None) -> None:
	"""Debit a one-off event — a custom image build. One row, no settle.

	The accrual term is untouched by this, so there is nothing to settle: subtracting from
	`balance` is exactly a debit of the live balance.

	A charge of zero still writes its row. The ledger is the record that the event happened, and
	the daily custom-build cap counts those rows — so an operator who sets `custom_build_credits`
	to zero makes builds free without also making them uncountable.
	"""
	if not config.credits_enabled():
		return
	account = _locked(user)
	account.balance = flt(flt(account.balance) - flt(credits), PRECISION)
	account.lifetime_spent = flt(flt(account.lifetime_spent) + flt(credits), PRECISION)
	_save(account)
	_write_entry(account, USAGE, -flt(credits), description, reference)


def grant(user: str, credits, description: str) -> None:
	"""Credit an account without a payment — the signup grant, or an operator's goodwill."""
	if not config.credits_enabled() or not flt(credits):
		return
	account = _locked(user)
	account.balance = flt(flt(account.balance) + flt(credits), PRECISION)
	# The balance just rose, so the next depletion deserves its own warning.
	account.low_balance_warned = 0
	_save(account)
	_write_entry(account, GRANT, flt(credits), description)


# --- The account row --------------------------------------------------------


def ensure_account(user: str) -> str:
	"""The account name for a user — the email itself — created on first use.

	The signup grant is posted here rather than on user creation so it lands however the user
	arrived: waitlist invite, Desk, or a phase-7 social login.
	"""
	if frappe.db.exists(ACCOUNT, user):
		return user
	return _create_account(user)


def _create_account(user: str) -> str:
	account = frappe.new_doc(ACCOUNT)
	account.user = user
	account.burn_since = now_datetime()
	try:
		account.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		return user  # two parallel first deploys; the other one won
	grant(user, config.settings().signup_grant_credits, "Signup grant")
	return account.name


def _locked(user: str):
	"""The account row, locked for the rest of this transaction.

	`for_update=True` issues `SELECT ... FOR UPDATE`, so a second worker settling the same account
	waits here instead of reading a balance that is about to change. No raw SQL: the ORM does row
	locking natively.
	"""
	name = ensure_account(user)
	frappe.db.get_value(ACCOUNT, name, "name", for_update=True)
	return frappe.get_doc(ACCOUNT, name)


def _save(account) -> None:
	account.save(ignore_permissions=True)


def _write_entry(account, entry_type: str, credits, description: str, reference=None) -> None:
	"""Append one audit row. `balance_after` is stored so no screen ever sums this table."""
	entry = frappe.new_doc(LEDGER)
	entry.account = account.name
	entry.entry_type = entry_type
	entry.credits = flt(credits, PRECISION)
	entry.balance_after = flt(account.balance, PRECISION)
	entry.description = description
	if reference:
		entry.reference_doctype, entry.reference_name = reference
	entry.insert(ignore_permissions=True)
