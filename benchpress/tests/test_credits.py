# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 4 measures and records; nothing refuses anyone yet (that is phase 5).

So the assertions here are about arithmetic and bookkeeping: a session is charged for exactly the
hours it ran, every transition leaves an audit row whose signed sum is the balance, and the same
transition arriving twice is charged once.

The most important test in the module is `test_nothing_exists_when_credits_are_off`. A self-hoster
must never discover that credits exist — no account row, no ledger row, no extra query — and the
whole rest of the suite runs with the switch in exactly that position.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, flt, now_datetime

from benchpress import api, deploy_manager
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, metering, reconcile
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
LEDGER = "Credit Ledger Entry"
BENCHPRESS_SETTINGS = "BenchPress Settings"

# The seeded "Small" size: 1g / 1 core / 1.0 credits per hour.
RATE = 1.0
GRANT = 40.0
BUILD_CREDITS = 40.0
USER = "credits-owner@example.com"


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Credits Owner",
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id: str, owner: str) -> object:
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": f"Credits {lab_id}",
				"frappe_version": "version-15",
				"image_tag": "benchpress/test:latest",
				"memory_limit": "1g",
				"cpu_cores": 1,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


def _ensure_bench(lab, owner: str, **extra) -> object:
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists("Bench Instance", name):
		frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Running",
				"container_id": "credits-container",
				**extra,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestCredits(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.user = _ensure_user(USER)
		cls.lab = _ensure_lab("credits-lab", cls.user)
		cls.bench = _ensure_bench(cls.lab, cls.user)
		# A second real instance: `Credit Ledger Entry.reference_name` is a Dynamic Link, so a
		# made-up bench name would fail link validation rather than test anything. Stopped, so
		# the reconciliation sweep expects nothing from it.
		cls.other_lab = _ensure_lab("credits-lab-other", cls.user)
		cls.other_bench = _ensure_bench(cls.other_lab, cls.user, status="Stopped")
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for bench in (cls.bench, cls.other_bench):
			frappe.delete_doc("Bench Instance", bench.name, force=True, ignore_permissions=True)
		for lab in (cls.lab, cls.other_lab):
			frappe.delete_doc("Lab", lab.name, force=True, ignore_permissions=True)
		cls.wipe_credits()
		if frappe.db.exists("User", cls.user):
			frappe.delete_doc("User", cls.user, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- fixtures were committed, so the cleanup must be too
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		config.clear_size_index()
		self.wipe_credits()
		self.reset_bench()

	@staticmethod
	def purge_build_logs(lab_name: str) -> None:
		"""A build commits every line it writes, so no rollback removes its log."""
		frappe.db.delete("Build Log", {"lab": lab_name})
		frappe.db.commit()  # nosemgrep -- undoing a committed row takes a commit

	# --- The switch off means the feature does not exist ----------------------

	def test_this_module_leaves_the_switch_where_it_found_it(self):
		"""Nothing else in this repo's suite may run with metering armed by accident.

		`deploy_manager` commits mid-pipeline, so a test here can make its own switch value
		durable; the restore has to be durable too. Compared against the value read before any
		test ran, and read from the database rather than the cached Single, because a leak shows
		up in exactly those two places.
		"""
		self.assertEqual(
			frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits"),
			self.switch_at_start,
		)

	def test_nothing_exists_when_credits_are_off(self):
		self.set_credits_enabled(0)
		bench = self.running_bench()
		metering.on_bench_running(bench)
		metering.on_bench_stopped(bench)
		metering.on_image_built(frappe.get_doc("Lab", self.lab.name))
		account.start_burn(self.user, bench.name, RATE)
		account.grant(self.user, 10, "should not happen")
		account.charge(self.user, 10, "should not happen")

		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))
		self.assertEqual(self.entry_count(), 0)
		self.assertEqual(account.summary(self.user), {"enabled": False})
		self.assertFalse(account.statement(self.user)["enabled"])
		self.assertIsNone(api.get_lab(self.lab.name)["credits_per_hour"])

	# --- The arithmetic -------------------------------------------------------

	def test_a_new_account_starts_with_the_signup_grant(self):
		self.enable_credits()
		self.assertEqual(account.ensure_account(self.user), self.user)
		self.assertEqual(self.balance(), GRANT)
		self.assertEqual(self.entries()[0].entry_type, "Grant")

	def test_settle_twice_in_a_row_is_idempotent(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=3)

		doc = frappe.get_doc(ACCOUNT, self.user)
		self.assertAlmostEqual(account.settle(doc), 3 * RATE, places=3)
		self.assertAlmostEqual(account.settle(doc), 0.0, places=3)
		self.assertAlmostEqual(doc.balance, GRANT - 3 * RATE, places=3)

	def test_a_three_hour_session_debits_exactly_three_times_the_rate(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=3)
		account.stop_burn(self.user, self.bench.name, RATE)

		self.assertAlmostEqual(self.balance(), GRANT - 3 * RATE, places=3)
		self.assertEqual(self.burn_rate(), 0.0)

	def test_a_session_writes_exactly_two_ledger_rows_and_they_sum_to_the_balance(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=3)
		account.stop_burn(self.user, self.bench.name, RATE)

		usage = [entry for entry in self.entries() if entry.entry_type == "Usage"]
		self.assertEqual(len(usage), 2, "a session is one start row and one stop row")
		self.assertEqual(usage[0].credits, 0.0, "nothing has accrued at the moment of starting")
		self.assertAlmostEqual(usage[1].credits, -3 * RATE, places=3)
		self.assertAlmostEqual(sum(flt(entry.credits) for entry in self.entries()), self.balance(), places=3)
		self.assertAlmostEqual(usage[1].balance_after, self.balance(), places=3)

	def test_the_live_balance_falls_while_an_instance_runs(self):
		"""`available` is arithmetic on the burn rate — no row is written as time passes."""
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=2)

		row = frappe.db.get_value(ACCOUNT, self.user, account.BALANCE_FIELDS, as_dict=True)
		self.assertAlmostEqual(account.available(row), GRANT - 2 * RATE, places=3)
		self.assertEqual(row.balance, GRANT, "the stored balance is only touched by a settle")

	def test_two_starts_never_lose_an_update(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		account.start_burn(self.user, self.other_bench.name, RATE)
		self.assertEqual(self.burn_rate(), 2 * RATE)

	def test_the_account_row_is_read_for_update(self):
		"""The double-spend guard: two parallel deploys must not read the same balance."""
		self.enable_credits()
		account.ensure_account(self.user)
		with patch("frappe.db.get_value", wraps=frappe.db.get_value) as get_value:
			account.start_burn(self.user, self.bench.name, RATE)
		locking = [call for call in get_value.call_args_list if call.kwargs.get("for_update")]
		self.assertTrue(locking, "the account was read without FOR UPDATE")

	def test_an_account_is_never_opened_by_a_read(self):
		self.enable_credits()
		self.assertEqual(account.summary(self.user)["balance"], 0.0)
		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))

	def test_the_summary_carries_the_allocation_the_meter_gauges_against(self):
		"""The denominator holds still while the balance under it falls — a gauge, not a graph."""
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=2)

		summary = account.summary(self.user)
		self.assertAlmostEqual(summary["allocated"], GRANT, places=3)
		self.assertAlmostEqual(summary["balance"], GRANT - 2 * RATE, places=3)

	def test_the_allocation_survives_the_settle_that_spends_it(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		self.backdate_burn(hours=2)
		account.stop_burn(self.user, self.bench.name, RATE)

		self.assertAlmostEqual(account.summary(self.user)["allocated"], GRANT, places=3)

	def test_a_top_up_raises_the_allocation_and_a_refund_lowers_it(self):
		self.enable_credits()
		reference = ("Bench Instance", self.bench.name)
		account.purchase(self.user, 200, "Pack", reference)
		self.assertAlmostEqual(account.summary(self.user)["allocated"], GRANT + 200, places=3)

		account.refund(self.user, 200, "Chargeback", reference)
		self.assertAlmostEqual(account.summary(self.user)["allocated"], GRANT, places=3)

	def test_an_account_that_does_not_exist_gauges_against_nothing(self):
		self.enable_credits()
		self.assertEqual(account.summary(self.user)["allocated"], 0.0)

	def test_the_summary_costs_one_query(self):
		self.enable_credits()
		account.ensure_account(self.user)
		account.summary(self.user)  # warm the settings cache the gate reads
		with self.assertQueryCount(1):
			account.summary(self.user)

	def test_the_statement_never_sums_the_ledger(self):
		self.enable_credits()
		account.start_burn(self.user, self.bench.name, RATE)
		statement = account.statement(self.user, limit_start=0, limit_page_length=1)
		self.assertEqual(len(statement["rows"]), 1)
		self.assertEqual(statement["total"], 2, "grant plus start row")
		# Not exactly the grant: the instance has been burning since the row above was written.
		self.assertAlmostEqual(statement["summary"]["balance"], GRANT, places=3)

	def test_the_ledger_cannot_be_rewritten(self):
		self.enable_credits()
		account.grant(self.user, 5, "for the audit")
		entry = frappe.get_doc(LEDGER, self.entries()[0].name)
		entry.credits = 500
		self.assertRaises(frappe.ValidationError, entry.save)

	# --- The lifecycle wiring -------------------------------------------------

	def test_a_running_instance_burns_at_its_size_rate(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		self.assertEqual(self.burn_rate(), RATE)
		self.assertTrue(frappe.db.get_value("Bench Instance", bench.name, "credit_burn_started"))

	def test_starting_the_same_instance_twice_adds_the_rate_once(self):
		"""A redeploy, or a restart that interrupted nothing, must not double the rate."""
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		metering.on_bench_running(bench)
		self.assertEqual(self.burn_rate(), RATE)

	def test_stopping_an_instance_that_never_burnt_is_free(self):
		self.enable_credits()
		metering.on_bench_stopped(self.running_bench())
		self.assertEqual(self.entry_count(), 0)

	def test_a_failed_deploy_settles_the_time_it_ran_and_charges_nothing_further(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		self.backdate_burn(hours=1)

		metering.on_bench_stopped(bench)
		settled = self.balance()
		self.assertAlmostEqual(settled, GRANT - RATE, places=3)

		metering.on_bench_stopped(bench)  # the cleanup path can fire twice
		self.assertEqual(self.balance(), settled)
		self.assertEqual(self.burn_rate(), 0.0)

	def test_a_cache_hit_build_writes_no_usage_row(self):
		self.enable_credits()
		lab = frappe.get_doc("Lab", self.lab.name)
		with patch.object(deploy_manager.image_cache, "resolve", return_value=("cached:tag", True)):
			deploy_manager._prepare_lab_image(lab, MagicMock(), frappe.session.user)
		self.assertEqual(self.entry_count(), 0)

	def test_a_cache_miss_build_writes_exactly_one_usage_row(self):
		self.enable_credits()
		lab = frappe.get_doc("Lab", self.lab.name)
		with (
			patch.object(deploy_manager.image_cache, "resolve", return_value=("fresh:tag", False)),
			patch.object(deploy_manager, "build_lab_image", return_value="fresh:tag"),
		):
			deploy_manager._prepare_lab_image(lab, MagicMock(), frappe.session.user)
		self.addCleanup(self.purge_build_logs, lab.name)

		entries = [entry for entry in self.entries() if entry.entry_type == "Usage"]
		self.assertEqual(len(entries), 1)
		self.assertEqual(entries[0].credits, -BUILD_CREDITS)
		self.assertAlmostEqual(self.balance(), GRANT - BUILD_CREDITS, places=3)

	# --- The daily drift check ------------------------------------------------

	def test_reconciliation_corrects_a_rate_no_running_instance_justifies(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		# A container that died without a stop_burn: the rate is now twice what runs.
		frappe.db.set_value(ACCOUNT, self.user, "burn_rate", 2 * RATE, update_modified=False)
		self.backdate_burn(hours=1)

		result = reconcile.reconcile_burn_rates()

		self.assertIn(self.user, result["corrected"])
		self.assertEqual(self.burn_rate(), RATE)
		self.assertAlmostEqual(self.balance(), GRANT - 2 * RATE, places=3)

	def test_reconciliation_leaves_a_correct_account_alone(self):
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.assertEqual(reconcile.reconcile_burn_rates()["corrected"], [])

	def test_reconciliation_never_calls_docker(self):
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		with patch("benchpress.docker_manager.get_client") as get_client:
			reconcile.reconcile_burn_rates()
		get_client.assert_not_called()

	def test_reconciliation_clears_the_flag_on_an_instance_that_is_not_running(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		frappe.db.set_value("Bench Instance", bench.name, "status", "Stopped", update_modified=False)

		reconcile.reconcile_burn_rates()

		self.assertIsNone(frappe.db.get_value("Bench Instance", bench.name, "credit_burn_started"))
		self.assertEqual(self.burn_rate(), 0.0)

	def test_expected_rates_do_not_scale_in_query_count(self):
		"""The sweep is two plucks and a dict, never a `get_doc` per instance."""
		self.enable_credits()
		reconcile.expected_burn_rates()  # warm the DocType meta this would otherwise count
		config.clear_size_index()
		one = self.count_queries(reconcile.expected_burn_rates)

		extra = [_ensure_lab(f"credits-lab-{index}", self.user) for index in range(2)]
		benches = [_ensure_bench(lab, self.user) for lab in extra]
		self.addCleanup(self.delete_docs, "Bench Instance", [bench.name for bench in benches])
		self.addCleanup(self.delete_docs, "Lab", [lab.name for lab in extra])

		config.clear_size_index()
		self.assertEqual(self.count_queries(reconcile.expected_burn_rates), one)

	# --- Helpers --------------------------------------------------------------

	def enable_credits(self) -> None:
		self.set_credits_enabled(1)

	def set_credits_enabled(self, value: int) -> None:
		"""One cleanup, not two: `addCleanup` runs LIFO, so a separate `clear_cache` would fire
		*before* the value was restored and leave the switch stuck on for every later test."""
		original = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		self.addCleanup(self.write_credits_switch, original)
		self.write_credits_switch(value)

	def write_credits_switch(self, value) -> None:
		"""Committed, because the code under test commits.

		`deploy_manager` commits mid-pipeline, which makes this test's pending switch value
		durable. If the restore then rode on the per-test rollback it would be thrown away, and
		every later test in the suite would run with metering armed.
		"""
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.db.commit()  # nosemgrep -- see above: the restore must outlive the rollback
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def running_bench(self):
		return frappe.get_doc("Bench Instance", self.bench.name)

	def reset_bench(self) -> None:
		frappe.db.set_value(
			"Bench Instance",
			self.bench.name,
			{"credit_burn_rate": 0.0, "credit_burn_started": None, "status": "Running"},
			update_modified=False,
		)

	def backdate_burn(self, hours: int) -> None:
		frappe.db.set_value(
			ACCOUNT,
			self.user,
			"burn_since",
			add_to_date(now_datetime(), hours=-hours),
			update_modified=False,
		)

	def balance(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, self.user, "balance"))

	def burn_rate(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, self.user, "burn_rate"))

	def entry_count(self) -> int:
		"""Scoped to the fixture user: a real site may already carry credit rows of its own."""
		return frappe.db.count(LEDGER, {"account": self.user})

	def entries(self) -> list:
		return frappe.get_all(
			LEDGER,
			filters={"account": self.user},
			fields=["name", "entry_type", "credits", "balance_after"],
			order_by="creation asc",
		)

	def count_queries(self, action) -> int:
		count = 0
		original = frappe.db.__class__.sql

		def counting_sql(*args, **kwargs):
			nonlocal count
			count += 1
			return original(*args, **kwargs)

		frappe.db.__class__.sql = counting_sql
		try:
			action()
		finally:
			frappe.db.__class__.sql = original
		return count

	def delete_docs(self, doctype: str, names: list) -> None:
		for name in names:
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	@classmethod
	def wipe_credits(cls) -> None:
		"""The ledger blocks updates, not deletes — the suite still has to clean up after itself.

		Committed for the same reason as the switch: a test whose pipeline committed left real
		rows behind, and a rolled-back delete would let them reappear.
		"""
		frappe.db.delete(LEDGER, {"account": USER})
		frappe.db.delete(ACCOUNT, {"user": USER})
		frappe.db.commit()  # nosemgrep -- fixture cleanup must outlive the per-test rollback
