# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import cint

from benchpress.docker_manager import validate_lab_id
from benchpress.image_cache import build_spec

BASELINE_CPU_CORES = 1

# A `Lab` spells its statuses the same way a `Bench Instance` does, and one grep cannot tell the
# two doctypes apart. Named so the lifecycle's one-writer guard stays readable.
LAB_DRAFT = "Draft"
LAB_READY = "Ready"


class Lab(Document):
	def validate(self):
		validate_lab_id(self.lab_id)
		self.apply_instance_size()
		self.validate_cpu_cores()
		self.reset_status_if_spec_changed()
		self.clear_golden_manifest_if_image_changed()

	def reset_status_if_spec_changed(self):
		"""A `Ready` lab's image tag is static now (`benchpress/<lab_id>:lab`, not a content
		hash), so an edit to what actually gets built no longer changes the tag by itself —
		nothing else would catch a Ready lab quietly pointing at a stale image.
		"""
		if self.status != LAB_READY or self.is_new():
			return
		before = self.get_doc_before_save()
		if before and build_spec(self) != build_spec(before):
			self.status = LAB_DRAFT
			# The golden in the old image was built from the old spec, so it no longer describes
			# what this lab asks for.
			self.golden_manifest = None
			frappe.msgprint(_("Lab spec changed — rebuild the image before deploying."))

	def clear_golden_manifest_if_image_changed(self):
		"""The manifest describes one image. A different tag has its own golden, or none."""
		before = self.get_doc_before_save()
		if before and before.image_tag != self.image_tag:
			self.golden_manifest = None

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
