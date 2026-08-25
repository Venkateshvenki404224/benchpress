# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per user, holding the balance and what has been put into it.

The document is deliberately thin: all accounting lives in `benchpress.credits.account`, which
row-locks this record before every mutation. Nothing outside that module may write a balance,
which is why an operator's only ways in are the two document actions below.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from benchpress.credits import account, payments
from benchpress.permissions import require_admin


class CreditAccount(Document):
	def validate(self):
		# The tripwire for a lost decrement: a slot released twice would otherwise leave a
		# negative count that reads as free capacity forever.
		if cint(self.active_instances) < 0:
			frappe.throw(_("Active instances cannot be negative."))

	@frappe.whitelist()
	def post_adjustment(self, credits: float, reason: str):
		"""Move this balance by hand, in either direction, with the reason on the row.

		The operator's path into the ledger. It exists as a document action rather than as a
		writable ledger form because only `benchpress.credits.account` may touch a balance: a row
		typed into the ledger directly would explain a balance it never changed.
		"""
		require_admin()
		account.adjust(self.name, credits, reason)

	@frappe.whitelist()
	def post_refund(self, order: str, credits: float, reason: str):
		"""Give credits back against the Razorpay order that granted them.

		The money leaves Razorpay by somebody's hand — there is no gateway automation here on
		purpose. This is the ledger catching up with that, as its own negative row.
		"""
		require_admin()
		if not frappe.db.exists(payments.ORDER, order):
			frappe.throw(_("There is no {0} {1} to refund against.").format(payments.ORDER, order))
		account.refund(self.name, credits, reason, (payments.ORDER, order))
