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
		for key in ("hrms", "lms", "helpdesk"):
			template = lab_templates.get_template(key)
			self.assertEqual(len(template["apps"]), 1)
			self.assertEqual(template["apps"][0]["app_name"], key)

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
