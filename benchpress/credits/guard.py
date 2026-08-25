# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The gate: one decorator that can refuse an action before any work is queued.

Everything refusable goes through `requires_admission`, so there is exactly one place that
decides what "cannot afford" and "too many" mean, and exactly one shape of refusal.

The concurrency cap is not here, and neither is the balance an instance is judged against. Both
are a claim now rather than a count and a comparison, taken by `benchpress.credits.admission`
against a row it inserts under one lock; what survives here is the numbers that claim is judged
against and the functions that price a call.

Two rules the refusals obey:

- **Never a bare `PermissionError`.** Every throw names the number that was hit and what to do
  next — top up, stop an instance, pick a larger size. A user who is refused without being told
  why has been given a bug, not a limit.
- **`0` means unlimited.** Every cap reads its `Credit Settings` field and returns early on zero,
  so an operator disables a cap by clearing it rather than by editing code.

Ordering inside the claim is deliberate: the cap is decided before the credits, so a caller who
is both at their cap and short is told about the cap, fixes it, and then learns about the
shortfall — two sentences, both actionable.

Costs are **holds, not debits**. Nothing here writes to a balance; `metering` still owns every
charge. What a start must prove is the price of one lease — the number the size picker quoted
and the number the deploy is about to spend — and admission reserves it until that deploy
spends it.
"""

import functools
import inspect

import frappe
from frappe import _
from frappe.utils import cint, flt, today

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, admission, config, lease
from benchpress.permissions import has_app_permission

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
LEDGER = "Credit Ledger Entry"
SITE = "Bench Site"


def requires_admission(cost=None, caps=()):
	"""Refuse what the caller cannot pay for, or already has too many of.

	`cost` and each entry in `caps` are called with the wrapped call's arguments by name, so they
	read `data=` or `self=` rather than indexing a tuple. With the switch off only the slot claim
	runs, and on a call about no instance that is nothing at all.

	A caller without an app role is passed straight through to the endpoint's own guard. The gate
	must never be the first thing a Guest meets: it would answer a permission question with an
	accounting sentence, and `ensure_account` would open a `Credit Account` for a caller who was
	about to be refused anyway.
	"""

	def decorator(method):
		@functools.wraps(method)
		def wrapper(*args, **kwargs):
			if has_app_permission():
				_enforce(method, cost, caps, args, kwargs)
			return method(*args, **kwargs)

		return wrapper

	return decorator


def _enforce(method, cost, caps, args, kwargs) -> None:
	"""Claim the slot and the credits together, then the caps that are about something else.

	The claim runs whatever the switch says, because concurrency is capacity rather than
	economics and `0` is already the operator's way of turning it off. The hold inside it is
	money, and money does not exist on a site with credits off — which is also why the price is
	not even computed there.

	The cap and the hold are one decision under one lock, so a caller at neither limit cannot be
	admitted twice by two requests that read the same figures.
	"""
	arguments = _arguments_by_name(method, args, kwargs)
	subject = _subject_instance(**arguments)
	needed = flt(cost(**arguments)) if cost and config.credits_enabled() else 0.0
	admission.claim(frappe.session.user, subject, concurrency_limit(), needed)
	if not config.credits_enabled():
		return
	for cap in caps:
		cap(**arguments)
	if needed and not subject:
		# A custom image build holds no slot, so nothing held its price either: it stays a check.
		require_balance(frappe.session.user, needed)


def _arguments_by_name(method, args, kwargs) -> dict:
	"""The call's arguments keyed by parameter name, however the caller passed them."""
	bound = inspect.signature(method).bind(*args, **kwargs)
	bound.apply_defaults()
	return bound.arguments


# --- What an action must be able to afford ------------------------------------


def instance_lease_cost(**call) -> float:
	"""One lease on this instance's lab, for a call that was handed the document itself."""
	return lab_lease_cost(_called_on(call).lab)


def payload_lease_cost(**call) -> float:
	"""The same price for `api.create_bench`, whose lab arrives inside the JSON payload."""
	return lab_lease_cost(frappe.parse_json(call.get("data")).get("lab"))


def lab_lease_cost(lab_name) -> float:
	"""What one window on this lab costs — what the start is about to spend, not a rate."""
	if not lab_name:
		return 0.0
	lab = frappe.get_cached_doc("Lab", lab_name)
	plan = lease.plan_for(lab)
	return lease.cost_of(lab, plan) if plan else 0.0


def build_charge(**call) -> float:
	"""A custom image build is a flat fee, so the check is the fee itself."""
	return flt(config.settings().custom_build_credits)


# --- The caps: one indexed count each, never a fetch-and-len -----------------


