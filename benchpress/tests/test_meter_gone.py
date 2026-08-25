# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The accrual engine is gone, and nothing it touched moved on the way out.

Half of these assert an absence: a name that no longer resolves, a column that no longer
exists, a balance that is a stored number rather than a moving one. A scan of the source is a
fair test when the property under test is "this is gone" — nothing else can prove that no call
path reaches a function.

The other half is what the deletion must not break. The ledger still sums to every balance,
which is the invariant `account.py` was built around and the one a field drop could quietly
violate. And anybody who bought prepaid time still holds it, as a lease.

This module names the retired identifiers, so the scan skips it, and skips `patches/` — the
migration has to name what it removes.
"""

import re
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, today

from benchpress.credits import account, lease
from benchpress.patches import drop_burn_fields, retire_always_on_passes

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"
BENCHPRESS_SETTINGS = "BenchPress Settings"
USER = "meter-gone@example.com"

# Every name the accrual engine went by. `settle` is matched only where it meant a meter:
# `payments.settle_order` settles a Razorpay order and stays.
RETIRED = (
	r"\bstart_burn\b",
	r"\bstop_burn\b",
	r"\bcorrect_burn_rate\b",
	r"\baccrued\b",
	r"\bburn_rate\b",
	r"\bburn_since\b",
	r"\bcredit_burn_rate\b",
	r"\bcredit_burn_started\b",
	r"\bttl_warned_at\b",
	r"\bmax_run_hours\b",
	r"\balways_on_monthly_inr\b",
	r"\bhas_active_pass\b",
	r"\bactive_pass_\w+\b",
	r"\bdef settle\(",
	r"\baccount\.settle\b",
)

SCANNED_SUFFIXES = (".py", ".json")
SKIPPED = ("patches", "tests/test_meter_gone.py")


def _scanned_files() -> list[Path]:
	root = Path(frappe.get_app_path("benchpress"))
	paths = []
	for path in root.rglob("*"):
		if path.suffix not in SCANNED_SUFFIXES or "__pycache__" in path.parts:
			continue
		if str(path.relative_to(root)).startswith(SKIPPED):
			continue
		paths.append(path)
	return paths


def _offenders() -> list[str]:
	found = []
	for path in _scanned_files():
		body = path.read_text(encoding="utf-8", errors="ignore")
		found += [f"{path.name}: {pattern}" for pattern in RETIRED if re.search(pattern, body)]
	return sorted(found)


def _columns(doctype: str) -> set[str]:
	return {row[0] for row in frappe.db.describe(doctype)}


class TestMeterGone(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	# --- No code path can start a burn ----------------------------------------

	def test_no_source_file_names_the_accrual_engine(self):
		self.assertEqual(_offenders(), [], "the accrual engine is still named in the app")

	def test_the_accrual_api_no_longer_resolves(self):
		for name in ("start_burn", "stop_burn", "settle", "correct_burn_rate", "accrued"):
			self.assertFalse(hasattr(account, name), f"account.{name} still exists")

	def test_the_pass_module_is_gone(self):
		with self.assertRaises(ImportError):
			from benchpress.credits import passes

	def test_the_reconciler_is_gone(self):
		with self.assertRaises(ImportError):
			from benchpress.credits import reconcile

	def test_nothing_is_scheduled_to_repair_a_rate(self):
		from benchpress import hooks

		self.assertNotIn("credits.reconcile", str(hooks.scheduler_events))

	# --- No field records one -------------------------------------------------

	def test_the_burn_columns_are_gone_from_the_schema(self):
		for doctype, fields in drop_burn_fields.RETIRED.items():
			self.assertEqual(
				_columns(doctype) & set(fields), set(), f"{doctype} still carries a retired column"
			)

	def test_the_pass_table_is_gone(self):
		self.assertFalse(frappe.db.table_exists(retire_always_on_passes.PASS))

	def test_dropping_the_burn_fields_says_nothing_the_second_time(self):
		self.assertEqual(drop_burn_fields.execute(), [])

	def test_converting_passes_says_nothing_the_second_time(self):
		self.assertEqual(retire_always_on_passes.convert_live_passes(), [])

	# --- `available()` is the balance ------------------------------------------

	def test_available_is_the_stored_balance(self):
		self.assertEqual(account.available(frappe._dict(balance=12.5, is_suspended=0)), 12.5)

	def test_a_leftover_burn_field_no_longer_moves_a_balance(self):
		"""A row read from a site whose columns the patch has not reached yet still reports what it stores."""
		row = frappe._dict(balance=12.5, burn_rate=4.0, burn_since="2026-01-01 00:00:00")
		self.assertEqual(account.available(row), 12.5)

	def test_neither_read_path_asks_for_a_rate(self):
		for field in ("burn_rate", "burn_since"):
			self.assertNotIn(field, account.BALANCE_FIELDS)
			self.assertNotIn(field, account.SUMMARY_FIELDS)

	# --- The ledger still balances ---------------------------------------------

	def test_every_ledger_sums_to_its_account_balance(self):
		self.enable_credits()
		self.ensure_user()
		account.grant(USER, 40.0, "Ledger check grant")
		account.charge(USER, 5.0, "Ledger check lease")
		rows = frappe.get_all(ACCOUNT, fields=["name", "balance"])
		self.assertTrue(rows, "nothing was asserted: no account exists")
		for row in rows:
			posted = frappe.get_all(LEDGER, filters={"account": row.name}, pluck="credits")
			self.assertAlmostEqual(
				flt(row.balance), sum(flt(value) for value in posted), places=6, msg=f"{row.name} drifted"
			)

	# --- The pass is gone without stranding anyone ------------------------------

	def test_a_pass_becomes_a_lease_that_outlasts_it(self):
		now = lease.now_ts()
		self.assertGreaterEqual(
			retire_always_on_passes.lease_deadline(add_days(today(), 12), now), now + 12 * 86400
		)

	def test_a_pass_expiring_today_is_worth_the_rest_of_today(self):
		now = lease.now_ts()
		self.assertGreater(retire_always_on_passes.lease_deadline(today(), now), now)

	def test_a_lapsed_pass_buys_no_time(self):
		now = lease.now_ts()
		self.assertEqual(retire_always_on_passes.lease_deadline(add_days(today(), -3), now), now)

	# --- Helpers ---------------------------------------------------------------

	def ensure_user(self) -> None:
		"""`Credit Account.user` is a Link, so the account needs somebody to belong to."""
		if frappe.db.exists("User", USER):
			return
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Meter Gone",
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
			}
		).insert(ignore_permissions=True)

	def enable_credits(self) -> None:
		"""Arm the switch for one test, inside its transaction.

		Nothing here commits, so the rollback restores the value; only the cached Single has to
		be dropped by hand, on the way in and on the way out.
		"""
		self.addCleanup(frappe.clear_cache, doctype=BENCHPRESS_SETTINGS)
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", 1)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)
