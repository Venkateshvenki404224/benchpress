"""`Job Receipt` module-level tests — pure logic, no Frappe DB (that lives in
`benchpress/tests/test_job_receipt_integration.py` once a bench DB is available for CI).

These assert the five-part contract directly against the implementation functions using a
minimal in-memory fake of the two `frappe` calls `job_receipt.py` touches, so the shape of
the pattern (mint-before-enqueue, checker-owns-status, unknown-not-failed) is pinned down
even without a live site.

Also covers the policy-hash / requeue-vs-remediate contract added in TASK-03652.
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
		self.policy_hash = None

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
		self.fake_frappe.get_all = MagicMock(return_value=["Administrator"])
		self.fake_frappe.db = MagicMock(get_value=db_get_value, exists=db_exists)
		self.fake_frappe.get_doc = get_doc
		self.fake_frappe.log_error = MagicMock()

		fake_utils = types.ModuleType("frappe.utils")
		fake_utils.now_datetime = MagicMock(return_value="2026-10-02T00:00:00")
		fake_utils.add_to_date = MagicMock(side_effect=lambda dt, minutes=0, hours=0, **kw: f"{dt}-plus-{minutes or hours}")
		self.fake_frappe.utils = fake_utils

		fake_assign_to = types.ModuleType("frappe.desk.form.assign_to")
		self.assign_to_add = MagicMock()
		fake_assign_to.add = self.assign_to_add

		sys.modules["frappe"] = self.fake_frappe
		sys.modules["frappe.utils"] = fake_utils
		sys.modules["frappe.desk"] = types.ModuleType("frappe.desk")
		sys.modules["frappe.desk.form"] = types.ModuleType("frappe.desk.form")
		sys.modules["frappe.desk.form.assign_to"] = fake_assign_to

		import importlib

		import benchpress.job_receipt as jr

		importlib.reload(jr)
		self.jr = jr

	def tearDown(self):
		sys.modules.pop("frappe", None)
		sys.modules.pop("frappe.utils", None)
		sys.modules.pop("frappe.desk", None)
		sys.modules.pop("frappe.desk.form", None)
		sys.modules.pop("frappe.desk.form.assign_to", None)

	def _mint(self, lid="route_sync:bench-1", effect="route written", policy_hash=None):
		self.jr.mint(lid, effect, policy_hash=policy_hash)
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

	# --- reconciliation obligation on Unknown (TASK-03744) ---

	def test_unknown_transition_opens_a_reconciliation_assignment(self):
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		self.assign_to_add.assert_called_once()
		kwargs = self.assign_to_add.call_args.args[0]
		self.assertEqual(kwargs["doctype"], self.jr.DOCTYPE)
		self.assertEqual(kwargs["name"], self.store[lid].name)
		self.assertEqual(kwargs["assign_to"], ["Administrator"])
		self.assertIn("date", kwargs)

	def test_reconciliation_assignment_not_opened_twice_on_repeat_call(self):
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		self.jr.mark_unknown_if_overdue(lid)  # already Unknown: no-op per the Pending-only guard
		self.assign_to_add.assert_called_once()

	def test_reconciliation_assignment_not_opened_on_completion(self):
		lid = self._mint()
		self.jr.mark_completed(lid)
		self.jr.mark_unknown_if_overdue(lid)  # no-op: already Completed
		self.assign_to_add.assert_not_called()

	def test_open_reconciliation_obligation_rejects_non_unknown_doc(self):
		lid = self._mint()
		doc = self.store[lid]  # still Pending
		with self.assertRaises(ValueError):
			self.jr._open_reconciliation_obligation(doc)

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

	# --- policy_hash / requeue-vs-remediate tests (TASK-03652) ---

	def test_mint_stores_policy_hash(self):
		lid = self._mint(policy_hash="abc123")
		self.assertEqual(self.store[lid].policy_hash, "abc123")

	def test_mint_without_policy_hash_stores_none(self):
		lid = self._mint()
		self.assertIsNone(self.store[lid].policy_hash)

	def test_requeue_or_remediate_requeues_when_hashes_match(self):
		lid = self._mint(policy_hash="aabbcc")
		self.jr.mark_unknown_if_overdue(lid)
		result = self.jr.requeue_or_remediate(lid, current_policy_hash="aabbcc")
		self.assertEqual(result, "requeue")

	def test_requeue_or_remediate_remediates_when_hashes_differ(self):
		lid = self._mint(policy_hash="aabbcc")
		self.jr.mark_unknown_if_overdue(lid)
		result = self.jr.requeue_or_remediate(lid, current_policy_hash="ddeeff")
		self.assertEqual(result, "remediate")

	def test_requeue_or_remediate_requeues_when_neither_side_has_hash(self):
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		result = self.jr.requeue_or_remediate(lid, current_policy_hash=None)
		self.assertEqual(result, "requeue")

	def test_requeue_or_remediate_returns_unknown_when_hash_added_at_retry_time(self):
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		result = self.jr.requeue_or_remediate(lid, current_policy_hash="newhash")
		self.assertEqual(
			result,
			"unknown",
			"minted before policy_hash existed (no baseline) — this is an unresolvable "
			"migration-state gap, not a confirmed policy change, so it must not collapse "
			"into 'remediate'",
		)

	def test_requeue_or_remediate_remediates_when_hash_only_at_mint_time(self):
		lid = self._mint(policy_hash="oldhash")
		self.jr.mark_unknown_if_overdue(lid)
		result = self.jr.requeue_or_remediate(lid, current_policy_hash=None)
		self.assertEqual(result, "remediate", "minted with hash but current has none — context changed")

	def test_requeue_or_remediate_works_on_failed_receipts(self):
		lid = self._mint(policy_hash="abc")
		self.jr.mark_failed(lid, "worker crashed")
		result = self.jr.requeue_or_remediate(lid, current_policy_hash="abc")
		self.assertEqual(result, "requeue")

	def test_requeue_or_remediate_raises_on_pending(self):
		lid = self._mint(policy_hash="abc")
		with self.assertRaises(ValueError):
			self.jr.requeue_or_remediate(lid, current_policy_hash="abc")

	def test_requeue_or_remediate_raises_on_completed(self):
		lid = self._mint(policy_hash="abc")
		self.jr.mark_completed(lid)
		with self.assertRaises(ValueError):
			self.jr.requeue_or_remediate(lid, current_policy_hash="abc")

	def test_requeue_or_remediate_raises_on_unknown_logical_id(self):
		with self.assertRaises(self.fake_frappe.DoesNotExistError):
			self.jr.requeue_or_remediate("never-minted", current_policy_hash="abc")

	# --- sweep_overdue_pending() (TASK-03454/TASK-03719) ---

	def test_sweep_flips_overdue_pending_to_unknown(self):
		lid = self._mint()
		self.store[lid].minted_at = "2000-01-01T00:00:00"  # ancient, always overdue

		def get_all(doctype, filters=None, pluck=None):
			return [doc.logical_id for doc in self.store.values() if doc.status == "Pending"]

		self.fake_frappe.get_all = get_all
		result = self.jr.sweep_overdue_pending()
		self.assertEqual(result["checked"], 1)
		self.assertEqual(result["flipped_to_unknown"], [lid])
		self.assertEqual(self.store[lid].status, "Unknown")

	def test_sweep_does_not_touch_completed_or_already_unknown(self):
		completed_lid = self._mint(lid="route_sync:bench-2")
		self.jr.mark_completed(completed_lid)
		unknown_lid = self._mint(lid="route_sync:bench-3")
		self.jr.mark_unknown_if_overdue(unknown_lid)

		def get_all(doctype, filters=None, pluck=None):
			# A real query only ever returns Pending rows matching the filter; this fake
			# mirrors that by returning only genuinely-Pending logical_ids.
			return [doc.logical_id for doc in self.store.values() if doc.status == "Pending"]

		self.fake_frappe.get_all = get_all
		result = self.jr.sweep_overdue_pending()
		self.assertEqual(result["checked"], 0)
		self.assertEqual(self.store[completed_lid].status, "Completed")
		self.assertEqual(self.store[unknown_lid].status, "Unknown")


if __name__ == "__main__":
	unittest.main()
