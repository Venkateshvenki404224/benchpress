# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Money in: a Razorpay order, settled into the ledger exactly once.

The gateway is an **optional app**. `razorpay_frappe` is deliberately absent from `required_apps`
and must stay absent — somebody running BenchPress on their own hardware should never be made to
install a payment processor to use it. So every entry point asks `payments_available()` first and
refuses with a sentence instead of an ImportError, and the import itself is local to the one
function that needs it.

**Idempotency is the whole game.** Razorpay retries webhooks, `on_update` fires on every save of
an order, and an operator pressing *Sync Status* in Desk is a third delivery of the same payment.
The guard is `account.purchase`, which checks the `(reference_doctype, reference_name)` index for
this order under the same row lock that applies the credit — so two deliveries racing each other
serialise on the lock rather than both reading an empty ledger. Everything a purchase does beyond
the credit hangs off that one once-ever answer.

**The amount is never taken from the caller.** `razorpay_frappe` exposes an open
`/razorpay-api/initiate-order` endpoint on which any logged-in user names their own amount,
metadata and references, so a paid order is *not* evidence of what was bought. Settlement
re-reads the price from the `Credit Pack` or `Credit Settings` the order points at and credits
nothing unless the rupees actually paid match it. A forged order buys exactly what it paid for.

Orders only: no payment links, no subscriptions, no auto-renewal, no dunning, no proration, no
cancellation. A lapsed always-on pass is bought again. Recurring billing is a business to run,
not a feature to add, and keeping it out is worth more than the convenience.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, flt, today

from benchpress.credits import account, config, metering, passes
from benchpress.labs import bench_label

APP = "razorpay_frappe"
ORDER = "Razorpay Order"
PACK = "Credit Pack"
BENCH = "Bench Instance"

CURRENCY = "INR"
PASS_DAYS = config.PASS_DAYS

BENCH_FIELDS = ["name", "owner", "lab", "credit_burn_rate", "credit_burn_started"]
PACK_FIELDS = ["name", "pack_label", "inr_price", "credits"]


def payments_available() -> bool:
	"""Whether a gateway is installed at all. Absent is a supported state, not a broken one."""
	return APP in frappe.get_installed_apps()


# --- What can be bought --------------------------------------------------------


def purchase_options() -> dict:
	"""Everything the buy dialog renders, including whether buying is possible at all.

	`payments_available` travels with the prices rather than through an endpoint of its own, so a
	site with credits switched on but no gateway installed shows its pricing and explains that
	checkout is not wired up — instead of offering a button that throws.
	"""
	if not config.credits_enabled():
		return {"enabled": False, "payments_available": False, "packs": []}
	return {
		"enabled": True,
		"payments_available": payments_available(),
		"packs": config.active_packs(),
		"always_on_inr": cint(config.settings().always_on_monthly_inr),
		"always_on_days": PASS_DAYS,
	}


def buy_credits(pack_name: str) -> dict:
	"""Open an order for one credit pack, priced from the pack and never from the caller."""
	pack = _pack_on_sale(pack_name)
	return _open_order(pack.inr_price, PACK, pack.name, _("{0} credit pack").format(pack.pack_label))


def buy_always_on_pass(bench_name: str) -> dict:
	"""Open an order for 30 days of always-on on one instance."""
	bench = _pass_candidate(bench_name)
	price = cint(config.settings().always_on_monthly_inr)
	if not price:
		frappe.throw(_("The always-on pass has no price set on this site, so it cannot be bought."))
	return _open_order(price, BENCH, bench.name, _("Always On Pass for {0}").format(_label(bench)))


def _pack_on_sale(pack_name: str):
	"""The pack, if it is one a customer may buy. Missing and withdrawn get the same sentence."""
	if not frappe.db.get_value(PACK, pack_name, "is_active"):
		frappe.throw(_("That credit pack is not on sale."))
	return frappe.get_cached_doc(PACK, pack_name)


def _pass_candidate(bench_name: str):
	"""The instance a pass is being bought for. One live pass at a time, so a month is sold once."""
	bench = frappe.db.get_value(BENCH, bench_name, BENCH_FIELDS, as_dict=True)
	if not bench:
		frappe.throw(_("That instance does not exist."))
	if passes.has_active_pass(bench.name):
		frappe.throw(_("This instance already holds an active pass. Buy the next one when it lapses."))
	return bench


def _open_order(amount, ref_doctype: str, ref_name: str, description: str) -> dict:
	"""One Razorpay order, plus what the SPA hands to checkout.

	Rupees are whole. Razorpay bills in paise and `razorpay_frappe` reaches them by multiplying by
	100, so a price carrying stray decimals would round somewhere nobody can see — and settlement
	compares whole rupees for exactly the same reason.
	"""
	_require_gateway()
	rupees = cint(amount)
	if rupees <= 0:
		frappe.throw(_("That costs nothing, so there is nothing to pay for."))

	from razorpay_frappe.razorpay_integration.doctype.razorpay_order.razorpay_order import (
		RazorpayOrder,
	)

	checkout = RazorpayOrder.initiate(
		rupees, CURRENCY, {"description": description}, ref_dt=ref_doctype, ref_dn=ref_name
	)
	return {**checkout, "amount": rupees, "currency": CURRENCY, "description": description}


