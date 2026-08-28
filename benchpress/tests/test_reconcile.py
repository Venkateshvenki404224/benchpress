# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import reconcile
from benchpress.reconcile import DEFAULT_GRACE_MINUTES, compare, configured_grace_minutes

LIVE_ID = "40c6dd07a12727f3648970f0a1ae5cdc912f17a6756566264687f2ede0d0ec15"
OTHER_ID = "7716d70b337b7783837f3b515725506c593b41b7cef81dda3f96011a0f24ef66"


def _container(container_id=LIVE_ID, *, age_minutes=60, name="bench-one"):
	"""One entry in the shape `docker_manager.list_benches` returns."""
	created = None if age_minutes is None else datetime.now(UTC) - timedelta(minutes=age_minutes)
	return {
		"id": container_id,
		"name": name,
		"bench_name": name,
		"status": "running",
		"health": "Healthy",
		"created": created,
	}


class TestCompare(unittest.TestCase):
	"""Both sides arrive as arguments, so every case here runs without a database or a daemon."""

	def drift(self, rows, containers, grace_minutes=DEFAULT_GRACE_MINUTES):
		return compare(rows, containers, grace_minutes=grace_minutes)

	def test_a_container_with_no_row_is_an_orphan(self):
		drift = self.drift([], [_container()])

		self.assertEqual([c["id"] for c in drift["orphan_containers"]], [LIVE_ID])
		self.assertEqual(drift["in_grace"], [])

	def test_a_container_inside_the_grace_window_is_never_an_orphan(self):
		"""Every deploy passes through this state: the container exists before the row names it."""
		drift = self.drift([], [_container(age_minutes=2)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual([c["id"] for c in drift["in_grace"]], [LIVE_ID])

	def test_a_container_of_unknown_age_is_never_an_orphan(self):
		drift = self.drift([], [_container(age_minutes=None)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual([c["id"] for c in drift["in_grace"]], [LIVE_ID])

	def test_a_wider_window_spares_an_older_container(self):
		drift = self.drift([], [_container(age_minutes=60)], grace_minutes=120)

		self.assertEqual(drift["orphan_containers"], [])

	def test_a_row_whose_container_is_gone_is_named_missing(self):
		drift = self.drift([{"name": "bench-one", "container_id": LIVE_ID, "status": "Running"}], [])

		self.assertEqual([r["name"] for r in drift["missing_containers"]], ["bench-one"])

	def test_a_matched_pair_is_no_drift_either_way(self):
		rows = [{"name": "bench-one", "container_id": LIVE_ID, "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual(drift, {"orphan_containers": [], "in_grace": [], "missing_containers": []})

	def test_a_row_holding_the_short_id_still_matches_its_container(self):
		rows = [{"name": "bench-one", "container_id": LIVE_ID[:12], "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual(drift["missing_containers"], [])

	def test_a_row_with_no_container_is_not_drift(self):
		"""A Draft bench has no container yet, and never had one."""
		drift = self.drift([{"name": "draft", "container_id": None, "status": "Draft"}], [])

		self.assertEqual(drift["missing_containers"], [])

	def test_both_directions_are_named_at_once(self):
		rows = [{"name": "gone", "container_id": OTHER_ID, "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual([c["id"] for c in drift["orphan_containers"]], [LIVE_ID])
		self.assertEqual([r["name"] for r in drift["missing_containers"]], ["gone"])

	def test_compare_reads_neither_side(self):
		"""The guard against a second, disagreeing implementation that goes and looks for itself."""
		with (
			patch("frappe.get_all", side_effect=AssertionError("compare queried the database")),
			patch(
				"benchpress.docker_manager.get_client",
				side_effect=AssertionError("compare asked the daemon"),
			),
		):
			drift = self.drift([], [_container()])

		self.assertEqual(len(drift["orphan_containers"]), 1)


class TestConfiguredGraceWindow(IntegrationTestCase):
	def _set_window(self, value):
		before = frappe.db.get_single_value("BenchPress Settings", "orphan_grace_minutes")
		frappe.db.set_single_value("BenchPress Settings", "orphan_grace_minutes", value)
		frappe.clear_cache(doctype="BenchPress Settings")
		self.addCleanup(frappe.clear_cache, doctype="BenchPress Settings")
		self.addCleanup(frappe.db.set_single_value, "BenchPress Settings", "orphan_grace_minutes", before)

	def test_an_unset_window_falls_back_to_fifteen(self):
		self._set_window(0)

		self.assertEqual(configured_grace_minutes(), DEFAULT_GRACE_MINUTES)

	def test_the_setting_is_what_compare_uses(self):
		self._set_window(120)

		drift = compare([], [_container(age_minutes=60)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual(len(drift["in_grace"]), 1)

	def test_the_window_matches_the_admission_claim_grace(self):
		"""Both exist because a deploy that has not written its row is still a deploy."""
		from benchpress.credits import admission_repair

		self.assertEqual(reconcile.DEFAULT_GRACE_MINUTES, admission_repair.CLAIM_GRACE_MINUTES)
