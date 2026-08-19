# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import lab_templates

REQUIRED_FIELDS = {
	"key",
	"title",
	"description",
	"frappe_version",
	"memory_limit",
	"cpu_cores",
	"apps",
}


class TestLabTemplates(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# The test site predates `Lab Template`, so the patch that seeds it has already been
		# recorded as run. Seeding here is idempotent and doubles as a test of the seeder.
		lab_templates.seed_lab_templates()
		# Class fixtures must outlive the per-test transaction.
		frappe.db.commit()  # nosemgrep

	def setUp(self):
		frappe.set_user("Administrator")

	def _make_lab(self, template_key, lab_id, title=None):
		if frappe.db.exists("Lab", lab_id):
			frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
		name = lab_templates.create_lab_from_template(template_key, lab_id, title)
		self.addCleanup(
			lambda n=name: frappe.delete_doc("Lab", n, force=True, ignore_permissions=True)
			if frappe.db.exists("Lab", n)
			else None
		)
		return frappe.get_doc("Lab", name)

	def test_catalog_is_non_empty_and_well_formed(self):
		templates = lab_templates.get_templates()
		self.assertTrue(templates)
		for template in templates:
			self.assertTrue(REQUIRED_FIELDS.issubset(template))
			self.assertIsInstance(template["apps"], list)

	def test_template_keys_are_unique(self):
		keys = [template["key"] for template in lab_templates.get_templates()]
		self.assertEqual(len(keys), len(set(keys)))

	def test_get_template_returns_match(self):
		self.assertEqual(lab_templates.get_template("erpnext")["key"], "erpnext")

	def test_first_party_app_templates_present(self):
		# Each first-party app template also lists the dependency that app's own
		# hooks.py declares in `required_apps`, installed before the app itself.
		expected = {
			"hrms": ["erpnext", "hrms"],
			"lms": ["payments", "lms"],
			"helpdesk": ["telephony", "helpdesk"],
			"hrms-16": ["erpnext", "hrms"],
			"lms-16": ["payments", "lms"],
			"helpdesk-16": ["telephony", "helpdesk"],
		}
		for key, app_names in expected.items():
			template = lab_templates.get_template(key)
			self.assertEqual([app["app_name"] for app in template["apps"]], app_names)

	def test_india_compliance_template_installs_erpnext_first(self):
		for key in ("india-compliance", "india-compliance-16"):
			template = lab_templates.get_template(key)
			app_names = [app["app_name"] for app in template["apps"]]
			# india_compliance extends ERPNext; order matters at install time.
			self.assertEqual(app_names, ["erpnext", "india_compliance"])

	def test_v16_templates_present(self):
		v16_keys = [
			"erpnext-16",
			"frappe-16",
			"crm-16",
			"hrms-16",
			"lms-16",
			"helpdesk-16",
			"india-compliance-16",
		]
		for key in v16_keys:
			template = lab_templates.get_template(key)
			self.assertEqual(template["frappe_version"], "version-16", key)

	def test_get_template_unknown_throws(self):
		with self.assertRaises(frappe.ValidationError):
			lab_templates.get_template("does-not-exist")

	def test_create_lab_from_template_populates_apps_and_resources(self):
		lab = self._make_lab("erpnext", "tmpl-erpnext-test")
		self.assertEqual(lab.frappe_version, "version-15")
		self.assertEqual(lab.memory_limit, "2g")
		self.assertEqual(lab.cpu_cores, 2)
		self.assertEqual(len(lab.apps), 1)
		self.assertEqual(lab.apps[0].app_name, "erpnext")

	def test_create_lab_from_template_with_no_apps(self):
		lab = self._make_lab("frappe", "tmpl-frappe-test", title="My Frappe Lab")
		self.assertEqual(lab.title, "My Frappe Lab")
		self.assertEqual(len(lab.apps), 0)

	def test_create_lab_from_template_unknown_throws(self):
		with self.assertRaises(frappe.ValidationError):
			lab_templates.create_lab_from_template("nope", "tmpl-nope-test")

	def test_created_lab_names_the_template_it_came_from(self):
		lab = self._make_lab("erpnext", "tmpl-erpnext-stamp")
		self.assertEqual(lab.template, "erpnext")

	def test_catalog_points_a_used_template_at_the_lab_it_built(self):
		lab = self._make_lab("hrms", "tmpl-hrms-used")
		catalog = {template["key"]: template for template in lab_templates.get_catalog()}

		self.assertEqual(catalog["hrms"]["lab"]["name"], lab.name)
		self.assertEqual(catalog["hrms"]["lab"]["status"], lab.status)

	def test_catalog_reports_a_lab_only_where_one_was_built(self):
		for template in lab_templates.get_catalog():
			built = bool(frappe.db.exists("Lab", {"template": template["key"]}))
			self.assertEqual(bool(template["lab"]), built, template["key"])

	def test_catalog_carries_every_template_field(self):
		for template in lab_templates.get_catalog():
			self.assertTrue(REQUIRED_FIELDS.issubset(template))

	def test_catalog_does_not_mutate_the_module_catalog(self):
		lab_templates.get_catalog()
		self.assertFalse(any("lab" in template for template in lab_templates.get_templates()))
