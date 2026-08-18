# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.patches.retire_orphaned_creating_sites import execute as retire_creating_sites


class TestRetireOrphanedCreatingSites(IntegrationTestCase):
	"""`Creating` used to be a state a dead worker could leave a site in forever."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": "test-lab-creating-sites",
				"title": "Test Lab (Creating Sites)",
				"frappe_version": "version-15",
			}
		).insert(ignore_permissions=True)
		cls.bench = frappe.get_doc({"doctype": "Bench Instance", "lab": cls.lab.name}).insert(
			ignore_permissions=True
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Site", filters={"bench": cls.bench.name}, pluck="name"):
			frappe.delete_doc("Bench Site", name, force=True, ignore_permissions=True)
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _site(self, site_name, status):
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"bench": self.bench.name,
				"site_name": site_name,
				"status": status,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Site", site.name, force=True, ignore_permissions=True)
		return site

	def test_a_stranded_creating_row_becomes_inactive(self):
		stranded = self._site("stranded.localhost", "Creating")

		retire_creating_sites()

		self.assertEqual(frappe.db.get_value("Bench Site", stranded.name, "status"), "Inactive")

	def test_rows_in_any_other_state_are_left_alone(self):
		"""A running site and a failed one both mean something; only `Creating` is a lie."""
		untouched = [self._site("live.localhost", "Active"), self._site("broken.localhost", "Error")]

		retire_creating_sites()

		statuses = [frappe.db.get_value("Bench Site", site.name, "status") for site in untouched]
		self.assertEqual(statuses, ["Active", "Error"])
