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


class CreditAccount(Document):
	def validate(self):
		if flt(self.burn_rate) < 0:
			frappe.throw(_("Burn rate cannot be negative."))
		# A rate with no start point would charge from the epoch on the next settle.
		if flt(self.burn_rate) and not self.burn_since:
			self.burn_since = now_datetime()
