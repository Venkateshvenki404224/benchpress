# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 5's gate: what the guard refuses, and — just as important — what it does not.

Every refusal test has a positive control immediately beside it. A guard that throws for everyone
passes a denial test perfectly, and that failure mode is the expensive one: it looks like security
and behaves like an outage.

Two properties are asserted repeatedly because both are easy to lose in a refactor:

- `0` means unlimited, for every cap.
- With `enable_credits` off nothing here happens at all — no refusal, no account row, no query.

The gate must also never be the first thing an unauthorised caller meets. `test_api_authorization`
owns who may call what; this module only proves the gate does not get in front of that answer.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, guard
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
LEDGER = "Credit Ledger Entry"
PASS = "Always On Pass"

# The seeded "Small" size: 1g / 1 core / 1.0 credits per hour / 3 sites.
RATE = 1.0
GRANT = 40.0
MAX_SITES = 3
USER = "guard-user@example.com"
ADMIN = "guard-admin@example.com"

# Every economic number this module retunes. `IntegrationTestCase` rolls back once per *class*,
# not per test, so a test's edits are visible to its siblings until then — each one is snapshotted
# before the first test and written back in `setUp`.
TUNED_SETTINGS = (
	"max_concurrent_free",
	"max_concurrent_paid",
	"max_devices",
	"max_builds_per_day",
	"custom_build_credits",
)


def _ensure_user(email: str, role: str | None = None) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Guard",
				"send_welcome_email": 0,
				"roles": [{"role": role}] if role else [],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id: str, owner: str):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": f"Guard {lab_id}",
				"frappe_version": "version-15",
				"image_tag": "benchpress/test:latest",
				"instance_size": "Small",
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


