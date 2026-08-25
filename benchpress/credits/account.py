# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One-off debits and credits — the accounting core.

Every entry point here moves a stored balance by a stated amount and appends one row saying so.
There is no meter, no accrual term and nothing that changes with the clock: a balance is what it
says, and the live check is a read rather than an aggregate. Time is sold by
`benchpress.credits.lease`, which buys a fixed window through `charge` and knows nothing about
how a balance is kept.

Every mutation runs under `for_update` on the account row, and that lock is the double-spend
guard: two parallel deploys cannot both read the same balance.

`credits_enabled()` is checked once at the top of each public function, never at the call sites,
so a self-hoster with the switch off gets no accounts, no ledger rows and no extra queries.

Nothing here calls Docker, and nothing sums the ledger to derive a balance.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from benchpress.credits import config

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"

# Matches the `precision` on both doctypes: a price multiplier can put a lease at 7.333333
# credits, and rounding that to two places at every debit would leak the difference.
PRECISION = 6

BALANCE_FIELDS = ["balance", "is_suspended", "reserved_credits"]
# The hot path reads only what it must; the meter also needs the denominator, so it asks for one
# field more in the same single read rather than making the guard carry it.
SUMMARY_FIELDS = [*BALANCE_FIELDS, "lifetime_spent"]
STATEMENT_FIELDS = ["name", "entry_type", "credits", "balance_after", "description", "creation"]
DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 100

SIGNUP_REFERENCE = "User"

USAGE = "Usage"
GRANT = "Grant"
PURCHASE = "Purchase"
REFUND = "Refund"
ADJUSTMENT = "Adjustment"


# --- Reads: O(1), and never a write ------------------------------------------


def available(account) -> float:
	"""The spendable balance. One stored number, so no scan and no SUM over the ledger.

	Takes anything carrying `balance` — a document, or the dict a single indexed read returns —
	so the hot path never has to build a document.
	"""
	return flt(flt(account.balance), PRECISION)


def spendable(account) -> float:
	"""What a new commitment may take: the balance less what admission is already holding.

	Never what the sweep asks — that is `available`, and a hold must not read as running out.
	It deliberately does not settle anything: an admission is a question, and a question that
	wrote a ledger row would put a Usage line in the statement for merely asking.
	"""
	return flt(available(account) - flt(account.reserved_credits), PRECISION)


def shortfall_message(needed, available) -> str:
	"""Refuse by name: what this costs, what is left, the gap, and the way out of it."""
	return _("Not enough credits: this needs {0} and {1} are available — {2} short. Top up at {3}.").format(
		flt(needed, 2), flt(available, 2), flt(needed - available, 2), config.TOP_UP_ROUTE
	)


def allocated(account) -> float:
	"""Every credit ever put into this account: what is left, plus what has gone.

	Still not a ledger sum — the two stored figures carry it between them, so the meter's
	denominator costs the same single read as its numerator. It holds still as credits are spent
	and `available` falls beneath it, which is what a gauge wants: a fixed denominator and a
	falling fill.

	A refund or a negative adjustment lowers it, because those credits were taken back — allocated
	is what the account has to spend, not what it was ever handed.
	"""
	return flt(flt(account.balance) + flt(account.lifetime_spent), PRECISION)


