# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from benchpress.credits.config import clear_size_index


class InstanceSize(Document):
	def validate(self):
		self.validate_cpu_cores()
		self.validate_single_default()

	def on_update(self):
		clear_size_index()

	def on_trash(self):
		clear_size_index()

	def validate_cpu_cores(self):
		if self.cpu_cores is not None and self.cpu_cores < 1:
			frappe.throw(_("CPU Cores must be at least 1."))

	def validate_single_default(self):
		"""Only one size may be the default, so `size_for_lab` has one answer."""
		if not self.is_default:
			return

		existing = self.get_other_default()
		if existing:
			frappe.throw(
				_("{0} is already the default size. Clear its Is Default before setting another.").format(
					existing
				)
			)

	def get_other_default(self) -> str | None:
		names = frappe.get_all(
			"Instance Size",
			filters={"is_default": 1, "name": ("!=", self.name)},
			pluck="name",
			limit=1,
		)
		return names[0] if names else None
