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
		self.validate_cpu_cores()

	def validate_cpu_cores(self):
		if cint(self.cpu_cores) < BASELINE_CPU_CORES:
			frappe.throw(_("CPU cores must be at least {0}.").format(BASELINE_CPU_CORES))
