# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The gate: one decorator that can refuse an action before any work is queued.

Phases 1-4 measured; this is where the economics start to say no. Everything refusable goes
through `requires_credits`, so there is exactly one place that decides what "cannot afford" and
"too many" mean, and exactly one shape of refusal.

Two rules the refusals obey:

- **Never a bare `PermissionError`.** Every throw names the number that was hit and what to do
  next — top up, stop an instance, pick a larger size. A user who is refused without being told
  why has been given a bug, not a limit.
- **`0` means unlimited.** Every cap reads its `Credit Settings` field and returns early on zero,
  so an operator disables a cap by clearing it rather than by editing code.

Ordering inside the gate is deliberate: the caps run first because they are plain indexed counts,
and the balance check last because it opens the account (posting the signup grant) as a side
effect. A caller who is both at their cap and short of credits is told about the cap, fixes it,
and then learns about the shortfall — two sentences, both actionable.

Costs are **checks, not debits**. Nothing here writes to a balance; `metering` still owns every
charge. What a start must prove is one hour of runway at its size rate, because an hourly meter
cannot honestly admit an instance the sweep would stop within the hour.
"""

import functools
import inspect

import frappe
from frappe import _
from frappe.utils import cint, flt, today

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, metering, passes
from benchpress.permissions import has_app_permission

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
LEDGER = "Credit Ledger Entry"
SITE = "Bench Site"

MINIMUM_RUNWAY_HOURS = 1
TOP_UP_ROUTE = config.TOP_UP_ROUTE


def requires_credits(cost=None, caps=()):
	"""Refuse what the caller cannot pay for, or already has too many of.

	`cost` and each entry in `caps` are called with the wrapped call's arguments by name, so they
	read `data=` or `self=` rather than indexing a tuple. With the switch off the wrapper is a
	pass-through and costs not one query.

	A caller without an app role is passed straight through to the endpoint's own guard. The gate
	must never be the first thing a Guest meets: it would answer a permission question with an
	accounting sentence, and `ensure_account` would open a `Credit Account` for a caller who was
	about to be refused anyway.
	"""

	def decorator(method):
		@functools.wraps(method)
		def wrapper(*args, **kwargs):
			if config.credits_enabled() and has_app_permission():
				_enforce(method, cost, caps, args, kwargs)
			return method(*args, **kwargs)

		return wrapper

	return decorator


def _enforce(method, cost, caps, args, kwargs) -> None:
	arguments = _arguments_by_name(method, args, kwargs)
	for cap in caps:
		cap(**arguments)
	if cost:
		_require_runway(cost(**arguments))


def _arguments_by_name(method, args, kwargs) -> dict:
	"""The call's arguments keyed by parameter name, however the caller passed them."""
	bound = inspect.signature(method).bind(*args, **kwargs)
	bound.apply_defaults()
	return bound.arguments


# --- What an action must be able to afford ------------------------------------


def instance_runway(**call) -> float:
	"""One hour at this instance's rate. `self` is the `Bench Instance` the method was called on.

	An unexpired `Always On Pass` is prepaid, so starting that instance costs nothing to prove.
	"""
	bench = call["self"]
	if passes.has_active_pass(bench.name):
		return 0.0
	return lab_runway(bench.lab)


def payload_runway(**call) -> float:
	"""The same runway for `api.create_bench`, whose lab arrives inside the JSON payload."""
	return lab_runway(frappe.parse_json(call.get("data")).get("lab"))


def lab_runway(lab_name) -> float:
	"""One hour at the lab's size rate — the least an hourly meter can honestly admit."""
	if not lab_name:
		return 0.0
	rate = metering.rate_for_lab(frappe.get_cached_doc("Lab", lab_name))
	return flt(rate * MINIMUM_RUNWAY_HOURS)


def build_charge(**call) -> float:
	"""A custom image build is a flat fee, so the check is the fee itself."""
	return flt(config.settings().custom_build_credits)


# --- The caps: one indexed count each, never a fetch-and-len -----------------


def cap_concurrent_instances(**call) -> None:
	"""The caller's running instances, not counting the one this call is about.

	Redeploying one of N running instances still leaves N running, so counting the subject would
	let the cap forbid the very people holding it from touching what they already have.
	"""
	limit = _concurrency_limit()
	if not limit:
		return
	running = frappe.db.count(BENCH, _other_running_instances(**call))
	if running >= limit:
		frappe.throw(
			_(
				"You have {0} instances running, the most your plan allows. Stop one, or buy credits at {1} to raise the limit."
			).format(limit, TOP_UP_ROUTE)
		)


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


def _other_running_instances(**call) -> dict:
	subject = _subject_instance(**call)
	filters = {"owner": frappe.session.user, "status": "Running"}
	if subject:
		filters["name"] = ("!=", subject)
	return filters


def _subject_instance(**call) -> str | None:
	"""The instance this call is about — the document itself, or the one its payload names."""
	bench = call.get("self")
	if bench is not None:
		return bench.name
	lab_name = frappe.parse_json(call.get("data")).get("lab")
	return get_instance_id(frappe.session.user, lab_name) if lab_name else None


def _concurrency_limit() -> int:
	"""The paid ceiling once anything has been bought, the free one until then.

	"Has paid" is the existence of a Purchase row, not a `lifetime_purchased` balance: an Always On
	Pass is money spent on hours rather than credits, so it posts a zero-credit row. Somebody who
	has bought a pass has plainly paid, and a float that stayed at zero would call them free.
	"""
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

	Takes the user rather than reading the session: a renewal is charged to the bench's owner,
	who is not always whoever pressed the button.
	"""
	row = _account_row(user)
	if row.is_suspended:
		frappe.throw(_("This account is suspended, so nothing new can be started."))
	available = account.available(row)
	if flt(needed) > available:
		frappe.throw(_shortfall_message(flt(needed), available))


def _require_runway(needed) -> None:
	require_balance(frappe.session.user, needed)


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


def _shortfall_message(needed, available) -> str:
	return _("Not enough credits: this needs {0} and {1} are available — {2} short. Top up at {3}.").format(
		flt(needed, 2), flt(available, 2), flt(needed - available, 2), TOP_UP_ROUTE
	)
