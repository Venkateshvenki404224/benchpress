# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import cint

from benchpress.docker_manager import validate_lab_id

BASELINE_CPU_CORES = 1


class Lab(Document):
	def validate(self):
		validate_lab_id(self.lab_id)
		self.apply_instance_size()
		self.validate_cpu_cores()

	def apply_instance_size(self):
		"""Copy the chosen size's resources onto the two fields Docker actually reads.

		The size is the *choice* — it carries the price, so it is what the user picks — but
		`memory_limit` and `cpu_cores` stay the stored truth, so `docker_manager` and every screen
		that renders limits need to know nothing about `Instance Size`. A lab with no size keeps
		its hand-typed limits, which is what a self-hoster running with credits off wants.
		"""
		if not self.instance_size:
			return
		size = frappe.get_cached_doc("Instance Size", self.instance_size)
		self.memory_limit = size.memory_limit
		self.cpu_cores = size.cpu_cores

	def validate_cpu_cores(self):
		if cint(self.cpu_cores) < BASELINE_CPU_CORES:
			frappe.throw(_("CPU cores must be at least {0}.").format(BASELINE_CPU_CORES))
