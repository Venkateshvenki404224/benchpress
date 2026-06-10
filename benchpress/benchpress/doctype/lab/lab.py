# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

from benchpress.docker_manager import validate_lab_id


class Lab(Document):
	def validate(self):
		validate_lab_id(self.lab_id)
