# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The accounting core: one-off debits and credits, and the lifecycle sites that raise them.

The assertions here are about bookkeeping. A debit writes exactly one audit row, the signed sum
of an account's rows is its balance, and the same lifecycle transition arriving twice is charged
once. `test_lease` owns what a lease costs; this owns what the ledger records.

The most important test in the module is `test_nothing_exists_when_credits_are_off`. A self-hoster
must never discover that credits exist — no account row, no ledger row, no extra query — and the
whole rest of the suite runs with the switch in exactly that position.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from benchpress import api, deploy_manager
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, metering
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
ACCOUNT_TABLE = "tabCredit Account"
LEDGER = "Credit Ledger Entry"
BENCHPRESS_SETTINGS = "BenchPress Settings"

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
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
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

	def test_the_account_row_is_read_for_update(self):
		"""The double-spend guard: two parallel deploys must not read the same balance.

		Against the emitted SQL rather than a kwarg, because the lock and the document load are
		now one statement — see `_locked` for why a plain read after the lock is not the same row.
		"""
		self.enable_credits()
		account.ensure_account(self.user)
		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql:
			account.charge(self.user, 5, "Lease", ("Bench Instance", self.bench.name))
		statements = [str(call.args[0]) for call in sql.call_args_list if call.args]
		self.assertTrue(
			[
				statement
				for statement in statements
				if ACCOUNT_TABLE in statement and "FOR UPDATE" in statement
			],
			"the account was read without FOR UPDATE",
		)

	def test_an_account_is_never_opened_by_a_read(self):
		self.enable_credits()
		self.assertEqual(account.summary(self.user)["balance"], 0.0)
		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))

	def test_the_summary_carries_the_allocation_the_meter_gauges_against(self):
		"""The denominator holds still while the balance under it falls — a gauge, not a graph."""
		self.enable_credits()
		account.charge(self.user, 5, "Lease", ("Bench Instance", self.bench.name))

		summary = account.summary(self.user)
		self.assertAlmostEqual(summary["allocated"], GRANT, places=3)
		self.assertAlmostEqual(summary["balance"], GRANT - 5, places=3)

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
		account.charge(self.user, 5, "Lease", ("Bench Instance", self.bench.name))
		statement = account.statement(self.user, limit_start=0, limit_page_length=1)
		self.assertEqual(len(statement["rows"]), 1)
		self.assertEqual(statement["total"], 2, "grant plus usage row")
		self.assertAlmostEqual(statement["summary"]["balance"], GRANT - 5, places=3)

	def test_the_ledger_cannot_be_rewritten(self):
		self.enable_credits()
		account.grant(self.user, 5, "for the audit")
		entry = frappe.get_doc(LEDGER, self.entries()[0].name)
		entry.credits = 500
		self.assertRaises(frappe.ValidationError, entry.save)

	# --- The lifecycle wiring -------------------------------------------------

	def test_a_running_instance_buys_a_lease(self):
		"""One window, charged once. `test_lease` owns the pricing and the deadline."""
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		self.assertEqual(len([entry for entry in self.entries() if entry.entry_type == "Usage"]), 1)

	def test_starting_the_same_instance_twice_charges_one_lease(self):
		"""A redeploy, or a restart that interrupted nothing, buys no second window."""
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		charged = self.balance()
		metering.on_bench_running(bench)
		self.assertEqual(self.balance(), charged)

	def test_stopping_an_instance_that_never_ran_is_free(self):
		self.enable_credits()
		metering.on_bench_stopped(self.running_bench())
		self.assertEqual(self.entry_count(), 0)

	def test_a_failed_deploy_charges_nothing(self):
		"""The invariant this module documents: a deploy that never reached `Running` is free."""
		self.enable_credits()
		bench = self.running_bench()

		metering.on_bench_stopped(bench)
		metering.on_bench_stopped(bench)  # the cleanup path can fire twice

		self.assertEqual(self.entry_count(), 0)

	def test_a_deploy_against_a_built_image_writes_no_usage_row(self):
		"""Deploy never builds, so the image step never charges — only an explicit build does."""
		self.enable_credits()
		tag = f"benchpress/{self.lab.name}:lab"
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": tag})
		lab = frappe.get_doc("Lab", self.lab.name)

		with patch.object(deploy_manager.image_cache, "resolve", return_value=(tag, True)):
			deploy_manager._prepare_lab_image(lab, MagicMock(), frappe.session.user)

		self.assertEqual(self.entry_count(), 0)

	def test_a_build_writes_exactly_one_usage_row(self):
		self.enable_credits()
		lab = frappe.get_doc("Lab", self.lab.name)
		with patch.object(deploy_manager, "build_lab_image", return_value="fresh:tag"):
			deploy_manager._build_lab_with_logs(lab, None)
		self.addCleanup(self.purge_build_logs, lab.name)

		entries = [entry for entry in self.entries() if entry.entry_type == "Usage"]
		self.assertEqual(len(entries), 1)
		self.assertEqual(entries[0].credits, -BUILD_CREDITS)
		self.assertAlmostEqual(self.balance(), GRANT - BUILD_CREDITS, places=3)

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
			{"status": "Running", "expires_at_ts": 0, "lease_state": ""},
			update_modified=False,
		)

	def balance(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, self.user, "balance"))

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

	@classmethod
	def wipe_credits(cls) -> None:
		"""The ledger blocks updates, not deletes — the suite still has to clean up after itself.

		Committed for the same reason as the switch: a test whose pipeline committed left real
		rows behind, and a rolled-back delete would let them reappear.
		"""
		frappe.db.delete(LEDGER, {"account": USER})
		frappe.db.delete(ACCOUNT, {"user": USER})
		frappe.db.commit()  # nosemgrep -- fixture cleanup must outlive the per-test rollback
