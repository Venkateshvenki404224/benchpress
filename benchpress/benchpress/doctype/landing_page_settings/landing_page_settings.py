# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from benchpress.benchpress.site_content import clear_content_cache


class LandingPageSettings(Document):
	def validate(self):
		self.check_step_phases()

	def on_update(self):
		clear_content_cache()

	def check_step_phases(self) -> None:
		declared = {(phase.phase_key or "").strip() for phase in self.pipeline_phases}
		for step in self.pipeline_steps:
			key = (step.phase_key or "").strip()
			if key not in declared:
				frappe.throw(
					_("Step {0} names phase {1}, which no row in Phases declares.").format(
						step.idx, frappe.bold(key or "—")
					)
				)