def summary(user: str) -> dict:
	"""What the balance meter renders: one indexed read plus arithmetic.

	A read never opens an account — a user who has done nothing has no row, and reporting zero is
	cheaper and more honest than writing one to find out.
	"""
	if not config.credits_enabled():
		return {"enabled": False}
	row = frappe.db.get_value(ACCOUNT, user, SUMMARY_FIELDS, as_dict=True)
	if not row:
		return {"enabled": True, "balance": 0.0, "allocated": 0.0, "reserved": 0.0, "is_suspended": False}
	return {
		"enabled": True,
		"balance": available(row),
		"allocated": allocated(row),
		"reserved": flt(row.reserved_credits, PRECISION),
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


# --- Balance changes ---------------------------------------------------------


def charge(user: str, credits, description: str, reference=None, request_id: str | None = None) -> None:
	"""Debit one event — a lease window, or a custom image build. One row.

	A charge of zero still writes its row. The ledger is the record that the event happened, and
	the daily custom-build cap counts those rows — so an operator who sets `custom_build_credits`
	to zero makes builds free without also making them uncountable.
	"""
	if not config.credits_enabled():
		return
	account = locked(user)
	account.balance = flt(flt(account.balance) - flt(credits), PRECISION)
	account.lifetime_spent = flt(flt(account.lifetime_spent) + flt(credits), PRECISION)
	save_account(account)
	_write_entry(account, USAGE, -flt(credits), description, reference, request_id)


def grant(user: str, credits, description: str, reference=None) -> None:
	"""Credit an account without a payment: the signup grant, or an operator's goodwill.

	`reference` is what makes a grant postable exactly once. `_post_signup_grant` passes the
	user, so the ledger itself remembers that the joining credits have landed.
	"""
	if not config.credits_enabled() or not flt(credits):
		return
	_apply_grant(locked(user), credits, description, reference)


def _apply_grant(account, credits, description: str, reference) -> None:
	account.balance = flt(flt(account.balance) + flt(credits), PRECISION)
	# The balance just rose, so the next depletion deserves its own warning.
	account.low_balance_warned = 0
	save_account(account)
	_write_entry(account, GRANT, flt(credits), description, reference)


def purchase(user: str, credits, description: str, reference) -> bool:
	"""Credit a paid top-up **exactly once**, and say whether this call was the one that did it.

	Webhooks retry, `on_update` fires on every save of an order, and an operator pressing *Sync
	Status* is a third delivery of the same payment — so the reference, not the caller, decides
	whether money has already been applied. The check runs *after* `locked`, under the same row
	lock that applies it: two deliveries racing each other serialise there instead of both reading
	an empty ledger and both crediting.

	Returning the decision rather than swallowing it lets the caller hang its own side effects — a
	realtime nudge — off the same once-ever answer.
	"""
	if not config.credits_enabled():
		return False
	account = locked(user)
	if reference_posted(reference):
		return False
	amount = flt(credits)
	account.balance = flt(flt(account.balance) + amount, PRECISION)
	account.lifetime_purchased = flt(flt(account.lifetime_purchased) + amount, PRECISION)
	account.low_balance_warned = 0
	save_account(account)
	_write_entry(account, PURCHASE, amount, description, reference)
	return True


def refund(user: str, credits, description: str, reference=None) -> None:
	"""Give credits back as a negative row of its own.

	Never by rewriting the purchase: the ledger is append-only, so a refund is an event that
	happened later and reads as one. Refunding also un-counts the purchase, because
	`lifetime_purchased` is what the low-balance threshold measures against and what tells a paid
	account from a free one.
	"""
	if not config.credits_enabled():
		return
	amount = abs(flt(credits))
	account = locked(user)
	account.balance = flt(flt(account.balance) - amount, PRECISION)
	account.lifetime_purchased = max(flt(flt(account.lifetime_purchased) - amount, PRECISION), 0.0)
	save_account(account)
	_write_entry(account, REFUND, -amount, description, reference)


def adjust(user: str, credits, reason: str) -> None:
	"""An operator's correction, in either direction, and never without a reason.

	The reason is the entire value of the row: an adjustment is the one entry type no rule
	produced, so a year later it is the only record of why a balance is what it is.
	"""
	if not config.credits_enabled():
		frappe.throw(_("Credits are switched off on this site."))
	if not cstr(reason).strip():
		frappe.throw(_("An adjustment needs a reason."))
	account = locked(user)
	account.balance = flt(flt(account.balance) + flt(credits), PRECISION)
	account.low_balance_warned = 0
	save_account(account)
	_write_entry(account, ADJUSTMENT, flt(credits), reason)


def lock(user: str) -> None:
	"""Serialise this transaction against every other purchase on one account.

	Taken before the guards and the replay check that decide from the account, and before
	`request_posted` in particular: that check locks a gap this account's ledger row is then
	inserted into, so two renewals reaching the gap ahead of the account row deadlock on the way
	back — one holding the gap and waiting for the account, the other the reverse.

	The account is not opened here. One that does not exist has posted nothing, and opening it
	would post the signup grant as a side effect of a purchase that may still be refused.
	"""
	if frappe.db.exists(ACCOUNT, user):
		frappe.db.get_value(ACCOUNT, user, "name", for_update=True)


def request_posted(user: str, request_id: str) -> bool:
	"""Whether this account has already written a row for this client request id. A **locking** read.

	`reference_posted` can be a plain lookup because the reference it guards is created by an
	outside system. A request id is created by a browser that may be firing three of them at
	once, and this session is REPEATABLE READ — a plain read would answer from the snapshot the
	transaction opened, which predates the racing click, and charge it twice. A locking read sees
	the latest commit. `reference_name` cannot carry the key instead: it is a Dynamic Link, and a
	synthetic name fails validation.

	Scoped to the account, on the `(account, request_id)` index. Matched across the whole ledger
	the key would be one namespace shared by every tenant, and the gap the locking read takes
	would span every tenant's rows rather than this one's.
	"""
	return bool(
		frappe.db.get_value(LEDGER, {"account": user, "request_id": request_id}, "name", for_update=True)
	)


def reference_posted(reference) -> bool:
	"""Whether this reference has already been written to the ledger. One indexed lookup.

	The index behind it is `(reference_doctype, reference_name)`, added by
	`benchpress.credits.seed.ensure_ledger_index` — without it this is a table scan on the one
	table that grows forever.
	"""
	doctype, name = reference
	return bool(frappe.db.exists(LEDGER, {"reference_doctype": doctype, "reference_name": name}))


# --- The account row --------------------------------------------------------


def ensure_account(user: str) -> str:
	"""The account name for a user, the email itself, created on first use.

	The signup grant is posted here rather than on user creation so it lands however the user
	arrived: waitlist invite, Desk, or a social login. It is posted on every call rather than
	only on the create, because admission opens accounts on a site with credits switched off and
	those rows would otherwise never be granted when an operator flips the switch.
	"""
	if not frappe.db.exists(ACCOUNT, user):
		_create_account(user)
	_post_signup_grant(user)
	return user


def _post_signup_grant(user: str) -> None:
	"""Post the joining credits once ever, keyed by the user in the ledger.

	An account opened before this reference existed carries its grant as an unreferenced row, so
	any ledger row at all counts as onboarded: without that, flipping the switch would grant a
	second time to everybody who was already trading.
	"""
	if not config.credits_enabled() or reference_posted((SIGNUP_REFERENCE, user)):
		return
	credits = flt(config.settings().signup_grant_credits)
	if not credits or frappe.db.exists(LEDGER, {"account": user}):
		return
	# Not through `grant`: that would re-enter `ensure_account`, which is what called this.
	account = frappe.get_doc(ACCOUNT, user, for_update=True)
	_apply_grant(account, credits, "Signup grant", (SIGNUP_REFERENCE, user))


def _create_account(user: str) -> str:
	account = frappe.new_doc(ACCOUNT)
	account.user = user
	try:
		account.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		frappe.clear_last_message()  # two parallel first deploys; the other one won
	return user


def locked(user: str):
	"""The account row, locked and loaded in one `SELECT ... FOR UPDATE`.

	A second worker touching the same account waits here instead of reading a balance that is
	about to change. Loading the document *is* the lock rather than following it: this session is
	REPEATABLE READ, where a plain read answers from the snapshot the transaction opened — so a
	load after the lock returns the row as it was before the other worker committed, and saving
	that stale `modified` raises `TimestampMismatchError` at whoever asked second.
	"""
	return frappe.get_doc(ACCOUNT, ensure_account(user), for_update=True)


def save_account(account) -> None:
	account.save(ignore_permissions=True)


def _write_entry(
	account, entry_type: str, credits, description: str, reference=None, request_id: str | None = None
) -> None:
	"""Append one audit row. `balance_after` is stored so no screen ever sums this table."""
	entry = frappe.new_doc(LEDGER)
	# The document refuses rows nobody's accounting produced; this is what marks ours. See
	# `CreditLedgerEntry.before_insert` for why a hand-written row is worse than no row.
	entry.flags.from_engine = True
	entry.account = account.name
	entry.entry_type = entry_type
	entry.credits = flt(credits, PRECISION)
	entry.balance_after = flt(account.balance, PRECISION)
	entry.description = description
	if reference:
		entry.reference_doctype, entry.reference_name = reference
	entry.request_id = request_id
	entry.insert(ignore_permissions=True)