def cap_sites_per_instance(**call) -> None:
	"""`Instance Size.max_sites` for the size the instance's lab deploys at."""
	bench_name = frappe.parse_json(call.get("data")).get("bench")
	limit = _site_limit(bench_name)
	if not limit:
		return
	if frappe.db.count(SITE, {"bench": bench_name}) >= limit:
		frappe.throw(
			_(
				"This instance already has the {0} sites its size allows. Deploy the lab at a larger size, or ask an admin to remove this instance."
			).format(limit)
		)


def cap_devices(**call) -> None:
	from benchpress.vpn_adapter import count_devices

	limit = cint(config.settings().max_devices)
	if not limit:
		return
	if count_devices() >= limit:
		frappe.throw(
			_("You already have {0} devices, the most allowed. Remove one before adding another.").format(
				limit
			)
		)


def cap_builds_per_day(**call) -> None:
	"""Custom builds since midnight, counted from the rows the builds themselves write.

	Only the explicit build action carries this cap. A build the *deploy* path performs is a cache
	miss the user did not ask for, and its credit charge is the control there — asking Docker
	whether a tag exists would put a socket round trip in front of every deploy request, which is
	exactly the coupling the enforcement sweep is kept free of.
	"""
	limit = cint(config.settings().max_builds_per_day)
	if not limit:
		return
	built = frappe.db.count(
		LEDGER,
		{"account": frappe.session.user, "reference_doctype": "Lab", "creation": (">=", today())},
	)
	if built >= limit:
		frappe.throw(
			_(
				"You have used today's {0} custom image builds. Deploying a lab whose recipe somebody has already built needs no build at all."
			).format(limit)
		)


def _subject_instance(**call) -> str | None:
	"""The instance this call is about — the document itself, or the one its payload names.

	`None` for a call that is about no instance at all, such as a device or an image build, and
	`admission.claim` treats that as nothing to claim.
	"""
	bench = _called_on(call)
	if bench is not None:
		return bench.name
	data = call.get("data")
	lab_name = frappe.parse_json(data).get("lab") if data else None
	return get_instance_id(frappe.session.user, lab_name) if lab_name else None


def _called_on(call):
	"""The `Bench Instance` document this call carries, whether as a method's `self` or an argument."""
	return call.get("self") or call.get("bench")


def concurrency_limit() -> int:
	"""How many instances this caller may hold at once. `0` means unlimited.

	"Has paid" is the existence of a Purchase row, not a `lifetime_purchased` balance: a refund
	clears the float, and somebody who bought and was refunded has still plainly paid.

	With credits off there are no plans to read, so the cap is its own setting. It defaults to
	`0`, which is what keeps an install that has never opted in behaving as it did.
	"""
	if not config.credits_enabled():
		return cint(config.settings().max_concurrent_uncredited)
	settings = config.settings()
	paid = frappe.db.exists(LEDGER, {"account": frappe.session.user, "entry_type": account.PURCHASE})
	return cint(settings.max_concurrent_paid if paid else settings.max_concurrent_free)


def _site_limit(bench_name) -> int:
	if not bench_name:
		return 0
	lab_name = frappe.db.get_value(BENCH, bench_name, "lab")
	if not lab_name:
		return 0
	size = config.size_for_lab(frappe.get_cached_doc("Lab", lab_name))
	return cint(size.max_sites) if size else 0


# --- The balance check -------------------------------------------------------


def require_balance(user: str, needed) -> None:
	"""Refuse by name, naming the shortfall and the route out of it.

	What a caller may spend is `spendable` rather than `available`: credits an admitted deploy is
	already holding are committed, and a renewal that spent them would overdraw the account the
	moment that deploy reaches `Running`.

	Takes the user rather than reading the session: a renewal is charged to the bench's owner,
	who is not always whoever pressed the button.
	"""
	row = _account_row(user)
	if row.is_suspended:
		frappe.throw(_("This account is suspended, so nothing new can be started."))
	spendable = account.spendable(row)
	if flt(needed) > spendable:
		frappe.throw(account.shortfall_message(flt(needed), spendable))


def _account_row(user: str):
	"""One user's balance fields, read under the lock the charge takes.

	`ensure_account` posts the signup grant, and a brand-new user whose grant has not landed yet
	would otherwise be refused the very first deploy they ever ask for.

	The read locks because the guard decides whether to debit and must see the row the debit will
	write: this session is REPEATABLE READ, where a plain read answers from the snapshot the
	transaction opened — before a racing purchase on the same account committed.
	"""
	name = account.ensure_account(user)
	return frappe.db.get_value(ACCOUNT, name, account.BALANCE_FIELDS, as_dict=True, for_update=True)
