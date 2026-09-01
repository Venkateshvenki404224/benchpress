# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.patches.backfill_bench_runtime import FIELD as RUNTIME_FIELD
from benchpress.patches.backfill_bench_runtime import SETTINGS
from benchpress.patches.backfill_bench_runtime import execute as backfill_bench_runtime
from benchpress.patches.drop_page_content_doctypes import PAGE_CONTENT_DOCTYPES
from benchpress.patches.drop_page_content_doctypes import execute as drop_page_content_doctypes
from benchpress.patches.retire_orphaned_creating_sites import execute as retire_creating_sites

KEPT_DOCTYPES = ("Contact Message", "Waitlist Entry")


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


class TestBackfillBenchRuntime(IntegrationTestCase):
	"""A container's runtime is fixed when it is created; the field must never claim otherwise."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": "test-lab-backfill-runtime",
				"title": "Test Lab (Backfill Runtime)",
				"frappe_version": "version-15",
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		self.previous = frappe.db.get_single_value(SETTINGS, RUNTIME_FIELD)
		self.addCleanup(self._restore_settings)
		frappe.db.delete("Singles", {"doctype": SETTINGS, "field": RUNTIME_FIELD})
		frappe.clear_document_cache(SETTINGS, SETTINGS)

	def _restore_settings(self):
		frappe.db.set_single_value(SETTINGS, RUNTIME_FIELD, self.previous)
		frappe.clear_document_cache(SETTINGS, SETTINGS)

	def _bench(self, runtime):
		bench = frappe.get_doc({"doctype": "Bench Instance", "lab": self.lab.name}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value("Bench Instance", bench.name, "runtime", runtime, update_modified=False)
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)
		return bench.name

	def test_a_bench_that_predates_the_field_is_stamped_runc(self):
		predates = self._bench("")

		backfill_bench_runtime()

		self.assertEqual(frappe.db.get_value("Bench Instance", predates, "runtime"), "runc")

	def test_a_bench_already_running_sysbox_is_left_alone(self):
		"""Stamping it `runc` would be the same lie in the other direction."""
		deployed = self._bench("sysbox")

		backfill_bench_runtime()

		self.assertEqual(frappe.db.get_value("Bench Instance", deployed, "runtime"), "sysbox")

	def test_sysbox_becomes_the_default_for_new_benches(self):
		backfill_bench_runtime()

		self.assertEqual(frappe.db.get_single_value(SETTINGS, RUNTIME_FIELD), "sysbox")

	def test_an_operator_who_has_already_chosen_keeps_that_choice(self):
		frappe.db.set_single_value(SETTINGS, RUNTIME_FIELD, "runc")

		backfill_bench_runtime()

		self.assertEqual(frappe.db.get_single_value(SETTINGS, RUNTIME_FIELD), "runc")


class TestDropPageContentDoctypes(IntegrationTestCase):
	"""The page-copy doctypes leave the schema, not only the app directory."""

	def test_desk_search_can_no_longer_find_any_of_them(self):
		drop_page_content_doctypes()

		self.assertEqual(self.survivors(), [])
		self.assertEqual(self.leftover_singles(), [])

	def test_a_site_that_never_had_them_runs_the_step_again_unchanged(self):
		drop_page_content_doctypes()

		drop_page_content_doctypes()

		self.assertEqual(self.survivors(), [])

	def test_the_records_that_hold_real_data_are_left_alone(self):
		drop_page_content_doctypes()

		for doctype in KEPT_DOCTYPES:
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)
			self.assertTrue(frappe.db.table_exists(doctype), doctype)

	def survivors(self) -> list[str]:
		return [
			doctype
			for doctype in PAGE_CONTENT_DOCTYPES
			if frappe.db.exists("DocType", doctype) or frappe.db.table_exists(doctype)
		]

	def leftover_singles(self) -> list[str]:
		singles = frappe.qb.Table("tabSingles")
		rows = (
			frappe.qb.from_(singles)
			.select(singles.doctype)
			.where(singles.doctype.isin(list(PAGE_CONTENT_DOCTYPES)))
			.run()
		)
		return [row[0] for row in rows]
