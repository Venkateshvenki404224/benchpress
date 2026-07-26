# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import json
from pathlib import Path

import frappe
from frappe.model import default_fields
from frappe.tests import IntegrationTestCase

APP_NAME = "benchpress"
MODULE_NAME = "benchpress"

# Colors the workspace editor offers for a shortcut.
SHORTCUT_COLORS = {"Grey", "Green", "Red", "Orange", "Pink", "Yellow", "Blue", "Cyan"}

# Content block type -> (workspace child table, the block's data key). The desk binds a block to a
# child row by matching that key against the row's `label`, so a typo renders nothing and raises
# nothing.
BLOCK_BINDINGS = {
	"card": ("links", "card_name"),
	"chart": ("charts", "chart_name"),
	"number_card": ("number_cards", "number_card_name"),
	"quick_list": ("quick_lists", "quick_list_name"),
	"shortcut": ("shortcuts", "shortcut_name"),
}


def load_fixtures(folder_name):
	"""Return (filename, parsed json) for every fixture under benchpress/<folder_name>/."""
	folder = Path(frappe.get_app_path(APP_NAME), MODULE_NAME, folder_name)
	return [(path.name, json.loads(path.read_text())) for path in sorted(folder.glob("*/*.json"))]


def card_break_groups(links):
	"""Group a flat workspace links list into (Card Break row, the rows following it) pairs."""
	groups = []
	for row in links:
		if row["type"] == "Card Break":
			groups.append((row, []))
		elif groups:
			groups[-1][1].append(row)
	return groups


def child_row_labels(workspace, child_table):
	"""Labels a content block may bind to. Only a Card Break heads a card, never a Link row."""
	rows = workspace[child_table]
	if child_table == "links":
		rows = [row for row in rows if row["type"] == "Card Break"]
	return {row["label"] for row in rows}


def referenced_doctypes(workspace):
	"""Yield every DocType a workspace points at through its links, shortcuts, and quick lists."""
	for link in workspace["links"]:
		if link["type"] == "Link" and link["link_type"] == "DocType":
			yield link["link_to"]
	for shortcut in workspace["shortcuts"]:
		if shortcut["type"] == "DocType":
			yield shortcut["link_to"]
	for quick_list in workspace["quick_lists"]:
		yield quick_list["document_type"]


def is_real_fieldname(doctype, fieldname):
	return fieldname in default_fields or frappe.get_meta(doctype).has_field(fieldname)


def field_type(doctype, fieldname):
	field = frappe.get_meta(doctype).get_field(fieldname)
	return field.fieldtype if field else None


