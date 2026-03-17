# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class BenchInstance(Document):
	def validate(self):
		self.validate_bench_name()

	def validate_bench_name(self):
		"""Ensure bench_name is a valid slug (lowercase alphanumeric + hyphens)."""
		if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", self.bench_name):
			frappe.throw(
				_("Bench Name must be lowercase alphanumeric with hyphens only (e.g., 'erp-production').")
			)
