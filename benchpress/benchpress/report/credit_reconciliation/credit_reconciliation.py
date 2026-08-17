# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Every paid Razorpay order, beside the ledger row it produced — and every row that has none.

The ledger is the money record. The gateway is a system we do not own, reachable through webhooks
that retry, arrive out of order, or do not arrive at all, so the two *will* disagree eventually.
This report exists so that when they do, somebody sees it: an order that took a customer's money
and credited nothing is not a rounding error, and a credit with no payment behind it is worse.

Both directions are reported, because both are real failures:

- **Paid, not credited** — settlement refused the order. `payments._unsettled` has logged why;
  the fix is a manual Adjustment on the account once the operator has decided what was owed.
- **Credited, no paid order** — a Purchase row pointing at an order that is missing or unpaid.
  Only a hand-written row or a refunded-then-replayed order can produce this.

Two queries and a dict, whatever the volume. Never a `get_doc` per order.
"""

import frappe
from frappe.utils import cint, cstr, flt

from benchpress.credits import account, payments

LEDGER = "Credit Ledger Entry"

SETTLED = "Settled"
NOT_CREDITED = "Paid, not credited"
UNBACKED = "Credited, no paid order"

COLUMNS = [
	{"label": "Status", "fieldname": "state", "fieldtype": "Data", "width": 170},
	{
		"label": "Order",
		"fieldname": "order",
		"fieldtype": "Link",
		"options": payments.ORDER,
		"width": 90,
	},
	{"label": "Payment", "fieldname": "payment_id", "fieldtype": "Data", "width": 160},
	{"label": "Buyer", "fieldname": "buyer", "fieldtype": "Link", "options": "User", "width": 200},
	{"label": "Paid (INR)", "fieldname": "amount", "fieldtype": "Currency", "width": 110},
	{"label": "Bought", "fieldname": "bought", "fieldtype": "Data", "width": 200},
	{"label": "Ledger Entry", "fieldname": "entry", "fieldtype": "Link", "options": LEDGER, "width": 130},
	{"label": "Credits", "fieldname": "credits", "fieldtype": "Float", "width": 90},
]


def execute(filters=None):
	if not payments.payments_available():
		return COLUMNS, []
	orders = _paid_orders()
	entries = _purchase_entries()
	return COLUMNS, _rows(orders, entries)


def _rows(orders: list, entries: dict) -> list[dict]:
	rows = [_order_row(order, entries.get(cstr(order.name))) for order in orders]
	rows.extend(_unbacked_rows(orders, entries))
	rows.sort(key=lambda row: row["state"] == SETTLED)
	return rows


def _order_row(order, entry) -> dict:
	return {
		"state": SETTLED if entry else NOT_CREDITED,
		"order": order.name,
		"payment_id": order.payment_id,
		"buyer": order.owner,
		"amount": flt(order.amount),
		"bought": _bought(order),
		"entry": entry.name if entry else None,
		"credits": flt(entry.credits) if entry else 0.0,
	}


def _unbacked_rows(orders: list, entries: dict) -> list[dict]:
	"""Purchase rows whose order is missing or not marked paid — the direction that hides."""
	paid = {cstr(order.name) for order in orders}
	return [
		{
			"state": UNBACKED,
			"order": cint(reference) or None,
			"payment_id": None,
			"buyer": entry.account,
			"amount": 0.0,
			"bought": entry.description,
			"entry": entry.name,
			"credits": flt(entry.credits),
		}
		for reference, entry in entries.items()
		if reference not in paid
	]


def _bought(order) -> str:
	"""What the order points at, in one line. The reference is the only description we trust."""
	return f"{order.ref_dt}: {order.ref_dn}" if order.ref_dt else ""


def _paid_orders() -> list:
	return frappe.get_all(
		payments.ORDER,
		filters={"status": "Paid"},
		fields=["name", "owner", "amount", "payment_id", "ref_dt", "ref_dn"],
		order_by="creation desc",
	)


def _purchase_entries() -> dict:
	"""`{order name: entry}` for every Purchase row, on the reference index."""
	rows = frappe.get_all(
		LEDGER,
		filters={"reference_doctype": payments.ORDER, "entry_type": account.PURCHASE},
		fields=["name", "account", "credits", "description", "reference_name"],
	)
	return {row.reference_name: row for row in rows}
