# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Admission: what a claim writes and holds, what it refuses, and what gives both back.

The unit tests here prove the logic. They cannot prove the property, because the suite never
commits and a second connection would see nothing and then block on the first one's lock until
`innodb_lock_wait_timeout`. `scripts/admission_drill.py` proves the property, against the
shipped endpoint, with twelve processes and a barrier. That division is deliberate.

Every refusal test has a positive control beside it: a claim that throws for everybody would
pass a denial test perfectly.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, flt, now_datetime

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import admission, admission_repair, config, metering
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
LEDGER = "Credit Ledger Entry"

USER = "admission-user@example.com"
OTHER = "admission-other@example.com"
LABS = ("admission-lab-a", "admission-lab-b", "admission-lab-c")

# Every drill lab prices its own lease, so the hold is a number this module chose rather than
# whatever plan the site happens to default to.
LEASE_COST = 4.0
ADMISSION_PLAN = "Admission 30 Minutes"

TUNED_SETTINGS = ("max_concurrent_free", "max_concurrent_paid", "max_concurrent_uncredited")


def _ensure_plan() -> str:
	if frappe.db.exists("Lease Plan", ADMISSION_PLAN):
		return ADMISSION_PLAN
	return (
		frappe.get_doc(
			{
				"doctype": "Lease Plan",
				"plan_label": ADMISSION_PLAN,
				"minutes": 30,
				"credits": LEASE_COST,
				"is_active": 1,
				"sort_order": 30,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Admission",
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id: str, plan: str):
	if frappe.db.exists("Lab", lab_id):
		return frappe.get_doc("Lab", lab_id)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Admission {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
			"instance_size": "Small",
			"default_lease_plan": plan,
			"deploy_credits": LEASE_COST,
		}
	).insert(ignore_permissions=True)


def _ensure_bench(lab, owner: str):
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists(BENCH, name):
		return frappe.get_doc(BENCH, name)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": BENCH,
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestAdmission(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.settings_at_start = {
			field: frappe.db.get_single_value(CREDIT_SETTINGS, field) for field in TUNED_SETTINGS
		}
		cls.user = _ensure_user(USER)
		cls.other = _ensure_user(OTHER)
		cls.plan = _ensure_plan()
		cls.labs = [_ensure_lab(lab_id, cls.plan) for lab_id in LABS]

	def setUp(self):
		frappe.set_user("Administrator")
		self.set_credits_enabled(self.switch_at_start)
		for field, value in self.settings_at_start.items():
			self.set_setting(field, value)
		self.wipe_admissions()
		# Re-made rather than shared: one test deletes its instance, and the class rolls back
		# once at the end rather than between methods.
		self.benches = [_ensure_bench(lab, USER) for lab in self.labs]
		for bench in self.benches:
			frappe.db.set_value(
				BENCH,
				bench.name,
				{"status": "Draft", "container_id": None, "expires_at_ts": 0, "lease_state": ""},
				update_modified=False,
			)

	def tearDown(self):
		frappe.set_user("Administrator")

	# --- The claim ------------------------------------------------------------

	def test_a_claim_writes_one_row_and_one_count(self):
		self.assertTrue(admission.claim(USER, self.benches[0].name, 2))
		self.assertEqual(self.rows(), [self.benches[0].name])
		self.assertEqual(self.counter(), 1)

	def test_the_cap_refuses_the_next_bench(self):
		admission.claim(USER, self.benches[0].name, 1)
		with self.assertRaises(frappe.ValidationError) as refusal:
			admission.claim(USER, self.benches[1].name, 1)
		self.assertIn("instances running", str(refusal.exception))
		self.assertEqual(self.counter(), 1)

	def test_one_under_the_cap_is_admitted(self):
		admission.claim(USER, self.benches[0].name, 2)
		self.assertTrue(admission.claim(USER, self.benches[1].name, 2))
		self.assertEqual(self.counter(), 2)

	def test_zero_means_unlimited_and_still_claims(self):
		for bench in self.benches:
			self.assertTrue(admission.claim(USER, bench.name, 0))
		self.assertEqual(self.counter(), len(self.benches))

	def test_another_caller_has_their_own_cap(self):
		"""The contended row is the account, so one caller at their cap refuses nobody else."""
		admission.claim(USER, self.benches[0].name, 1)
		self.assertTrue(admission.claim(OTHER, "some-other-bench", 1))

	def test_a_second_claim_for_one_bench_changes_nothing(self):
		"""A redeploy, restart or retry re-uses the slot the bench already holds."""
		admission.claim(USER, self.benches[0].name, 1)
		claimed_at = frappe.db.get_value(ADMISSION, self.benches[0].name, "claimed_at")

		self.assertFalse(admission.claim(USER, self.benches[0].name, 1))
		self.assertEqual(self.counter(), 1)
		self.assertEqual(frappe.db.get_value(ADMISSION, self.benches[0].name, "claimed_at"), claimed_at)

	def test_a_call_about_no_instance_claims_nothing(self):
		self.assertFalse(admission.claim(USER, None, 1))
		self.assertEqual(self.rows(), [])

	# --- Giving it back -------------------------------------------------------

	def test_release_drops_the_row_and_the_count(self):
		admission.claim(USER, self.benches[0].name, 1)
		admission.release(self.benches[0].name)
		self.assertEqual(self.rows(), [])
		self.assertEqual(self.counter(), 0)

	def test_releasing_twice_is_quiet(self):
		admission.claim(USER, self.benches[0].name, 1)
		admission.release(self.benches[0].name)
		admission.release(self.benches[0].name)
		self.assertEqual(self.counter(), 0)

	def test_a_released_slot_can_be_claimed_again(self):
		admission.claim(USER, self.benches[0].name, 1)
		admission.release(self.benches[0].name)
		self.assertTrue(admission.claim(USER, self.benches[1].name, 1))

	def test_a_negative_count_is_refused(self):
		"""The tripwire for a lost decrement, at the one place it would otherwise be invisible."""
		account = frappe.get_doc(ACCOUNT, self.opened_account())
		account.active_instances = -1
		self.assertRaises(frappe.ValidationError, account.save)

	# --- The lifecycle paths that must give it back ---------------------------

	def test_stopping_a_bench_frees_its_slot(self):
		from benchpress.deploy_manager import stop_bench

		bench = self.running_bench(self.benches[0])
		admission.claim(USER, bench.name, 1)
		with (
			patch("benchpress.deploy_manager.stop_container"),
			patch("frappe.enqueue"),
			patch("frappe.db.commit"),
		):
			stop_bench(bench.name)
		self.assertEqual(self.counter(), 0)

	def test_tearing_a_bench_down_frees_its_slot(self):
		bench = self.running_bench(self.benches[0])
		admission.claim(USER, bench.name, 1)
		self.teardown(bench)
		self.assertEqual(self.counter(), 0)

	def test_a_redeploy_keeps_the_slot_across_the_teardown(self):
		"""Releasing halfway through hands the slot away and leaves the caller one over."""
		bench = self.running_bench(self.benches[0])
		admission.claim(USER, bench.name, 1)
		self.teardown(bench, release_admission=False)
		self.assertEqual(self.counter(), 1)

	def test_deleting_a_bench_frees_its_slot(self):
		bench = self.benches[0]
		admission.claim(USER, bench.name, 1)
		frappe.delete_doc(BENCH, bench.name, force=True, ignore_permissions=True)
		self.assertEqual(self.counter(), 0)
		self.assertEqual(self.rows(), [])

	# --- The hold -------------------------------------------------------------

	def test_a_claim_holds_the_credits_its_start_will_spend(self):
		self.enable_credits()
		self.set_balance(10)
		self.assertTrue(admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST))
		self.assertEqual(self.reserved(), LEASE_COST)
		self.assertEqual(self.held(self.benches[0].name), LEASE_COST)

	def test_a_hold_is_not_a_charge(self):
		"""No balance moves and no statement line appears for merely asking to deploy."""
		self.enable_credits()
		self.set_balance(10)
		entries = frappe.db.count(LEDGER, {"account": USER})
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		self.assertEqual(self.balance(), 10.0)
		self.assertEqual(frappe.db.count(LEDGER, {"account": USER}), entries)

	def test_what_one_admission_holds_the_next_cannot_spend(self):
		"""The whole point of the field: the balance still reads 10, what is spendable does not."""
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=6.0)
		with self.assertRaises(frappe.ValidationError) as refusal:
			admission.claim(USER, self.benches[1].name, 0, cost=6.0)
		self.assertIn("Not enough credits", str(refusal.exception))
		self.assertEqual(self.balance(), 10.0)

	def test_the_same_call_is_admitted_with_nothing_in_the_way(self):
		"""The positive control: the same cost against the same balance, no hold held."""
		self.enable_credits()
		self.set_balance(10)
		self.assertTrue(admission.claim(USER, self.benches[1].name, 0, cost=6.0))

	def test_exactly_what_is_left_over_a_hold_is_enough(self):
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=6.0)
		self.assertTrue(admission.claim(USER, self.benches[1].name, 0, cost=4.0))
		self.assertEqual(self.reserved(), 10.0)

	def test_a_suspended_account_starts_nothing_and_holds_nothing(self):
		self.enable_credits()
		self.set_balance(100)
		frappe.db.set_value(ACCOUNT, USER, "is_suspended", 1, update_modified=False)
		with self.assertRaises(frappe.ValidationError) as refusal:
			admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		self.assertIn("suspended", str(refusal.exception))
		self.assertEqual(self.rows(), [])

	def test_a_start_that_costs_nothing_is_admitted_at_zero_credits(self):
		"""A lab no lease plan reaches is free, and free is what it has to afford."""
		self.enable_credits()
		self.set_balance(0)
		self.assertTrue(admission.claim(USER, self.benches[0].name, 0, cost=0.0))
		self.assertEqual(self.reserved(), 0.0)

	def test_nothing_is_held_with_credits_switched_off(self):
		"""Concurrency is capacity; the hold is money, and there is no money on such a site."""
		self.set_credits_enabled(0)
		self.assertTrue(admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST))
		self.assertEqual(self.reserved(), 0.0)
		self.assertEqual(self.held(self.benches[0].name), 0.0)

	def test_a_second_claim_for_one_bench_holds_no_more(self):
		"""A retry re-uses the hold it already took, so it costs nothing to ask twice."""
		self.enable_credits()
		self.set_balance(LEASE_COST)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		self.assertFalse(admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST))
		self.assertEqual(self.reserved(), LEASE_COST)

	def test_a_bench_that_already_holds_a_slot_is_still_priced(self):
		"""A redeploy takes no new slot, and would otherwise be the one start nobody can refuse."""
		self.enable_credits()
		self.set_balance(LEASE_COST)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		admission.release_hold(self.benches[0].name)
		self.set_balance(LEASE_COST / 2)
		with self.assertRaises(frappe.ValidationError) as refusal:
			admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		self.assertIn("Not enough credits", str(refusal.exception))

	# --- Giving the hold back -------------------------------------------------

	def test_releasing_the_hold_keeps_the_slot(self):
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		self.assertEqual(admission.release_hold(self.benches[0].name), LEASE_COST)
		self.assertEqual(self.reserved(), 0.0)
		self.assertEqual(self.held(self.benches[0].name), 0.0)
		self.assertEqual(self.rows(), [self.benches[0].name])
		self.assertEqual(self.counter(), 1)
		self.assertEqual(self.balance(), 10.0)

	def test_releasing_the_hold_twice_returns_it_once(self):
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		admission.release_hold(self.benches[0].name)
		self.assertEqual(admission.release_hold(self.benches[0].name), 0.0)
		self.assertEqual(self.reserved(), 0.0)

	def test_release_gives_back_the_hold_with_the_slot(self):
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		admission.release(self.benches[0].name)
		self.assertEqual(self.reserved(), 0.0)
		self.assertEqual(self.rows(), [])
		self.assertEqual(self.balance(), 10.0, "a hold that comes back was never a charge")

	def test_a_negative_hold_is_refused(self):
		"""The tripwire for a hold returned twice, which would spend more than the account has."""
		account = frappe.get_doc(ACCOUNT, self.opened_account())
		account.reserved_credits = -1
		self.assertRaises(frappe.ValidationError, account.save)

	def test_reaching_running_turns_the_hold_into_a_charge(self):
		"""The one transition the whole hold exists for, and the ledger row it finally writes."""
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		metering.on_bench_running(self.running_bench(self.benches[0]))
		self.assertEqual(self.reserved(), 0.0)
		self.assertEqual(self.balance(), 10.0 - LEASE_COST)
		self.assertEqual(self.rows(), [self.benches[0].name], "the slot outlives the hold")

	def test_a_failed_deploy_gives_the_hold_back_and_charges_nothing(self):
		self.enable_credits()
		self.set_balance(10)
		bench = self.running_bench(self.benches[0])
		admission.claim(USER, bench.name, 0, cost=LEASE_COST)
		entries = frappe.db.count(LEDGER, {"account": USER})

		metering.on_bench_stopped(bench)
		admission.release(bench.name)

		self.assertEqual(self.reserved(), 0.0)
		self.assertEqual(self.balance(), 10.0)
		self.assertEqual(frappe.db.count(LEDGER, {"account": USER}), entries)

	# --- The gate -------------------------------------------------------------

	def test_the_gate_claims_with_credits_switched_off(self):
		"""Concurrency is capacity, not economics: the claim runs whatever the switch says."""
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 1)
		frappe.set_user(USER)
		with patch("frappe.enqueue"):
			frappe.get_doc(BENCH, self.benches[0].name).enqueue_deploy()
		frappe.set_user("Administrator")
		self.assertEqual(self.rows(), [self.benches[0].name])

	def test_the_gate_refuses_at_the_uncredited_cap(self):
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 1)
		admission.claim(USER, self.benches[0].name, 1)
		frappe.set_user(USER)
		with self.assertRaises(frappe.ValidationError), patch("frappe.enqueue"):
			frappe.get_doc(BENCH, self.benches[1].name).enqueue_deploy()

	def test_zero_uncredited_admits_everything_and_still_claims(self):
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 0)
		frappe.set_user(USER)
		with patch("frappe.enqueue"):
			for bench in self.benches:
				frappe.get_doc(BENCH, bench.name).enqueue_deploy()
		frappe.set_user("Administrator")
		self.assertEqual(len(self.rows()), len(self.benches))

	def test_the_spa_start_path_is_behind_the_gate(self):
		"""`api.bench_action` is how the SPA starts a bench, and it carried no limit at all."""
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 1)
		admission.claim(USER, self.benches[0].name, 1)
		self.running_bench(self.benches[1])
		frappe.set_user(USER)
		with self.assertRaises(frappe.ValidationError) as refusal:
			api.bench_action(self.benches[1].name, "start")
		self.assertIn("instances running", str(refusal.exception))

	def test_the_spa_start_path_admits_one_under_the_cap(self):
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 2)
		admission.claim(USER, self.benches[0].name, 2)
		self.running_bench(self.benches[1])
		frappe.set_user(USER)
		with (
			patch("benchpress.docker_manager.start_container"),
			patch("benchpress.deploy_manager.enqueue_route_sync"),
			patch("frappe.db.commit"),
		):
			api.bench_action(self.benches[1].name, "start")
		frappe.set_user("Administrator")
		self.assertIn(self.benches[1].name, self.rows())

	def test_stopping_stays_outside_the_gate(self):
		"""Stopping is what a refused caller is being told to do, so it cannot itself be refused."""
		self.set_credits_enabled(0)
		self.set_setting("max_concurrent_uncredited", 1)
		bench = self.running_bench(self.benches[1])
		admission.claim(USER, self.benches[0].name, 1)
		admission.claim(USER, bench.name, 0)
		frappe.set_user(USER)
		with (
			patch("benchpress.deploy_manager.stop_container"),
			patch("frappe.enqueue"),
			patch("frappe.db.commit"),
		):
			api.bench_action(bench.name, "stop")
		frappe.set_user("Administrator")
		self.assertNotIn(bench.name, self.rows())

	# --- The reconciler -------------------------------------------------------

	def test_the_reconciler_releases_a_claim_whose_bench_is_not_live(self):
		admission.claim(USER, self.benches[0].name, 0)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Stopped", update_modified=False)
		self.backdate(self.benches[0].name, minutes=admission_repair.CLAIM_GRACE_MINUTES + 1)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.rows(), [])
		self.assertEqual(self.counter(), 0)

	def test_the_reconciler_leaves_a_claim_whose_deploy_is_only_queued(self):
		"""A bench is `Draft` until a worker picks its deploy up, which is not the same as idle."""
		admission.claim(USER, self.benches[0].name, 0)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.rows(), [self.benches[0].name])

	def test_the_reconciler_keeps_a_claim_whose_bench_is_still_deploying(self):
		admission.claim(USER, self.benches[0].name, 0)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Deploying", update_modified=False)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.rows(), [self.benches[0].name])

	def test_the_reconciler_errors_a_deploy_nobody_is_running(self):
		"""A worker killed mid-deploy leaves a claim no `except` block will ever reach."""
		admission.claim(USER, self.benches[0].name, 0)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Deploying", update_modified=False)
		self.backdate(self.benches[0].name, hours=admission_repair.STALE_DEPLOY_HOURS + 1)
		admission_repair.reconcile_admissions()
		self.assertEqual(frappe.db.get_value(BENCH, self.benches[0].name, "status"), "Error")
		self.assertEqual(self.rows(), [])

	def test_the_reconciler_adopts_a_live_instance_holding_nothing(self):
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Running", update_modified=False)
		admission_repair.reconcile_admissions()
		self.assertIn(self.benches[0].name, self.rows())
		self.assertEqual(self.counter(), 1)

	def test_the_reconciler_heals_a_drifted_counter(self):
		admission.claim(USER, self.benches[0].name, 0)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Running", update_modified=False)
		frappe.db.set_value(ACCOUNT, USER, "active_instances", 7, update_modified=False)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.counter(), 1)

	def test_the_reconciler_heals_a_drifted_hold(self):
		self.enable_credits()
		self.set_balance(10)
		admission.claim(USER, self.benches[0].name, 0, cost=LEASE_COST)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Running", update_modified=False)
		frappe.db.set_value(ACCOUNT, USER, "reserved_credits", 99.0, update_modified=False)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.reserved(), LEASE_COST)

	def test_an_adopted_orphan_holds_nothing(self):
		"""Its lease was charged when it started, so there is nothing left for a hold to cover."""
		self.enable_credits()
		self.set_balance(10)
		frappe.db.set_value(BENCH, self.benches[0].name, "status", "Running", update_modified=False)
		admission_repair.reconcile_admissions()
		self.assertEqual(self.held(self.benches[0].name), 0.0)
		self.assertEqual(self.reserved(), 0.0)

	def test_the_drill_mints_a_token_the_harness_can_read(self):
		"""`bench execute … ensure_drill_user` is how every drill run gets its credentials."""
		from benchpress.credits import drill

		with patch("frappe.db.commit"):
			token = drill.ensure_drill_user()
			self.assertEqual(drill.ensure_drill_user(), token, "the token must not rotate")

		self.assertRegex(token, r"^[A-Za-z0-9]{8,}:[A-Za-z0-9]{8,}$")
		key, _, _secret = token.partition(":")
		self.assertEqual(key, frappe.db.get_value("User", drill.DRILL_USER, "api_key"))

	# --- Helpers --------------------------------------------------------------

	def backdate(self, bench_name: str, **age) -> None:
		frappe.db.set_value(
			ADMISSION,
			bench_name,
			"claimed_at",
			add_to_date(now_datetime(), **{unit: -value for unit, value in age.items()}),
			update_modified=False,
		)

	def teardown(self, bench, **kwargs) -> None:
		from benchpress.deploy_manager import teardown_bench

		with (
			patch("benchpress.deploy_manager.stop_container"),
			patch("benchpress.deploy_manager.remove_container"),
			patch("benchpress.deploy_manager._drop_site_database"),
			patch("benchpress.ingress.withdraw"),
			patch("frappe.db.commit"),
		):
			teardown_bench(frappe.get_doc(BENCH, bench.name), **kwargs)

	def running_bench(self, bench):
		frappe.db.set_value(
			BENCH,
			bench.name,
			{"status": "Running", "container_id": "admission-container"},
			update_modified=False,
		)
		return frappe.get_doc(BENCH, bench.name)

	def opened_account(self) -> str:
		from benchpress.credits import account

		return account.ensure_account(USER)

	def counter(self) -> int:
		return frappe.db.get_value(ACCOUNT, USER, "active_instances") or 0

	def reserved(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, USER, "reserved_credits"))

	def balance(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, USER, "balance"))

	def held(self, bench_name: str) -> float:
		return flt(frappe.db.get_value(ADMISSION, bench_name, "held_credits"))

	def set_balance(self, credits) -> None:
		frappe.db.set_value(ACCOUNT, self.opened_account(), "balance", credits, update_modified=False)

	def enable_credits(self) -> None:
		self.set_credits_enabled(1)

	def rows(self) -> list[str]:
		return sorted(frappe.get_all(ADMISSION, filters={"account": USER}, pluck="name"))

	def set_credits_enabled(self, value) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def set_setting(self, field: str, value) -> None:
		frappe.db.set_single_value(CREDIT_SETTINGS, field, value)
		frappe.clear_cache(doctype=CREDIT_SETTINGS)
		config.clear_size_index()

	def wipe_admissions(self) -> None:
		"""The ledger blocks updates, not deletes, and the suite still cleans up after itself."""
		for email in (USER, OTHER):
			frappe.db.delete(ADMISSION, {"account": email})
			frappe.db.delete(LEDGER, {"account": email})
			frappe.db.delete(ACCOUNT, {"user": email})