def _require_gateway() -> None:
	if not config.credits_enabled():
		frappe.throw(_("Credits are switched off on this site, so there is nothing to buy."))
	if not payments_available():
		frappe.throw(
			_("Payments are not set up on this site. Ask the operator to install the razorpay_frappe app.")
		)


# --- Settlement: the only way money enters the ledger --------------------------


def on_razorpay_update(doc, event=None) -> None:
	"""The doc event `razorpay_frappe` documents, and the seam this whole phase hangs on.

	It fires on *every* save of an order, which is the reason settlement is replay-safe rather than
	once-only: the checkout callback, the `payment.captured` webhook and each of its retries all
	save the same document, and every one of them arrives here.
	"""
	if doc.status == "Paid":
		settle_order(doc)


def settle_order(order) -> None:
	"""Apply one paid order, once.

	The account credited is the order's `owner`, never the session: a webhook is processed as
	Administrator and the checkout callback as the buyer, and the buyer is the one who paid.
	"""
	if not config.credits_enabled():
		return
	if order.ref_dt == PACK:
		_settle_pack(order)
	elif order.ref_dt == BENCH:
		_settle_pass(order)
	else:
		_unsettled(order, "it references nothing BenchPress sells")


def _settle_pack(order) -> None:
	"""Credit what the referenced pack grants, if the rupees paid are that pack's price."""
	pack = frappe.db.get_value(PACK, order.ref_dn, PACK_FIELDS, as_dict=True)
	if not pack:
		return _unsettled(order, "the credit pack it names no longer exists")
	if not _amount_matches(order, pack.inr_price):
		return _unsettled(order, f"it paid {cint(order.amount)} for a pack priced {cint(pack.inr_price)}")
	if account.purchase(
		order.owner, flt(pack.credits), _("Bought the {0} pack").format(pack.pack_label), _reference(order)
	):
		_announce(order.owner)


def _settle_pass(order) -> None:
	"""Grant the pass, and stop the hourly meter the pass replaces.

	The ledger row carries **zero credits**: a pass buys hours, not credits. It is written anyway,
	because the ledger is the record that money moved and because it is the replay guard both
	halves of this share — the pass row is only ever created behind a `purchase` that returned
	True, so a redelivered webhook cannot mint a second month.
	"""
	bench = frappe.db.get_value(BENCH, order.ref_dn, BENCH_FIELDS, as_dict=True)
	if not bench:
		return _unsettled(order, "the instance it names no longer exists")
	if bench.owner != order.owner:
		return _unsettled(order, "it was paid by somebody who does not own that instance")
	price = cint(config.settings().always_on_monthly_inr)
	if not _amount_matches(order, price):
		return _unsettled(order, f"it paid {cint(order.amount)} for a pass priced {price}")
	description = _("Always On Pass for {0}, {1} days").format(_label(bench), PASS_DAYS)
	if account.purchase(order.owner, 0.0, description, _reference(order)):
		_grant_pass(bench, order)
		_announce(order.owner)


def _grant_pass(bench, order) -> None:
	"""The pass row, then the meter it makes unnecessary."""
	pass_doc = frappe.new_doc(passes.PASS)
	pass_doc.bench_instance = bench.name
	pass_doc.valid_until = add_days(today(), PASS_DAYS)
	pass_doc.razorpay_order = cstr(order.name)
	pass_doc.insert(ignore_permissions=True)
	metering.on_pass_purchased(bench)


def _amount_matches(order, price) -> bool:
	return cint(order.amount) == cint(price)


def _reference(order) -> tuple[str, str]:
	"""What makes a payment findable, and therefore unrepeatable."""
	return (ORDER, cstr(order.name))


def _unsettled(order, reason: str) -> None:
	"""Record a paid order the ledger cannot accept. Never raise.

	Throwing inside a doc event would roll the order's own `status` back with the transaction, so
	the site would forget it had been paid as well as failing to credit it — strictly worse than a
	payment that is visibly outstanding. The reconciliation report is where these are meant to be
	found, and an operator settles them with an Adjustment.
	"""
	frappe.log_error(
		title=f"Unsettled Razorpay order {order.name}",
		message=f"Order {order.order_id} was paid but credited nothing: {reason}.",
	)


def _announce(user: str) -> None:
	"""Nudge the balance chip. Best-effort — the SPA also refreshes when checkout returns."""
	frappe.publish_realtime("benchpress:credits", user=user)


def _label(bench) -> str:
	"""What the instance is called on screen. `bench.name` is an md5, which explains nothing."""
	return bench_label(frappe.db.get_value("Lab", bench.lab, "lab_id")) or bench.name
