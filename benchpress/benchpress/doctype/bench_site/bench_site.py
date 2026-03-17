# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BenchSite(Document):
	def validate(self):
		self.compute_full_domain()

	def compute_full_domain(self):
		"""Compute full_domain from site_name and bench domain."""
		if self.bench:
			bench_domain = frappe.db.get_value("Bench Instance", self.bench, "domain")
			if bench_domain:
				self.full_domain = f"{self.site_name}.{bench_domain}"