class TestWorkspaceFixtures(IntegrationTestCase):
	"""Guards the hand-authored desk fixtures, which fail silently rather than loudly.

	Every rule iterates over whatever the app ships, so new workspaces, cards, and charts are
	covered without touching this file.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.workspaces = load_fixtures("workspace")
		cls.number_cards = load_fixtures("number_card")
		cls.dashboard_charts = load_fixtures("dashboard_chart")

	@property
	def widgets(self):
		"""(DocType, filename, fixture) for every widget a workspace can embed."""
		return [("Number Card", *card) for card in self.number_cards] + [
			("Dashboard Chart", *chart) for chart in self.dashboard_charts
		]

	def test_fixtures_are_synced_to_the_database(self):
		"""bench migrate skips a fixture whose `modified` is not newer than the DB row."""
		for filename, workspace in self.workspaces:
			with self.subTest(fixture=filename):
				self.assertEqual(
					frappe.db.get_value("Workspace", workspace["name"], "content"),
					workspace["content"],
					f"{filename}: disk content differs from the synced Workspace — bump `modified`",
				)
		for doctype, filename, widget in self.widgets:
			with self.subTest(fixture=filename):
				self.assertTrue(
					frappe.db.exists(doctype, widget["name"]),
					f"{filename}: {doctype} {widget['name']} was never imported",
				)

	def test_content_blocks_resolve_to_child_rows(self):
		for filename, workspace in self.workspaces:
			for block in json.loads(workspace["content"]):
				binding = BLOCK_BINDINGS.get(block["type"])
				if not binding:
					continue
				child_table, data_key = binding
				labels = child_row_labels(workspace, child_table)
				with self.subTest(fixture=filename, block=block["id"]):
					self.assertIn(
						block["data"][data_key],
						labels,
						f"{filename}: block {block['id']} names "
						f"{block['data'][data_key]!r}, which is not a {child_table} label",
					)

	def test_referenced_doctypes_are_installed(self):
		for filename, workspace in self.workspaces:
			for doctype in referenced_doctypes(workspace):
				with self.subTest(fixture=filename, doctype=doctype):
					self.assertTrue(frappe.db.exists("DocType", doctype), f"{filename}: no such DocType")
		for _doctype, filename, widget in self.widgets:
			with self.subTest(fixture=filename, doctype=widget["document_type"]):
				self.assertTrue(
					frappe.db.exists("DocType", widget["document_type"]), f"{filename}: no such DocType"
				)

	def test_no_child_table_is_referenced(self):
		"""A child table has no list view, so linking one produces a dead end."""
		for filename, workspace in self.workspaces:
			for doctype in referenced_doctypes(workspace):
				with self.subTest(fixture=filename, doctype=doctype):
					self.assertFalse(
						frappe.get_meta(doctype).istable, f"{filename}: {doctype} is a child table"
					)

	def test_card_break_link_counts_match(self):
		"""build_links_table_from_card slices the flat links list by `link_count`."""
		for filename, workspace in self.workspaces:
			links = workspace["links"]
			if not links:
				continue
			with self.subTest(fixture=filename):
				self.assertEqual(
					links[0]["type"], "Card Break", f"{filename}: links must start with a Card Break"
				)
			for card_break, rows in card_break_groups(links):
				with self.subTest(fixture=filename, card=card_break["label"]):
					self.assertEqual(
						card_break["link_count"],
						len(rows),
						f"{filename}: card {card_break['label']} claims "
						f"{card_break['link_count']} links but {len(rows)} follow it",
					)

	def assert_filters_are_runnable(self, filename, document_type, filters):
		"""A filter naming a missing field leaves the widget empty rather than raising."""
		for _doctype, fieldname, _operator, _value in filters:
			with self.subTest(fixture=filename, fieldname=fieldname):
				self.assertTrue(
					is_real_fieldname(document_type, fieldname),
					f"{filename}: {document_type} has no field {fieldname!r}",
				)
		with self.subTest(fixture=filename):
			frappe.db.count(document_type, filters)

	def test_widget_filters_are_runnable(self):
		for _doctype, filename, widget in self.widgets:
			self.assert_filters_are_runnable(
				filename, widget["document_type"], json.loads(widget["filters_json"])
			)

	def test_quick_list_filters_are_runnable(self):
		for filename, workspace in self.workspaces:
			for row in workspace["quick_lists"]:
				self.assert_filters_are_runnable(
					filename, row["document_type"], json.loads(row["quick_list_filter"])
				)

	def test_charts_resolve_and_plot_a_real_time_axis(self):
		"""A timeseries chart silently plots nothing when `based_on` is not a date field."""
		for filename, workspace in self.workspaces:
			for row in workspace["charts"]:
				with self.subTest(fixture=filename, chart=row["chart_name"]):
					self.assertTrue(
						frappe.db.exists("Dashboard Chart", row["chart_name"]),
						f"{filename}: no Dashboard Chart named {row['chart_name']!r}",
					)
		for filename, chart in self.dashboard_charts:
			with self.subTest(fixture=filename, based_on=chart["based_on"]):
				self.assertIn(
					field_type(chart["document_type"], chart["based_on"]),
					{"Date", "Datetime"},
					f"{filename}: {chart['document_type']}.{chart['based_on']} is not a date field",
				)

	def test_shortcut_colors_are_allowed(self):
		for filename, workspace in self.workspaces:
			for shortcut in workspace["shortcuts"]:
				with self.subTest(fixture=filename, shortcut=shortcut["label"]):
					self.assertIn(shortcut["color"], SHORTCUT_COLORS, f"{filename}: unsupported color")
