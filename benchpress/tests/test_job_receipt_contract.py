"""`Job Receipt` module-level tests — pure logic, no Frappe DB (that lives in
`benchpress/tests/test_job_receipt_integration.py` once a bench DB is available for CI).

These assert the five-part contract directly against the implementation functions using a
minimal in-memory fake of the two `frappe` calls `job_receipt.py` touches, so the shape of
the pattern (mint-before-enqueue, checker-owns-status, unknown-not-failed) is pinned down
even without a live site.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock


class _FakeDoc:
	def __init__(self, name, logical_id):
		self.name = name
		self.logical_id = logical_id
		self.expected_effect = None
		self.status = "Pending"
		self.minted_at = None
		self.claimed_at = None
		self.completed_at = None

	def insert(self, ignore_permissions=True):
		self._store[self.logical_id] = self
		return self

	def save(self, ignore_permissions=True):
		return self


class TestJobReceiptContract(unittest.TestCase):
	"""Exercises job_receipt.py against a fake `frappe` module injected into sys.modules."""

	def setUp(self):
		self.store = {}
		self.fake_frappe = types.ModuleType("frappe")
		self.fake_frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})

		def new_doc(doctype):
			doc = _FakeDoc(name=f"fake-{len(self.store)}", logical_id=None)
			doc._store = self.store
			return doc

		def db_get_value(doctype, filters, field):
			lid = filters.get("logical_id") if isinstance(filters, dict) else None
			doc = self.store.get(lid)
			return doc.name if doc else None

		def db_exists(doctype, filters):
			lid = filters.get("logical_id") if isinstance(filters, dict) else None
			return lid in self.store

		def get_doc(doctype, name):
			for doc in self.store.values():
				if doc.name == name:
					return doc
			raise self.fake_frappe.DoesNotExistError(name)

		self.fake_frappe.new_doc = new_doc
		self.fake_frappe.db = MagicMock(get_value=db_get_value, exists=db_exists)
		self.fake_frappe.get_doc = get_doc
		self.fake_frappe.log_error = MagicMock()

		fake_utils = types.ModuleType("frappe.utils")
		fake_utils.now_datetime = MagicMock(return_value="2026-10-02T00:00:00")
		self.fake_frappe.utils = fake_utils

		sys.modules["frappe"] = self.fake_frappe
		sys.modules["frappe.utils"] = fake_utils

		import importlib

		import benchpress.job_receipt as jr

		importlib.reload(jr)
		self.jr = jr

	def tearDown(self):
		sys.modules.pop("frappe", None)
		sys.modules.pop("frappe.utils", None)

	def _mint(self, lid="route_sync:bench-1", effect="route written"):
		self.jr.mint(lid, effect)
		return lid

	def test_mint_is_idempotent_on_logical_id(self):
		lid = self._mint()
		self.jr.mint(lid, "a different effect string")
		self.assertEqual(len(self.store), 1, "second mint() with same id must not open a second row")

	def test_mint_before_enqueue_row_is_pending(self):
		lid = self._mint()
		self.assertEqual(self.store[lid].status, "Pending")

	def test_mark_completed_requires_an_existing_row(self):
		with self.assertRaises(self.fake_frappe.DoesNotExistError):
			self.jr.mark_completed("never-minted")

	def test_mark_completed_sets_completed_and_is_idempotent(self):
		lid = self._mint()
		self.jr.mark_completed(lid)
		self.assertEqual(self.store[lid].status, "Completed")
		# Re-running the checker's own successful write must not raise or re-stamp timestamps
		first_completed_at = self.store[lid].completed_at
		self.jr.mark_completed(lid)
		self.assertEqual(self.store[lid].completed_at, first_completed_at)

	def test_overdue_pending_becomes_unknown_not_failed(self):
		lid = self._mint()
		status = self.jr.mark_unknown_if_overdue(lid)
		self.assertEqual(status, "Unknown")
		self.assertEqual(self.store[lid].status, "Unknown")

	def test_overdue_check_is_a_noop_once_completed(self):
		lid = self._mint()
		self.jr.mark_completed(lid)
		status = self.jr.mark_unknown_if_overdue(lid)
		self.assertEqual(
			status, "Completed", "a job that already completed must not be downgraded to Unknown"
		)

	def test_mark_failed_requires_an_observed_signal_and_logs(self):
		lid = self._mint()
		self.jr.mark_failed(lid, "RQ worker record shows dead process")
		self.assertEqual(self.store[lid].status, "Failed")
		self.fake_frappe.log_error.assert_called_once()


if __name__ == "__main__":
	unittest.main()
