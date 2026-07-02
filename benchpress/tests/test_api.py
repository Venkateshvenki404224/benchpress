# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import time

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import api

BUDGETS_MS = {
	"get_labs": 500,
	"get_user_context": 250,
}


def _timed(function):
	start = time.perf_counter()
	result = function()
	elapsed_ms = (time.perf_counter() - start) * 1000
	return result, elapsed_ms


class TestApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	def assert_within_budget(self, endpoint, elapsed_ms):
		self.assertLess(
			elapsed_ms,
			BUDGETS_MS[endpoint],
			f"{endpoint} took {elapsed_ms:.0f}ms, budget is {BUDGETS_MS[endpoint]}ms",
		)

	def test_get_labs_shape_and_timing(self):
		labs, elapsed_ms = _timed(api.get_labs)
		self.assertIsInstance(labs, list)
		for lab in labs:
			self.assertIn("app_names", lab)
			self.assertIn("app_count", lab)
			self.assertIn("bench_count", lab)
		self.assert_within_budget("get_labs", elapsed_ms)

	def test_get_user_context_shape_and_timing(self):
		context, elapsed_ms = _timed(api.get_user_context)
		for key in ("is_admin", "user", "roles"):
			self.assertIn(key, context)
		self.assert_within_budget("get_user_context", elapsed_ms)
