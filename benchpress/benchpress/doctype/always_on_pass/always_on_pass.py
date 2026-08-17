# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from benchpress.credits import passes


class AlwaysOnPass(Document):
	def validate(self):
		self.validate_not_expired()
		self.validate_not_duplicated()

	def validate_not_expired(self):
		if frappe.utils.getdate(self.valid_until) < frappe.utils.getdate():
			frappe.throw(_("A pass cannot end in the past."))

	def validate_not_duplicated(self):
		"""One live pass per instance — two would let the same month be sold twice."""
		existing = passes.active_pass_name(self.bench_instance, exclude=self.name)
		if existing:
			frappe.throw(_("This instance already holds an active pass ({0}).").format(existing))
