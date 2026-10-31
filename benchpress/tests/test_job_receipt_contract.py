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
		self.expected_hash = None
		self.status = "Pending"
		self.minted_at = None
		self.claimed_at = None
		self.completed_at = None
		self.policy_hash = None
		self.reconciliation_lapse_count = None
		self.reason_code = None

	def insert(self, ignore_permissions=True):
		self._store[self.logical_id] = self
		return self

	def save(self, ignore_permissions=True):
		return self


class TestJobReceiptContract(unittest.TestCase):
	"""Exercises job_receipt.py against a fake `frappe` module injected into sys.modules."""

	def setUp(self):
		self._real_modules = {
			name: sys.modules.get(name)
			for name in (
				"frappe",
				"frappe.utils",
				"frappe.desk",
				"frappe.desk.form",
				"frappe.desk.form.assign_to",
			)
		}

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
		fake_utils.add_to_date = MagicMock(
			side_effect=lambda dt, minutes=0, hours=0, **kw: f"{dt}-plus-{minutes or hours}"
		)
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
		for name, mod in self._real_modules.items():
			if mod is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = mod

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

	# --- content-hash check on completion (issue #444) ---

	def test_mark_completed_without_hashes_is_identity_only(self):
		"""No expected_hash minted, no actual_hash passed: unchanged legacy behavior."""
		lid = self._mint()
		self.jr.mark_completed(lid)
		self.assertEqual(self.store[lid].status, "Completed")

	def test_mark_completed_matching_hash_completes(self):
		lid = "route_sync:bench-hash-match"
		self.jr.mint(lid, "route written", expected_hash="abc123")
		self.jr.mark_completed(lid, actual_hash="abc123")
		self.assertEqual(self.store[lid].status, "Completed")

	def test_mark_completed_mismatched_hash_raises_and_does_not_complete(self):
		lid = "route_sync:bench-hash-mismatch"
		self.jr.mint(lid, "route written", expected_hash="abc123")
		with self.assertRaises(self.jr.ContentHashMismatchError):
			self.jr.mark_completed(lid, actual_hash="deadbeef")
		self.assertEqual(self.store[lid].status, "Pending")

	def test_mark_completed_expected_hash_without_actual_hash_falls_back_to_identity(self):
		"""A caller that minted expected_hash but can't supply actual_hash this call
		(e.g. a legacy call site not yet updated) must not be penalized — falls back
		to identity-only completion rather than raising on a missing comparison side."""
		lid = "route_sync:bench-hash-one-sided"
		self.jr.mint(lid, "route written", expected_hash="abc123")
		self.jr.mark_completed(lid)
		self.assertEqual(self.store[lid].status, "Completed")

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

	def test_mark_failed_without_reason_code_leaves_it_unset(self):
		lid = self._mint()
		self.jr.mark_failed(lid, "RQ worker record shows dead process")
		self.assertIsNone(getattr(self.store[lid], "reason_code", None))

	def test_mark_failed_stores_reason_code_in_same_save_call(self):
		lid = self._mint()
		self.jr.mark_failed(lid, "RQ worker record shows dead process", reason_code="worker_crash")
		self.assertEqual(self.store[lid].status, "Failed")
		self.assertEqual(self.store[lid].reason_code, "worker_crash")

	def test_mark_failed_rejects_unknown_reason_code(self):
		lid = self._mint()
		with self.assertRaises(ValueError):
			self.jr.mark_failed(lid, "RQ worker record shows dead process", reason_code="made_up")

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

	# --- sweep_overdue_reconciliation() (Hive TASK-10886, Moltbook d1670e43/f3751d86) ---

	def test_sweep_reconciliation_re_escalates_lapsed_todo(self):
		"""An Unknown receipt whose ToDo deadline has already passed gets cancelled +
		re-assigned with a fresh deadline, rather than sitting unread forever."""
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		doc = self.store[lid]

		lapsed_todo = {"name": "todo-1", "allocated_to": "ops@example.com", "date": "2000-01-01"}
		set_value_calls = []

		def get_all(doctype, filters=None, fields=None, pluck=None):
			if doctype == self.jr.DOCTYPE:
				return [
					{"name": doc.name, "logical_id": doc.logical_id, "expected_effect": doc.expected_effect}
				]
			if doctype == "ToDo":
				return [lapsed_todo]
			return []

		def db_set_value(doctype, name, field, value):
			set_value_calls.append((doctype, name, field, value))

		self.fake_frappe.get_all = get_all
		self.fake_frappe.db.set_value = db_set_value

		result = self.jr.sweep_overdue_reconciliation()

		self.assertEqual(result["checked"], 1)
		self.assertEqual(result["re_escalated"], [lid])
		self.assertIn(("ToDo", "todo-1", "status", "Cancelled"), set_value_calls)
		self.assertEqual(
			self.assign_to_add.call_count, 2, "once on the original Unknown transition, once on re-escalation"
		)
		second_call_kwargs = self.assign_to_add.call_args_list[-1][0][0]
		self.assertEqual(second_call_kwargs["assign_to"], ["ops@example.com"])
		self.assertIn("past its reconciliation deadline", second_call_kwargs["description"])

	def test_sweep_reconciliation_skips_unknown_without_lapsed_todo(self):
		"""An Unknown receipt whose ToDo deadline has NOT yet passed must not be touched —
		this sweep only acts once the obligation is genuinely overdue."""
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		doc = self.store[lid]

		def get_all(doctype, filters=None, fields=None, pluck=None):
			if doctype == self.jr.DOCTYPE:
				return [
					{"name": doc.name, "logical_id": doc.logical_id, "expected_effect": doc.expected_effect}
				]
			if doctype == "ToDo":
				return []  # no OPEN todo past its deadline
			return []

		self.fake_frappe.get_all = get_all
		before_assign_calls = self.assign_to_add.call_count

		result = self.jr.sweep_overdue_reconciliation()

		self.assertEqual(result["checked"], 1)
		self.assertEqual(result["re_escalated"], [])
		self.assertEqual(
			self.assign_to_add.call_count,
			before_assign_calls,
			"must not re-escalate when nothing is actually overdue",
		)

	# --- severity tiering + false-positive measurement (Hive TASK-10899,
	# spiritofthefleet's two named gaps on sweep_overdue_reconciliation) ---

	def test_severity_is_routine_below_warn_threshold(self):
		self.assertEqual(self.jr._reconciliation_severity(1), "routine")

	def test_severity_is_warn_at_threshold(self):
		self.assertEqual(self.jr._reconciliation_severity(self.jr.RECONCILE_SEVERITY_WARN_AT), "warn")

	def test_severity_is_critical_at_threshold(self):
		self.assertEqual(self.jr._reconciliation_severity(self.jr.RECONCILE_SEVERITY_CRITICAL_AT), "critical")

	def test_sweep_reconciliation_increments_lapse_count_and_tags_severity(self):
		"""First lapse on a receipt must be tagged routine and persist lapse_count=1 —
		this is the baseline the severity-tiering gap required (every lapse was
		previously treated identically, with no durable count at all)."""
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		doc = self.store[lid]
		self.assertEqual(doc.reconciliation_lapse_count, None)  # fake doc default; never set yet

		lapsed_todo = {"name": "todo-1", "allocated_to": "ops@example.com", "date": "2000-01-01"}
		set_value_calls = []

		def get_all(doctype, filters=None, fields=None, pluck=None):
			if doctype == self.jr.DOCTYPE:
				return [
					{
						"name": doc.name,
						"logical_id": doc.logical_id,
						"expected_effect": doc.expected_effect,
						"reconciliation_lapse_count": doc.reconciliation_lapse_count,
					}
				]
			if doctype == "ToDo":
				return [lapsed_todo]
			return []

		def db_set_value(doctype, name, field, value):
			set_value_calls.append((doctype, name, field, value))
			if doctype == self.jr.DOCTYPE and field == "reconciliation_lapse_count":
				doc.reconciliation_lapse_count = value

		self.fake_frappe.get_all = get_all
		self.fake_frappe.db.set_value = db_set_value

		result = self.jr.sweep_overdue_reconciliation()

		self.assertEqual(result["re_escalated"], [lid])
		self.assertIn((self.jr.DOCTYPE, doc.name, "reconciliation_lapse_count", 1), set_value_calls)
		last_description = self.assign_to_add.call_args_list[-1][0][0]["description"]
		self.assertIn("[routine]", last_description)
		self.assertIn("lapse #1", last_description)

	def test_sweep_reconciliation_escalates_to_warn_on_second_lapse(self):
		"""A receipt that lapses a second time (lapse_count becomes 2, the configured
		WARN threshold) must be tagged warn, not routine — this is exactly the
		one-time-slip-vs-ignored-pattern distinction spiritofthefleet named as missing."""
		lid = self._mint()
		self.jr.mark_unknown_if_overdue(lid)
		doc = self.store[lid]
		doc.reconciliation_lapse_count = 1  # simulate one prior lapse already recorded

		lapsed_todo = {"name": "todo-2", "allocated_to": "ops@example.com", "date": "2000-01-01"}

		def get_all(doctype, filters=None, fields=None, pluck=None):
			if doctype == self.jr.DOCTYPE:
				return [
					{
						"name": doc.name,
						"logical_id": doc.logical_id,
						"expected_effect": doc.expected_effect,
						"reconciliation_lapse_count": doc.reconciliation_lapse_count,
					}
				]
			if doctype == "ToDo":
				return [lapsed_todo]
			return []

		self.fake_frappe.get_all = get_all
		self.fake_frappe.db.set_value = MagicMock()

		self.jr.sweep_overdue_reconciliation()

		last_description = self.assign_to_add.call_args_list[-1][0][0]["description"]
		self.assertIn("[warn]", last_description)
		self.assertIn("lapse #2", last_description)

	def test_measure_false_positive_rate_with_no_lapsed_receipts_returns_none_rate(self):
		self.fake_frappe.get_all = MagicMock(return_value=[])
		result = self.jr.measure_reconciliation_false_positive_rate()
		self.assertEqual(result["total_ever_lapsed"], 0)
		self.assertIsNone(result["resolved_without_escalation_rate"])

	def test_measure_false_positive_rate_buckets_resolved_vs_still_unresolved(self):
		rows = [
			{"name": "a", "logical_id": "a", "status": "Completed", "reconciliation_lapse_count": 1},
			{"name": "b", "logical_id": "b", "status": "Failed", "reconciliation_lapse_count": 2},
			{"name": "c", "logical_id": "c", "status": "Unknown", "reconciliation_lapse_count": 3},
		]
		self.fake_frappe.get_all = MagicMock(return_value=rows)
		result = self.jr.measure_reconciliation_false_positive_rate()
		self.assertEqual(result["total_ever_lapsed"], 3)
		self.assertEqual(result["resolved_without_escalation"], 2)
		self.assertEqual(result["still_unresolved"], 1)
		self.assertAlmostEqual(result["resolved_without_escalation_rate"], 2 / 3)


if __name__ == "__main__":
	unittest.main()
