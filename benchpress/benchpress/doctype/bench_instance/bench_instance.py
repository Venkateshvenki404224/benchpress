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

	def on_trash(self):
		if self.wg_public_key:
			try:
				from benchpress.wg_manager import remove_peer_from_server

				remove_peer_from_server(self.wg_public_key)
			except Exception:
				frappe.log_error(title=f"WG cleanup failed: {self.name}")
		if self.wg_ip and self.container_id:
			try:
				from benchpress.wg_manager import remove_wg_routing

				remove_wg_routing(self.wg_ip, self.container_id)
			except Exception:
				pass
