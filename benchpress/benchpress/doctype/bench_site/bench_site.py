# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BenchSite(Document):
	def validate(self):
		self.compute_full_domain()

	def compute_full_domain(self):
		"""Derive the site's display name — a label, never a routable address.

		Nothing resolves `full_domain`: the site is served by the container itself on its
		WireGuard address, and `Bench Instance.domain` is free text on the desk form, so this
		value drifts whenever an admin edits it. This controller is its only writer; anything
		that needs the name the site actually exists under reads `site_name`.
		"""
		domain = frappe.db.get_value("Bench Instance", self.bench, "domain") if self.bench else None
		self.full_domain = f"{self.site_name}.{domain}" if domain else self.site_name
