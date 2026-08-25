# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LeasePlan(Document):
	def validate(self):
		if self.minutes < 1:
			frappe.throw(_("A lease plan has to last at least a minute."))
