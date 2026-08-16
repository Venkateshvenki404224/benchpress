# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.data import cint

from benchpress.benchpress.doctype.lab.lab import BASELINE_CPU_CORES

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


def _new_lab(lab_id):
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": "Test Lab",
			"frappe_version": "version-15",
		}
	)


class IntegrationTestLab(IntegrationTestCase):
	"""
	Integration tests for Lab.
	Use this class for testing interactions between multiple components.
	"""

	def test_valid_lab_id_inserts(self):
		for lab_id in ("crm-lab", "dev-v15", "lab_2", "v16.0-beta"):
			if frappe.db.exists("Lab", lab_id):
				frappe.delete_doc("Lab", lab_id, force=True)
			doc = _new_lab(lab_id)
			doc.insert()
			self.assertEqual(doc.name, lab_id)
			doc.delete()

	def test_invalid_lab_id_rejected(self):
		for lab_id in ("TESTE V16", "DEV-v15", "with space", "-leading", "trailing-", "a..b", "", "x" * 65):
			with self.assertRaises(frappe.ValidationError, msg=f"lab_id {lab_id!r} should be rejected"):
				_new_lab(lab_id).insert()

	def test_cpu_cores_default_matches_baseline(self):
		cpu_cores = frappe.get_meta("Lab").get_field("cpu_cores")

		self.assertEqual(cint(cpu_cores.default), BASELINE_CPU_CORES)

	def test_cpu_cores_below_baseline_rejected(self):
		lab = _new_lab("below-cpu-baseline")
		lab.cpu_cores = BASELINE_CPU_CORES - 1

		with self.assertRaisesRegex(frappe.ValidationError, "CPU cores must be at least 1"):
			lab.insert()
