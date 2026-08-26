# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.data import time_diff_in_seconds

from benchpress.benchpress import demo_data

SEEDED_DOCTYPES = ("Lab", "Bench Instance", "Bench Site", "Deploy Log", "Build Log")


def demo_lab_ids():
	return [spec["lab_id"] for spec in demo_data.LAB_SPECS]


def demo_universe():
	"""The rows this module owns, per seeded doctype: the field to filter on, and its values.

	A dev site carries real labs, benches and logs, and the seeder is run by hand against it. Every
	count and every scan below narrows to these rows, or it reads whatever else is on the site.
	`Lab` is named after its `lab_id`, so the seeded ids are their own filter.
	"""
	labs = demo_lab_ids()
	benches = frappe.get_all("Bench Instance", filters={"lab": ["in", labs]}, pluck="name")
	return {
		"Lab": ("lab_id", labs),
		"Bench Instance": ("lab", labs),
		"Bench Site": ("bench", benches),
		"Deploy Log": ("bench", benches),
		"Build Log": ("lab", labs),
	}


def demo_rows(doctype, fields):
	"""Seeded rows only. An empty universe is asked for nothing — `in ()` is not a query."""
	field, values = demo_universe()[doctype]
	if not values:
		return []
	return frappe.get_all(doctype, filters={field: ["in", values]}, fields=fields)


def delete_all(doctype, filters):
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def purge_demo_data():
	"""Remove any previously seeded demo records, children first, so the seeder actually runs.

	The dev site keeps the records of an earlier hand-run seed; without this the idempotence
	assertion below would pass vacuously. Each test rolls back, so nothing is really lost.
	"""
	labs = demo_lab_ids()
	benches = frappe.get_all("Bench Instance", filters={"lab": ["in", labs]}, pluck="name")
	if benches:
		delete_all("Deploy Log", {"bench": ["in", benches]})
		delete_all("Bench Site", {"bench": ["in", benches]})
	delete_all("Bench Instance", {"lab": ["in", labs]})
	delete_all("Build Log", {"lab": ["in", labs]})
	delete_all("Lab", {"lab_id": ["in", labs]})


def record_counts():
	"""Delta-compared, so it tolerates old rows — but not a concurrent deploy writing its own."""
	return {doctype: len(demo_rows(doctype, ["name"])) for doctype in SEEDED_DOCTYPES}


class TestDemoData(IntegrationTestCase):
	"""The seeder is run by hand on live dev sites, so it must be safe to run twice."""

	def setUp(self):
		purge_demo_data()

	def seeded_statuses(self, doctype) -> set:
		return {row.status for row in demo_rows(doctype, ["status"])}

	def test_seeding_is_idempotent(self):
		before = record_counts()
		demo_data.create_demo_data()
		after_first_run = record_counts()
		self.assertNotEqual(before, after_first_run, "the first run created nothing")

		demo_data.create_demo_data()
		self.assertEqual(after_first_run, record_counts(), "the second run created more records")

	def test_seeding_creates_no_vpn_peer(self):
		"""A seeded peer would claim a pool address and reconcile the live WireGuard interface."""
		before = frappe.db.count("VPN Peer")
		demo_data.create_demo_data()
		self.assertEqual(frappe.db.count("VPN Peer"), before)

	def test_every_widget_status_is_represented(self):
		demo_data.create_demo_data()
		self.assertIn("Ready", self.seeded_statuses("Lab"))
		self.assertIn("Running", self.seeded_statuses("Bench Instance"))
		self.assertIn("Error", self.seeded_statuses("Bench Instance"))
		self.assertIn("Active", self.seeded_statuses("Bench Site"))

	def test_deploy_logs_span_the_chart_timespan(self):
		"""A single-day pile of logs would draw one spike instead of a curve."""
		demo_data.create_demo_data()
		days = {row.timestamp.date() for row in demo_rows("Deploy Log", ["timestamp"])}
		self.assertGreater(len(days), 1)

	def test_a_seeded_run_lasts_minutes_not_weeks(self):
		"""Duration is `modified - timestamp`, so a backdated log must settle its own `modified`."""
		demo_data.create_demo_data()
		for doctype in ("Deploy Log", "Build Log"):
			for log in demo_rows(doctype, ["name", "timestamp", "modified"]):
				seconds = time_diff_in_seconds(log.modified, log.timestamp)
				self.assertGreater(seconds, 0, f"{doctype} {log.name} settled before it started")
				self.assertLess(seconds, 3600, f"{doctype} {log.name} claims a {seconds / 3600:.0f}h run")