def _ensure_bench(lab, owner: str, **extra):
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists(BENCH, name):
		frappe.delete_doc(BENCH, name, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": BENCH,
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Stopped",
				"container_id": "guard-container",
				**extra,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestCreditGuard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.settings_at_start = {
			field: frappe.db.get_single_value(CREDIT_SETTINGS, field) for field in TUNED_SETTINGS
		}
		cls.max_sites_at_start = frappe.db.get_value("Instance Size", "Small", "max_sites")
		cls.user = _ensure_user(USER, "BenchPress User")
		cls.admin = _ensure_user(ADMIN, "BenchPress Admin")
		cls.lab = _ensure_lab("guard-lab", cls.user)
		cls.other_lab = _ensure_lab("guard-lab-other", cls.user)
		cls.bench = _ensure_bench(cls.lab, cls.user)
		cls.other_bench = _ensure_bench(cls.other_lab, cls.user)
		# Deliberately not committed. `IntegrationTestCase` rolls the whole class back at the end,
		# which takes these fixtures with it — and a commit anywhere in this module would make every
		# retuned price and cap durable on the site instead.

	def setUp(self):
		"""Start every test from the economics the module found, not from what a sibling left.

		**Nothing in this module commits**, so the class-end rollback undoes all of it — which is
		only safe because none of the code under test commits either: the guard throws before the
		endpoint body runs, and `frappe.enqueue` is patched wherever a body does run. One committed
		write here would make every other pending edit durable with it, and a test that retunes the
		economics would silently retune the site.
		"""
		frappe.set_user("Administrator")
		self.restore_economics()
		self.wipe_credits()
		self.reset_benches()

	def restore_economics(self) -> None:
		self.set_credits_enabled(self.switch_at_start)
		for field, value in self.settings_at_start.items():
			self.set_setting(field, value)
		self.set_size_field("max_sites", self.max_sites_at_start)

	def tearDown(self):
		frappe.set_user("Administrator")

	# --- The switch off means the gate does not exist -------------------------

	def test_this_module_leaves_the_switch_where_it_found_it(self):
		self.assertEqual(
			frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits"),
			self.switch_at_start,
		)

	def test_nothing_is_refused_and_no_account_opened_when_credits_are_off(self):
		self.set_credits_enabled(0)
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			self.assertEqual(api.create_bench(json.dumps({"lab": self.lab.name}))["status"], "Deploying")
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))

	# --- Money: the shortfall, and its positive control ----------------------

	def test_a_user_at_zero_credits_cannot_deploy_and_is_told_the_shortfall(self):
		self.enable_credits()
		self.set_balance(0)
		frappe.set_user(self.user)

		with self.assertRaises(frappe.ValidationError) as refusal:
			api.create_bench(json.dumps({"lab": self.lab.name}))

		message = str(refusal.exception)
		self.assertIn("Not enough credits", message)
		self.assertIn("short", message, "a refusal that does not name the gap explains nothing")
		self.assertIn(guard.TOP_UP_ROUTE, message, "a refusal must name the way out of it")

	def test_a_funded_user_may_deploy(self):
		"""The positive control: the same call, the only difference being a balance."""
		self.enable_credits()
		self.set_balance(GRANT)
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			self.assertEqual(api.create_bench(json.dumps({"lab": self.lab.name}))["status"], "Deploying")

	def test_a_balance_below_one_hour_is_still_a_shortfall(self):
		"""An hourly meter cannot honestly admit an instance the sweep would stop within the hour."""
		self.enable_credits()
		self.set_balance(RATE / 2)
		frappe.set_user(self.user)
		self.assertRaises(frappe.ValidationError, self.bench_document().enqueue_start)

	def test_exactly_one_hour_of_runway_is_enough(self):
		self.enable_credits()
		self.set_balance(RATE)
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			self.bench_document().enqueue_deploy()

	def test_a_suspended_account_cannot_start_anything(self):
		self.enable_credits()
		self.set_balance(GRANT)
		frappe.db.set_value(ACCOUNT, self.user, "is_suspended", 1, update_modified=False)
		frappe.set_user(self.user)
		with self.assertRaises(frappe.ValidationError) as refusal:
			self.bench_document().enqueue_start()
		self.assertIn("suspended", str(refusal.exception))

	def test_a_brand_new_user_is_granted_before_being_judged(self):
		"""The signup grant lands on first use, so a first deploy must never be refused for it."""
		self.enable_credits()
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			self.bench_document().enqueue_deploy()
		frappe.set_user("Administrator")
		self.assertEqual(account.summary(self.user)["balance"], GRANT)

	def test_an_always_on_pass_starts_free(self):
		"""A pass is prepaid, so an empty balance is not a reason to refuse that instance."""
		self.enable_credits()
		self.set_balance(0)
		self.grant_pass(self.bench.name)
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			self.bench_document().enqueue_deploy()

	def test_an_expired_pass_exempts_nothing(self):
		self.enable_credits()
		self.set_balance(0)
		self.grant_pass(self.bench.name, valid_until=add_days(today(), -1))
		frappe.set_user(self.user)
		self.assertRaises(frappe.ValidationError, self.bench_document().enqueue_deploy)

	# --- The concurrency cap --------------------------------------------------

	def test_the_concurrency_cap_refuses_one_over(self):
		self.enable_credits()
		self.set_setting("max_concurrent_free", 1)
		self.set_running(self.other_bench.name)
		frappe.set_user(self.user)
		with self.assertRaises(frappe.ValidationError) as refusal:
			self.bench_document().enqueue_start()
		self.assertIn("instances running", str(refusal.exception))

	def test_the_concurrency_cap_allows_one_under(self):
		self.enable_credits()
		self.set_setting("max_concurrent_free", 2)
		self.set_running(self.other_bench.name)
		frappe.set_user(self.user)
		guard.cap_concurrent_instances(self=self.bench_document())

	def test_zero_means_unlimited_concurrency(self):
		self.enable_credits()
		self.set_setting("max_concurrent_free", 0)
		self.set_running(self.other_bench.name)
		self.set_running(self.bench.name)
		frappe.set_user(self.user)
		guard.cap_concurrent_instances(self=self.bench_document())

	def test_the_concurrency_cap_does_not_count_the_instance_being_redeployed(self):
		"""Otherwise the cap forbids exactly the people holding it from touching what they have."""
		self.enable_credits()
		self.set_setting("max_concurrent_free", 1)
		self.set_running(self.bench.name)
		frappe.set_user(self.user)
		guard.cap_concurrent_instances(self=self.bench_document())

	def test_a_purchase_raises_the_concurrency_cap(self):
		"""Having paid is a Purchase row, not a balance.

		An Always On Pass buys hours rather than credits, so it posts a zero-credit Purchase row —
		somebody who has bought one has plainly paid, and a `lifetime_purchased` float that stayed
		at zero would still call them a free user.
		"""
		self.enable_credits()
		self.set_setting("max_concurrent_free", 1)
		self.set_setting("max_concurrent_paid", 3)
		self.set_running(self.other_bench.name)
		account.purchase(self.user, 0.0, "an always-on pass", ("Lab", self.lab.name))
		frappe.set_user(self.user)
		guard.cap_concurrent_instances(self=self.bench_document())

	# --- The sites-per-instance cap ------------------------------------------

	def test_the_site_cap_refuses_one_over_the_size_allowance(self):
		self.enable_credits()
		self.add_sites(MAX_SITES)
		frappe.set_user(self.user)
		with self.assertRaises(frappe.ValidationError) as refusal:
			api.create_site(json.dumps({"bench": self.bench.name, "site_name": "one-too-many"}))
		self.assertIn("sites its size allows", str(refusal.exception))

	def test_the_site_cap_allows_one_under(self):
		self.enable_credits()
		self.add_sites(MAX_SITES - 1)
		frappe.set_user(self.user)
		with patch("frappe.enqueue"):
			api.create_site(json.dumps({"bench": self.bench.name, "site_name": "room-for-this"}))

	def test_zero_max_sites_means_unlimited(self):
		self.enable_credits()
		self.set_size_field("max_sites", 0)
		self.add_sites(MAX_SITES + 1)
		frappe.set_user(self.user)
		guard.cap_sites_per_instance(data=json.dumps({"bench": self.bench.name}))

	# --- The device cap ------------------------------------------------------

	def test_the_device_cap_refuses_one_over(self):
		self.enable_credits()
		self.set_setting("max_devices", 2)
		frappe.set_user(self.user)
		with patch("benchpress.vpn_adapter.count_devices", return_value=2):
			with self.assertRaises(frappe.ValidationError) as refusal:
				guard.cap_devices()
		self.assertIn("devices", str(refusal.exception))

	def test_the_device_cap_allows_one_under(self):
		self.enable_credits()
		self.set_setting("max_devices", 2)
		frappe.set_user(self.user)
		with patch("benchpress.vpn_adapter.count_devices", return_value=1):
			guard.cap_devices()

	def test_zero_means_unlimited_devices(self):
		self.enable_credits()
		self.set_setting("max_devices", 0)
		frappe.set_user(self.user)
		with patch("benchpress.vpn_adapter.count_devices", return_value=99) as counted:
			guard.cap_devices()
		counted.assert_not_called()

	# --- The builds-per-day cap ---------------------------------------------

	def test_the_build_cap_refuses_one_over(self):
		self.enable_credits()
		self.set_setting("max_builds_per_day", 2)
		self.record_builds(2, owner=self.admin)
		frappe.set_user(self.admin)
		with self.assertRaises(frappe.ValidationError) as refusal:
			api.build_lab_image(self.lab.name)
		self.assertIn("custom image builds", str(refusal.exception))

	def test_the_build_cap_allows_one_under(self):
		self.enable_credits()
		self.set_setting("max_builds_per_day", 2)
		self.record_builds(1, owner=self.admin)
		frappe.set_user(self.admin)
		with patch("frappe.enqueue"):
			self.assertEqual(api.build_lab_image(self.lab.name)["status"], "Building")

	def test_zero_means_unlimited_builds(self):
		self.enable_credits()
		self.set_setting("max_builds_per_day", 0)
		self.record_builds(5, owner=self.admin)
		frappe.set_user(self.admin)
		with patch("frappe.enqueue"):
			api.build_lab_image(self.lab.name)

	def test_yesterdays_builds_do_not_count_against_today(self):
		self.enable_credits()
		self.set_setting("max_builds_per_day", 1)
		self.record_builds(1, owner=self.admin, creation=add_days(today(), -1))
		frappe.set_user(self.admin)
		with patch("frappe.enqueue"):
			api.build_lab_image(self.lab.name)

	def test_a_free_build_is_still_counted(self):
		"""`custom_build_credits = 0` makes builds free, not uncountable."""
		self.enable_credits()
		self.set_setting("custom_build_credits", 0)
		account.charge(self.admin, 0, "Custom image build for a free size", ("Lab", self.lab.name))
		self.assertEqual(self.build_row_count(self.admin), 1)

	# --- The gate never answers a permission question ------------------------

	def test_a_caller_without_an_app_role_meets_the_endpoint_guard_not_the_gate(self):
		self.enable_credits()
		roleless = _ensure_user("guard-norole@example.com")
		self.addCleanup(self.delete_user, roleless)
		frappe.set_user(roleless)
		self.assertRaises(frappe.PermissionError, api.create_bench, json.dumps({"lab": self.lab.name}))
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(ACCOUNT, roleless), "the gate opened an account for a stranger")

	# --- Helpers -------------------------------------------------------------

	def enable_credits(self) -> None:
		self.set_credits_enabled(1)

	def set_credits_enabled(self, value: int) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def set_setting(self, field: str, value) -> None:
		frappe.db.set_single_value(CREDIT_SETTINGS, field, value)
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	def set_size_field(self, field: str, value) -> None:
		frappe.db.set_value("Instance Size", "Small", field, value, update_modified=False)
		config.clear_size_index()

	def set_balance(self, credits, user: str | None = None) -> None:
		user = user or self.user
		account.ensure_account(user)
		frappe.db.set_value(ACCOUNT, user, "balance", credits, update_modified=False)

	def bench_document(self):
		return frappe.get_doc(BENCH, self.bench.name)

	def set_running(self, bench_name: str) -> None:
		frappe.db.set_value(BENCH, bench_name, "status", "Running", update_modified=False)

	def reset_benches(self) -> None:
		names = [self.bench.name, self.other_bench.name]
		for name in names:
			frappe.db.set_value(
				BENCH,
				name,
				{"status": "Stopped", "credit_burn_rate": 0.0, "credit_burn_started": None},
				update_modified=False,
			)
		frappe.db.delete(PASS, {"bench_instance": ("in", names)})
		frappe.db.delete("Bench Site", {"bench": ("in", names)})

	def grant_pass(self, bench_name: str, valid_until=None) -> None:
		"""Inserted past its own validation when the test needs an expired one to exist."""
		pass_doc = frappe.get_doc(
			{"doctype": PASS, "bench_instance": bench_name, "valid_until": add_days(today(), 30)}
		)
		pass_doc.insert(ignore_permissions=True)
		if valid_until:
			frappe.db.set_value(PASS, pass_doc.name, "valid_until", valid_until, update_modified=False)

	def add_sites(self, count: int) -> None:
		for index in range(count):
			frappe.get_doc(
				{"doctype": "Bench Site", "site_name": f"guard-site-{index}", "bench": self.bench.name}
			).insert(ignore_permissions=True)

	def record_builds(self, count: int, owner: str, creation=None) -> None:
		"""The rows a custom build writes, which is what the daily cap counts.

		Funded well past the build fee on purpose: these tests are about the cap, and a shortfall
		refusal would pass them for the wrong reason.
		"""
		self.set_balance(GRANT * 100, owner)
		for index in range(count):
			account.charge(owner, 1, f"Custom image build {index}", ("Lab", self.lab.name))
		if creation:
			frappe.db.set_value(LEDGER, {"account": owner}, "creation", creation, update_modified=False)

	def build_row_count(self, owner: str) -> int:
		return frappe.db.count(LEDGER, {"account": owner, "reference_doctype": "Lab"})

	def delete_user(self, email: str) -> None:
		frappe.set_user("Administrator")
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	@classmethod
	def wipe_credits(cls) -> None:
		"""The ledger blocks updates, not deletes — the suite still has to clean up after itself."""
		for email in (USER, ADMIN):
			frappe.db.delete(LEDGER, {"account": email})
			frappe.db.delete(ACCOUNT, {"user": email})
