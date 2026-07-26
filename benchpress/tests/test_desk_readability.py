# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

APP_NAME = "benchpress"
MODULE_NAME = "benchpress"

# A title stands in for the record name in list views, link fields, and quick lists, so it has to
# be short, plain, and safe to show. A Password is secret, a Code field holds shell output, and a
# Table has no scalar value to render.
UNUSABLE_TITLE_FIELDTYPES = {"Code", "Password", "Table", "Table MultiSelect", "Text Editor"}


def doctype_definitions():
	"""Return (DocType name, parsed json) for every DocType this app ships."""
	folder = Path(frappe.get_app_path(APP_NAME), MODULE_NAME, "doctype")
	definitions = (json.loads(path.read_text()) for path in sorted(folder.glob("*/*.json")))
	return [(each["name"], each) for each in definitions if each.get("doctype") == "DocType"]


def hooked_list_scripts():
	"""Return (DocType name, app-relative asset path) for every doctype_list_js entry."""
	hook = frappe.get_hooks("doctype_list_js", default={}, app_name=APP_NAME)
	return [(doctype, path) for doctype, paths in hook.items() for path in paths]


def app_asset(path):
	return Path(frappe.get_app_path(APP_NAME), *path.strip("/").split("/"))


class TestDeskReadability(IntegrationTestCase):
	"""Guards the two desk affordances that fail silently: titles and list view scripts.

	A `title_field` pointing at the wrong fieldtype renders a blank or a wall of shell output, and
	a `doctype_list_js` path that does not resolve is dropped without a warning.
	"""

	def test_title_fields_are_displayable(self):
		for doctype, definition in doctype_definitions():
			title_field = definition.get("title_field")
			if not title_field:
				continue
			field = frappe.get_meta(doctype).get_field(title_field)
			with self.subTest(doctype=doctype, title_field=title_field):
				self.assertIsNotNone(field, f"{doctype} has no field {title_field!r}")
				self.assertNotIn(
					field.fieldtype,
					UNUSABLE_TITLE_FIELDTYPES,
					f"{doctype}.{title_field} is a {field.fieldtype}, which makes a poor title",
				)

	def test_list_view_scripts_exist_on_disk(self):
		for doctype, path in hooked_list_scripts():
			with self.subTest(doctype=doctype, asset=path):
				self.assertTrue(
					app_asset(path).exists(),
					f"{doctype}: hooks.py registers {path}, which is missing on disk",
				)

	def test_list_view_scripts_target_an_installed_doctype(self):
		for doctype, path in hooked_list_scripts():
			with self.subTest(doctype=doctype, asset=path):
				self.assertTrue(frappe.db.exists("DocType", doctype), f"{path}: no such DocType")

	def test_list_view_scripts_settle_on_the_doctype_they_are_hooked_to(self):
		"""frappe.listview_settings is keyed by DocType, so a copied file silently does nothing."""
		for doctype, path in hooked_list_scripts():
			with self.subTest(doctype=doctype, asset=path):
				self.assertIn(
					f'frappe.listview_settings["{doctype}"]',
					app_asset(path).read_text(),
					f"{path}: does not assign frappe.listview_settings[{doctype!r}]",
				)
