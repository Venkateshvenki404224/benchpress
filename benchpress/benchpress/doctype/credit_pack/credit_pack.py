# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CreditPack(Document):
	def validate(self):
		if self.inr_price is not None and self.inr_price < 0:
			frappe.throw(_("Price cannot be negative."))
		if self.credits is not None and self.credits <= 0:
			frappe.throw(_("A pack must grant more than zero credits."))
