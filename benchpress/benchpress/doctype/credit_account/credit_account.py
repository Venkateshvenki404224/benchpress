# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per user, holding the settled balance and the current burn rate.

The document is deliberately thin: all accounting lives in `benchpress.credits.account`, which
row-locks this record before every mutation. Nothing outside that module should write these
fields, so `validate` only guards the invariants a hand edit in Desk could break.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from benchpress.credits import account, payments
from benchpress.permissions import require_admin


class CreditAccount(Document):
	def validate(self):
		if flt(self.burn_rate) < 0:
			frappe.throw(_("Burn rate cannot be negative."))
		# A rate with no start point would charge from the epoch on the next settle.
		if flt(self.burn_rate) and not self.burn_since:
			self.burn_since = now_datetime()

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
