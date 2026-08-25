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
re-reads the price from the `Credit Pack` the order points at and credits nothing unless the
rupees actually paid match it. A forged order buys exactly what it paid for.

Orders only: no payment links, no subscriptions, no auto-renewal, no dunning, no proration, no
cancellation. Money buys credits and credits buy time, so a customer who wants more time renews a
lease rather than holding a plan. Recurring billing is a business to run, not a feature to add,
and keeping it out is worth more than the convenience.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from benchpress.credits import account, config

APP = "razorpay_frappe"
ORDER = "Razorpay Order"
PACK = "Credit Pack"

CURRENCY = "INR"

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
	}


def buy_credits(pack_name: str) -> dict:
	"""Open an order for one credit pack, priced from the pack and never from the caller."""
	pack = _pack_on_sale(pack_name)
	return _open_order(pack.inr_price, PACK, pack.name, _("{0} credit pack").format(pack.pack_label))


def _pack_on_sale(pack_name: str):
	"""The pack, if it is one a customer may buy. Missing and withdrawn get the same sentence."""
	if not frappe.db.get_value(PACK, pack_name, "is_active"):
		frappe.throw(_("That credit pack is not on sale."))
	return frappe.get_cached_doc(PACK, pack_name)


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
	"""The doc event `razorpay_frappe` documents, and the seam settlement hangs on.

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
	if order.ref_dt != PACK:
		return _unsettled(order, "it references nothing BenchPress sells")
	_settle_pack(order)


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
