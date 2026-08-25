# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The lease clock: what a deploy buys, when it ends, and who may end it.

Three properties decide whether this can be sold, and each has a test here that fails loudly
against the obvious wrong implementation.

**The cutoff is a Python integer.** The app clock and the database clock on this deployment are
5h30m apart, so `expires_at <= NOW()` in SQL is five and a half hours of free compute — and while
testing it merely looks like the lease has not expired yet. `test_a_deadline_five_hours_old_is_claimed`
plants exactly that row.

**The clock is armed at `Running`, never at deploy.** A cold image build takes minutes, and a lease
that starts before the container exists sells time the build ate.

**A claimed row is re-read under a lock before anything stops.** The sweep's read was true when it
ran and may be stale by the time the job acts. `test_the_stop_job_locks_the_row_before_it_acts`
matches the emitted SQL rather than a keyword argument: the kwarg is the code, the SQL is the
contract.

Nothing here commits. `claim_due` does, once per claim, so every test that reaches it mocks
`frappe.db.commit` — which is also how commit-per-claim is pinned.
"""

import inspect
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, now_datetime

from benchpress import api, deploy_manager, lab_detail
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import account, config, lease, metering
from benchpress.credits.seed import seed_default_lease_plan, seed_defaults

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
LEDGER = "Credit Ledger Entry"
PLAN = "Lease Plan"

GRANT = 40.0
HALF_HOUR = 30
HALF_HOUR_CREDITS = 5.0
WEEK = 7 * 24 * 60
WEEK_CREDITS = 200.0
FIVE_HOURS = 5 * 3600

USER = "lease-owner@example.com"
OTHER_USER = "lease-neighbour@example.com"


def _ensure_user(email: str, first_name: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_plan(label: str, minutes: int, credits: float) -> str:
	if frappe.db.exists(PLAN, label):
		frappe.db.set_value(PLAN, label, {"minutes": minutes, "credits": credits, "is_active": 1})
		return label
	return (
		frappe.get_doc(
			{
				"doctype": PLAN,
				"plan_label": label,
				"minutes": minutes,
				"credits": credits,
				"is_active": 1,
				"sort_order": minutes,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _ensure_lab(lab_id: str, owner: str):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": f"Lease {lab_id}",
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
				"status": "Running",
				"container_id": "lease-container",
				**extra,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestLease(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.default_plan_at_start = frappe.db.get_single_value(CREDIT_SETTINGS, "default_lease_plan")
		cls.user = _ensure_user(USER, "Lease Owner")
		cls.other_user = _ensure_user(OTHER_USER, "Lease Neighbour")
		cls.short_plan = _ensure_plan("Lease Test 30 Minutes", HALF_HOUR, HALF_HOUR_CREDITS)
		cls.long_plan = _ensure_plan("Lease Test 1 Week", WEEK, WEEK_CREDITS)
		cls.free_plan = _ensure_plan("Lease Test Free", HALF_HOUR, 0.0)
		cls.lab = _ensure_lab("lease-lab", cls.user)
		cls.bench = _ensure_bench(cls.lab, cls.user)
		cls.other_lab = _ensure_lab("lease-lab-other", cls.other_user)
		cls.other_bench = _ensure_bench(cls.other_lab, cls.other_user)
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		# The catalog first, and in a `try`: a `Lease Plan` is product data — it is what the
		# lease picker offers. Deleting the benches ahead of it once hit a lock-wait timeout,
		# which aborted the rest of this method and left three fixture plans on sale.
		try:
			cls.restore_catalog()
		finally:
			cls.drop_fixtures()
		frappe.db.commit()  # nosemgrep -- fixtures were committed, so the cleanup must be too
		super().tearDownClass()

	@classmethod
	def restore_catalog(cls) -> None:
		"""Put `Credit Settings` back, then remove the fixture plans it may still name.

		That order, not the other one: this module commits, so a Single left naming a deleted
		fixture breaks every later `Credit Settings` save in the suite with a broken link. A
		recorded value that is itself a fixture means an earlier run died here — fall back to
		the seed rather than restoring the leak.
		"""
		fixtures = (cls.short_plan, cls.long_plan, cls.free_plan)
		restore = None if cls.default_plan_at_start in fixtures else cls.default_plan_at_start
		frappe.db.set_single_value(CREDIT_SETTINGS, "default_lease_plan", restore)
		for plan in fixtures:
			frappe.delete_doc(PLAN, plan, force=True, ignore_permissions=True)
		seed_default_lease_plan()
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	@classmethod
	def drop_fixtures(cls) -> None:
		for bench in (cls.bench, cls.other_bench):
			frappe.delete_doc(BENCH, bench.name, force=True, ignore_permissions=True)
		for lab in (cls.lab, cls.other_lab):
			frappe.delete_doc("Lab", lab.name, force=True, ignore_permissions=True)
		cls.wipe_credits()
		for user in (cls.user, cls.other_user):
			if frappe.db.exists("User", user):
				frappe.delete_doc("User", user, force=True, ignore_permissions=True)

	@classmethod
	def wipe_credits(cls) -> None:
		"""The ledger blocks updates, not deletes — the suite still has to clean up after itself."""
		for user in (USER, OTHER_USER):
			frappe.db.delete(LEDGER, {"account": user})
			frappe.db.delete(ACCOUNT, {"user": user})
		frappe.db.commit()  # nosemgrep -- fixture cleanup must outlive the per-test rollback

	def setUp(self):
		frappe.set_user("Administrator")
		config.clear_size_index()
		self.wipe_credits()
		self.reset_labs()
		self.reset_benches()
		self.set_credit_setting("default_lease_plan", self.short_plan)

	def tearDown(self):
		frappe.set_user("Administrator")

	# --- Fixtures -------------------------------------------------------------

	def reset_labs(self) -> None:
		for name in (self.lab.name, self.other_lab.name):
			frappe.db.set_value(
				"Lab",
				name,
				{"default_lease_plan": None, "max_lease_minutes": 0, "deploy_credits": 0},
			)
			frappe.clear_document_cache("Lab", name)
		frappe.db.set_value("Instance Size", "Small", {"default_lease_plan": None, "price_multiplier": 1.0})
		config.clear_size_index()

	def reset_benches(self) -> None:
		for name in (self.bench.name, self.other_bench.name):
			frappe.db.set_value(
				BENCH,
				name,
				{
					"status": "Running",
					"container_id": "lease-container",
					"expires_at_ts": 0,
					"lease_state": "",
					"stop_claimed_at": None,
					"expiry_attempts": 0,
					"credit_burn_rate": 0,
					"credit_burn_started": None,
				},
				update_modified=False,
			)

	def enable_credits(self) -> None:
		self.set_credits_enabled(1)

	def set_credits_enabled(self, value: int) -> None:
		"""One cleanup, not two: `addCleanup` runs LIFO, so a separate cache clear would fire
		before the value was restored and leave the switch stuck on for every later test."""
		original = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		self.addCleanup(self.write_credits_switch, original)
		self.write_credits_switch(value)

	def write_credits_switch(self, value) -> None:
		"""Committed, because the code under test commits.

		`claim_due` commits per claim, which makes this test's pending switch value durable. A
		restore riding on the per-test rollback would be thrown away, and the site would be left
		with credits armed.
		"""
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.db.commit()  # nosemgrep -- see above: the restore must outlive the rollback
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def set_credit_setting(self, field: str, value) -> None:
		"""Retune one number durably, and put it back the same way. See `write_credits_switch`."""
		original = frappe.db.get_single_value(CREDIT_SETTINGS, field)
		self.addCleanup(self.write_credit_setting, field, original)
		self.write_credit_setting(field, value)

	def write_credit_setting(self, field: str, value) -> None:
		frappe.db.set_single_value(CREDIT_SETTINGS, field, value)
		frappe.db.commit()  # nosemgrep -- the code under test commits, so the restore must too
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	def lease_events(self, publish, event: str | None = None) -> list:
		"""Only this feature's pushes. Every `save` also emits Frappe's own `doc_update`."""
		wanted = event or lease.EXPIRED_EVENT
		return [call for call in publish.call_args_list if call.args[0] == wanted]

	@contextmanager
	def renewing(self):
		"""Renew with Docker, the route job and the commit stood down, so the rollback still holds."""
		with (
			patch("benchpress.docker_manager.start_container") as start,
			patch("benchpress.deploy_manager.enqueue_route_sync") as route,
			patch("frappe.publish_realtime") as publish,
			patch.object(frappe.db, "commit"),
		):
			yield frappe._dict(start=start, route=route, publish=publish)

	def fund(self, credits: float = 1000.0) -> None:
		account.grant(self.user, credits, "Lease renewal test float")

	def claim(self) -> None:
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)

	def stop_the_bench(self) -> None:
		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			deploy_manager.stop_bench(self.bench.name)

	def age_the_bench(self, days: int) -> None:
		"""Backdate `modified`, which is what the reaper measures a stopped bench against."""
		frappe.db.set_value(
			BENCH, self.bench.name, "modified", add_days(now_datetime(), -days), update_modified=False
		)

	def bench_row(self):
		return frappe.db.get_value(BENCH, self.bench.name, ["name", "modified", "status"], as_dict=True)

	def set_lab_ceiling(self, minutes: int) -> None:
		frappe.db.set_value("Lab", self.lab.name, "max_lease_minutes", minutes)
		frappe.clear_document_cache("Lab", self.lab.name)

	def statements(self, sql) -> list[str]:
		return [str(call.args[0]) for call in sql.call_args_list if call.args]

	def locks_the_bench(self, statement: str) -> bool:
		return "FOR UPDATE" in statement and "tabBench Instance" in statement

	def running_bench(self):
		return frappe.get_doc(BENCH, self.bench.name)

	def lab_doc(self):
		return frappe.get_doc("Lab", self.lab.name)

	def plan(self, name: str) -> dict:
		return frappe.db.get_value(PLAN, name, ["name", "plan_label", "minutes", "credits"], as_dict=True)

	def balance(self) -> float:
		return flt(frappe.db.get_value(ACCOUNT, self.user, "balance"))

	def usage_rows(self, user: str = USER) -> list:
		return frappe.get_all(
			LEDGER,
			filters={"account": user, "entry_type": "Usage"},
			fields=["credits", "description", "reference_name"],
		)

	def deadline(self, bench_name: str | None = None) -> int:
		return int(frappe.db.get_value(BENCH, bench_name or self.bench.name, "expires_at_ts") or 0)

	def lease_state(self, bench_name: str | None = None) -> str:
		return frappe.db.get_value(BENCH, bench_name or self.bench.name, "lease_state") or ""

	def expire(self, bench_name: str | None = None, seconds_ago: int = 60) -> int:
		"""Plant a deadline in the past, the way a real lease reaches the sweep."""
		deadline = lease.now_ts() - seconds_ago
		frappe.db.set_value(
			BENCH,
			bench_name or self.bench.name,
			{"expires_at_ts": deadline, "lease_state": lease.ACTIVE, "expiry_attempts": 0},
			update_modified=False,
		)
		return deadline

	# --- Pricing and configuration --------------------------------------------

	def test_a_lab_uses_its_own_plan_then_its_size_then_the_default(self):
		"""Same precedence rule as `config.size_for_lab`: chosen, resolved, default."""
		self.enable_credits()
		self.assertEqual(lease.plan_for(self.lab_doc())["name"], self.short_plan)

		frappe.db.set_value("Instance Size", "Small", "default_lease_plan", self.long_plan)
		config.clear_size_index()
		self.assertEqual(lease.plan_for(self.lab_doc())["name"], self.long_plan)

		frappe.db.set_value("Lab", self.lab.name, "default_lease_plan", self.free_plan)
		frappe.clear_document_cache("Lab", self.lab.name)
		self.assertEqual(lease.plan_for(self.lab_doc())["name"], self.free_plan)

	def test_cost_is_the_plan_times_the_size_multiplier(self):
		self.enable_credits()
		frappe.db.set_value("Instance Size", "Small", "price_multiplier", 2.5)
		config.clear_size_index()
		self.assertEqual(
			lease.cost_of(self.lab_doc(), self.plan(self.short_plan)),
			HALF_HOUR_CREDITS * 2.5,
		)

	def test_a_lab_can_price_its_own_deploys(self):
		"""`deploy_credits` overrides the multiplier outright — a promotional or fixed-price lab."""
		self.enable_credits()
		frappe.db.set_value("Instance Size", "Small", "price_multiplier", 2.5)
		config.clear_size_index()
		frappe.db.set_value("Lab", self.lab.name, "deploy_credits", 3.0)
		frappe.clear_document_cache("Lab", self.lab.name)
		self.assertEqual(lease.cost_of(self.lab_doc(), self.plan(self.short_plan)), 3.0)

	def test_a_free_plan_still_arms_a_clock(self):
		"""Free is a price, not an exemption — the window still closes."""
		self.enable_credits()
		frappe.db.set_value("Lab", self.lab.name, "default_lease_plan", self.free_plan)
		frappe.clear_document_cache("Lab", self.lab.name)
		bench = self.running_bench()
		metering.on_bench_running(bench)

		self.assertEqual(self.balance(), GRANT)
		self.assertEqual(self.lease_state(), lease.ACTIVE)
		self.assertAlmostEqual(self.deadline(), lease.now_ts() + HALF_HOUR * 60, delta=5)

	def test_a_lease_ceiling_clips_a_longer_plan(self):
		self.enable_credits()
		frappe.db.set_value("Lab", self.lab.name, "max_lease_minutes", 60)
		frappe.clear_document_cache("Lab", self.lab.name)
		self.assertEqual(lease.minutes_for(self.lab_doc(), self.plan(self.long_plan)), 60)

	def test_a_lease_ceiling_of_zero_is_unlimited(self):
		self.enable_credits()
		self.assertEqual(lease.minutes_for(self.lab_doc(), self.plan(self.long_plan)), WEEK)

	# --- The clock is armed at Running, never at deploy -----------------------

	def test_creating_a_bench_charges_nothing_and_arms_nothing(self):
		"""A cold image build can take many minutes; a lease that starts here sells time the
		build ate."""
		self.enable_credits()
		account.ensure_account(self.user)
		frappe.db.set_value(BENCH, self.bench.name, "status", "Draft", update_modified=False)
		frappe.set_user(self.user)
		try:
			created = api.create_bench(frappe.as_json({"lab": self.lab.name}))
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(self.usage_rows(), [])
		self.assertEqual(self.deadline(created["name"]), 0)
		self.assertEqual(self.lease_state(created["name"]), "")

	def test_reaching_running_charges_once_and_sets_the_deadline(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)

		rows = self.usage_rows()
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].credits, -HALF_HOUR_CREDITS)
		self.assertEqual(rows[0].reference_name, bench.name)
		self.assertEqual(self.balance(), GRANT - HALF_HOUR_CREDITS)
		self.assertAlmostEqual(self.deadline(), lease.now_ts() + HALF_HOUR * 60, delta=5)

	def test_a_second_transition_into_running_does_not_charge_twice(self):
		"""A restart interrupts no session — the window it was sold is still open."""
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		first = self.deadline()
		metering.on_bench_running(bench)

		self.assertEqual(len(self.usage_rows()), 1)
		self.assertEqual(self.deadline(), first)

	def test_no_account_carries_a_burn_rate_any_more(self):
		"""The hourly meter is gone. Two meters beside each other would bill the same hour twice."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.assertEqual(flt(frappe.db.get_value(ACCOUNT, self.user, "burn_rate")), 0.0)
		self.assertFalse(frappe.db.get_value(BENCH, self.bench.name, "credit_burn_started"))

	def test_a_deploy_that_fails_after_the_container_started_is_free(self):
		"""The invariant `metering.py` documents: a deploy that never reached `Running` costs nothing."""
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_stopped(bench)

		self.assertEqual(self.usage_rows(), [])
		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))

	def test_stopping_clears_the_clock(self):
		self.enable_credits()
		bench = self.running_bench()
		metering.on_bench_running(bench)
		metering.on_bench_stopped(bench)

		self.assertEqual(self.deadline(), 0)
		self.assertEqual(self.lease_state(), "")

	def test_a_restarted_bench_gets_a_fresh_deadline_and_is_not_reclaimed(self):
		"""The resurrection test — the reference platform's bug.

		An implementation that writes `status` without the deadline leaves the old, passed value
		on the row, and the next sweep stops the bench seconds after the user started it.
		"""
		self.enable_credits()
		# The concurrency cap is not what this test is about, and the fixture user owns benches
		# left running by the rest of the module.
		self.set_credit_setting("max_concurrent_free", 0)
		metering.on_bench_running(self.running_bench())
		self.expire()
		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			deploy_manager.stop_bench(self.bench.name)
		self.assertEqual(self.deadline(), 0)

		with (
			patch("benchpress.docker_manager.start_container"),
			patch.object(deploy_manager, "enqueue_route_sync"),
			patch.object(frappe.db, "commit"),
		):
			frappe.get_doc(BENCH, self.bench.name).enqueue_start()

		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Running")
		self.assertGreater(self.deadline(), lease.now_ts())
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertNotIn(self.bench.name, lease.claim_due(50))

	# --- The claim protocol ----------------------------------------------------

	def test_a_deadline_five_hours_old_is_claimed(self):
		"""The clock-skew test. `expires_at <= NOW()` in SQL would leave this row alone.

		The database on this host runs 5h30m behind the app, so a deadline five hours in the past
		reads as still in the future to SQL — and the bench runs free until it is not.
		"""
		self.enable_credits()
		self.expire(seconds_ago=FIVE_HOURS)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertIn(self.bench.name, lease.claim_due(50))

	def test_a_deadline_in_the_future_is_left_alone(self):
		self.enable_credits()
		frappe.db.set_value(
			BENCH,
			self.bench.name,
			{"expires_at_ts": lease.now_ts() + 600, "lease_state": lease.ACTIVE},
			update_modified=False,
		)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertEqual(lease.claim_due(50), [])

	def test_two_sweeps_over_one_due_row_claim_it_once(self):
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			first = lease.claim_due(50)
			second = lease.claim_due(50)

		self.assertIn(self.bench.name, first)
		self.assertEqual(second, [])

	def test_a_claimed_row_leaves_the_scan_range(self):
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)
		self.assertEqual(self.lease_state(), lease.STOPPING)
		self.assertTrue(frappe.db.get_value(BENCH, self.bench.name, "stop_claimed_at"))

	def test_the_sweep_commits_once_per_claim(self):
		"""A batch in one transaction holds every claimed row's lock for the whole sweep, and a
		renew touching one of them fails on the 50-second lock wait."""
		self.enable_credits()
		self.expire()
		self.expire(self.other_bench.name)
		with patch.object(frappe.db, "commit") as commit, patch("frappe.enqueue"):
			claimed = lease.claim_due(50)

		self.assertEqual(len(claimed), 2)
		self.assertEqual(commit.call_count, 2)

	def test_the_stop_is_enqueued_after_commit(self):
		"""Otherwise the job reads the pre-claim row and stops a bench whose claim then rolls back."""
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			lease.claim_due(50)

		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
		self.assertEqual(enqueue.call_args.kwargs["queue"], "long")

	def test_the_sweep_makes_no_docker_call(self):
		"""It runs wherever the scheduler puts it, and `queue-short` has no socket mounted."""
		self.enable_credits()
		self.expire()
		with (
			patch.object(frappe.db, "commit"),
			patch("frappe.enqueue"),
			patch("benchpress.docker_manager.get_client") as client,
		):
			lease.sweep_expired_leases()
		client.assert_not_called()

	def test_the_stop_job_locks_the_row_before_it_acts(self):
		"""Asserting a kwarg asserts the code; asserting the emitted SQL asserts the contract."""
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)

		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql, patch.object(frappe.db, "commit"):
			lease.confirm_expiry(self.bench.name)
		statements = [str(call.args[0]) for call in sql.call_args_list if call.args]
		self.assertTrue(
			any("FOR UPDATE" in statement for statement in statements),
			"the claimed row was re-read without FOR UPDATE",
		)

	def test_a_deadline_that_moved_makes_the_stop_a_no_op(self):
		"""The renew-shaped race: the sweep's read was true when it ran and stale when it acted."""
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)
		frappe.db.set_value(BENCH, self.bench.name, "expires_at_ts", lease.now_ts() + 1800)

		with patch.object(deploy_manager, "stop_container") as stop, patch.object(frappe.db, "commit"):
			deploy_manager.stop_bench(self.bench.name)

		stop.assert_not_called()
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Running")
		self.assertEqual(self.lease_state(), lease.ACTIVE)
		self.assertIsNone(frappe.db.get_value(BENCH, self.bench.name, "stop_claimed_at"))

	def test_a_stop_that_fails_leaves_the_row_reclaimable(self):
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)

		with patch.object(deploy_manager, "stop_container", side_effect=RuntimeError("docker is down")):
			with patch.object(frappe.db, "commit"):
				self.assertRaises(RuntimeError, deploy_manager.stop_bench, self.bench.name)

		self.assertEqual(self.lease_state(), lease.ACTIVE)
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "expiry_attempts"), 1)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertIn(self.bench.name, lease.claim_due(50))

	def test_a_stop_that_keeps_failing_stops_taking_a_slot(self):
		self.enable_credits()
		self.expire()
		frappe.db.set_value(
			BENCH, self.bench.name, "expiry_attempts", lease.MAX_EXPIRY_ATTEMPTS, update_modified=False
		)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertEqual(lease.claim_due(50), [])

	def test_a_plain_stop_is_untouched_by_the_lease(self):
		"""A bench with no lease stops exactly the way it does on a dev checkout."""
		self.set_credits_enabled(0)
		with patch.object(deploy_manager, "stop_container") as stop, patch.object(frappe.db, "commit"):
			deploy_manager.stop_bench(self.bench.name)
		stop.assert_called_once()
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Stopped")

	def test_the_sweep_does_nothing_when_credits_are_off(self):
		self.set_credits_enabled(0)
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			self.assertEqual(lease.sweep_expired_leases()["claimed"], [])
		enqueue.assert_not_called()

	# --- The push --------------------------------------------------------------

	def test_expiry_pushes_reconcilable_state_to_the_owner_alone(self):
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)

		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime") as publish,
		):
			deploy_manager.stop_bench(self.bench.name)

		events = self.lease_events(publish)
		self.assertEqual(len(events), 1)
		payload = events[0].args[1]
		self.assertEqual(events[0].kwargs["user"], self.user)
		self.assertTrue(events[0].kwargs["after_commit"])
		self.assertEqual(payload["bench"], self.bench.name)
		self.assertEqual(payload["state"], "Stopped")
		self.assertIn("lab_id", payload)
		self.assertIn("expires_at_ts", payload)
		self.assertIn("server_now_ms", payload)
		self.assertIn("revision", payload)
		self.assertFalse(
			[key for key in payload if "password" in key],
			"the bench row carries three passwords and none of them belong in a push",
		)

	def test_another_tenants_bench_produces_no_event_here(self):
		self.enable_credits()
		self.expire(self.other_bench.name)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			lease.claim_due(50)

		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime") as publish,
		):
			deploy_manager.stop_bench(self.other_bench.name)

		events = self.lease_events(publish)
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].kwargs["user"], self.other_user)

	def test_a_plain_stop_announces_nothing(self):
		"""Only an expiry is news the tab did not ask for; a user pressing Stop already knows."""
		self.enable_credits()
		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime") as publish,
		):
			deploy_manager.stop_bench(self.bench.name)
		self.assertEqual(self.lease_events(publish), [])

	# --- The clock the browser anchors on --------------------------------------

	def test_the_anchor_keeps_its_milliseconds(self):
		"""Whole seconds on the wire put the browser's clock up to a second behind the server.

		The countdown then rounds that up again, and a running lease reads about 1.6 seconds
		longer than it is — time the user does not have. The deadline stays whole seconds; only
		the clock sample needs the resolution.
		"""
		with patch("time.time", return_value=1787622936.472):
			self.assertEqual(api.server_time(), {"server_now_ms": 1787622936472})

	def test_the_lab_payload_carries_the_same_anchor(self):
		"""A tab that reloads re-anchors from the payload it already fetched."""
		with patch("time.time", return_value=1787622936.472):
			payload = lab_detail.get_lab(self.lab.name)
		self.assertEqual(payload["server_now_ms"], 1787622936472)

	def test_the_expiry_push_carries_the_same_anchor(self):
		with patch("time.time", return_value=1787622936.472), patch("frappe.publish_realtime") as publish:
			lease.announce_expired(self.running_bench())
		self.assertEqual(self.lease_events(publish)[0].args[1]["server_now_ms"], 1787622936472)

	# --- Renew: the arithmetic -------------------------------------------------

	def test_a_renewal_extends_from_the_deadline_not_from_now(self):
		"""Extending from now silently burns whatever time was left, which is a refund."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		bought = self.deadline()

		with self.renewing():
			api.renew_bench(self.bench.name, self.short_plan, "req-extend")

		self.assertEqual(self.deadline(), bought + HALF_HOUR * 60)
		self.assertEqual(self.balance(), GRANT - 2 * HALF_HOUR_CREDITS)
		self.assertEqual(len(self.usage_rows()), 2)

	def test_a_renewal_of_a_bench_stopped_in_grace_extends_from_now(self):
		"""There is no remaining time to preserve, and a past deadline would buy time already gone."""
		self.enable_credits()
		self.set_credit_setting("reap_after_days", 7)
		self.stop_the_bench()
		self.assertEqual(self.deadline(), 0)

		with self.renewing():
			api.renew_bench(self.bench.name, self.short_plan, "req-grace-extend")

		self.assertAlmostEqual(self.deadline(), lease.now_ts() + HALF_HOUR * 60, delta=5)

	def test_a_renewal_past_the_labs_ceiling_is_refused_and_costs_nothing(self):
		"""The reference platform's `renewal_max`, which they had to add after `periods=1000`."""
		self.enable_credits()
		self.fund()
		metering.on_bench_running(self.running_bench())
		self.set_lab_ceiling(60)
		before = self.balance()

		with self.renewing(), self.assertRaises(frappe.ValidationError) as refused:
			api.renew_bench(self.bench.name, self.long_plan, "req-ceiling")

		self.assertIn("60", str(refused.exception))
		self.assertEqual(self.balance(), before)
		self.assertEqual(len(self.usage_rows()), 1)

	def test_a_ceiling_of_zero_lets_a_renewal_run_as_long_as_the_plan(self):
		self.enable_credits()
		self.fund()
		metering.on_bench_running(self.running_bench())
		self.set_lab_ceiling(0)
		bought = self.deadline()

		with self.renewing():
			api.renew_bench(self.bench.name, self.long_plan, "req-unlimited")

		self.assertEqual(self.deadline(), bought + WEEK * 60)

	def test_a_renewal_nobody_can_afford_names_the_shortfall_and_costs_nothing(self):
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		before = self.balance()

		with self.renewing(), self.assertRaises(frappe.ValidationError) as refused:
			api.renew_bench(self.bench.name, self.long_plan, "req-broke")

		message = str(refused.exception)
		self.assertIn(str(WEEK_CREDITS), message)
		self.assertEqual(self.balance(), before)
		self.assertEqual(len(self.usage_rows()), 1)

	# --- Renew: the race that protects money -----------------------------------

	def test_a_renewal_locks_the_row_the_stop_job_locks(self):
		"""Renew and the stop serialise on the row itself. Asserting the SQL asserts the contract."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())

		with self.renewing(), patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql:
			api.renew_bench(self.bench.name, self.short_plan, "req-lock")

		self.assertTrue(
			[statement for statement in self.statements(sql) if self.locks_the_bench(statement)],
			"the bench row was read without the lock `confirm_expiry` takes",
		)

	def test_a_renewal_that_commits_first_leaves_the_sweep_nothing_to_claim(self):
		"""The sweep's read was true when it ran and stale by the time it tried to act.

		Both racers take the same row lock, so the renew either commits before the conditional
		claim runs — this — or arrives after it and is refused by name. There is no third order
		in which a bench that has just been paid for is stopped.
		"""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.expire()
		self.assertIn(self.bench.name, lease._due(lease.now_ts(), 50))

		with self.renewing():
			api.renew_bench(self.bench.name, self.short_plan, "req-wins")
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			self.assertEqual(lease.claim_due(50), [])

		enqueue.assert_not_called()
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Running")
		self.assertEqual(self.lease_state(), lease.ACTIVE)
		self.assertGreater(self.deadline(), lease.now_ts())

	def test_a_renewal_that_arrives_after_the_claim_is_refused_by_name(self):
		"""The sweep won. The user gets a sentence about starting it again, not a traceback."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.expire()
		self.claim()
		before = self.balance()

		with self.renewing(), self.assertRaises(frappe.ValidationError) as refused:
			api.renew_bench(self.bench.name, self.short_plan, "req-loses")

		self.assertIn("start", str(refused.exception).lower())
		self.assertEqual(self.balance(), before)
		self.assertEqual(len(self.usage_rows()), 1)

	def test_a_refused_renewal_never_reaches_the_charge(self):
		"""The charge sits inside the lock and after every guard, so a refusal cannot debit."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.expire()
		self.claim()

		with self.renewing(), patch.object(account, "charge") as charge:
			with self.assertRaises(frappe.ValidationError):
				api.renew_bench(self.bench.name, self.short_plan, "req-guarded")

		charge.assert_not_called()

	# --- A claim that no longer exists must not stop anything ------------------

	def test_a_queued_expiry_stop_outlived_by_its_claim_does_not_run(self):
		"""`queue-long` is one worker, so a claimed stop can sit behind a two-hour deploy.

		By the time it runs, the user may have stopped the bench themselves and started it
		again — buying a new window. The row then reads `Active` with no claim on it, which is
		also what a user pressing Stop looks like, so the job has to say which one it is.
		"""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		self.expire()
		self.claim()
		self.stop_the_bench()
		metering.on_bench_running(self.running_bench())
		frappe.db.set_value(BENCH, self.bench.name, "status", "Running", update_modified=False)

		with patch.object(deploy_manager, "stop_container") as stop, patch.object(frappe.db, "commit"):
			deploy_manager.stop_bench(self.bench.name, from_claim=True)

		stop.assert_not_called()
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Running")
		self.assertEqual(self.lease_state(), lease.ACTIVE)

	def test_a_user_pressed_stop_carries_no_claim_and_always_goes_ahead(self):
		"""The control. The same row state, and the opposite answer, because the caller differs."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())

		with patch.object(deploy_manager, "stop_container") as stop, patch.object(frappe.db, "commit"):
			deploy_manager.stop_bench(self.bench.name)

		stop.assert_called_once()
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Stopped")

	def test_the_sweep_enqueues_a_stop_that_says_it_came_from_a_claim(self):
		self.enable_credits()
		self.expire()
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			lease.claim_due(50)
		self.assertTrue(enqueue.call_args.kwargs["from_claim"])

	# --- Renew: idempotency ----------------------------------------------------

	def test_three_clicks_carrying_one_request_id_charge_once(self):
		"""Three tabs of impatient clicking is the ordinary case, not the exotic one."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		bought = self.deadline()

		with self.renewing():
			for _ in range(3):
				api.renew_bench(self.bench.name, self.short_plan, "req-same")

		self.assertEqual(len(self.usage_rows()), 2)
		self.assertEqual(self.deadline(), bought + HALF_HOUR * 60)
		self.assertEqual(self.balance(), GRANT - 2 * HALF_HOUR_CREDITS)

	def test_two_request_ids_charge_twice(self):
		"""Idempotency must not swallow a genuine second purchase."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())
		bought = self.deadline()

		with self.renewing():
			api.renew_bench(self.bench.name, self.short_plan, "req-first")
			api.renew_bench(self.bench.name, self.short_plan, "req-second")

		self.assertEqual(len(self.usage_rows()), 3)
		self.assertEqual(self.deadline(), bought + 2 * HALF_HOUR * 60)

	def test_the_replay_guard_reads_under_the_lock(self):
		"""This session is REPEATABLE READ, so a plain read answers from the snapshot the
		transaction opened — before the racing click committed — and charges the same click twice."""
		self.enable_credits()
		with patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql:
			account.request_posted("req-never-seen")
		self.assertTrue(
			[statement for statement in self.statements(sql) if "FOR UPDATE" in statement],
			"the replay guard read the ledger without a locking read",
		)

	def test_request_id_has_no_default(self):
		"""A key the server invents for a caller who sent none is not an idempotency key."""
		parameter = inspect.signature(api.renew_bench).parameters["request_id"]
		self.assertIs(parameter.default, inspect.Parameter.empty)

	# --- Renew: the grace window -----------------------------------------------

	def test_grace_ends_when_the_reaper_would_take_the_bench(self):
		self.enable_credits()
		self.set_credit_setting("reap_after_days", 3)
		self.stop_the_bench()
		self.assertAlmostEqual(lease.grace_ends_at(self.bench_row()), lease.now_ts() + 3 * 86400, delta=60)

	def test_nothing_reaps_the_bench_when_the_window_is_zero(self):
		"""`0` is unlimited, here as everywhere — so renew never stops being the answer."""
		self.enable_credits()
		self.set_credit_setting("reap_after_days", 0)
		self.stop_the_bench()
		self.assertIsNone(lease.grace_ends_at(self.bench_row()))

	def test_a_renewal_inside_grace_starts_the_container_it_already_has(self):
		"""The container still exists — expiry only stopped it — so this is a start, not a rebuild."""
		self.enable_credits()
		self.set_credit_setting("reap_after_days", 7)
		self.stop_the_bench()

		with self.renewing() as docker:
			api.renew_bench(self.bench.name, self.short_plan, "req-restore")

		docker.start.assert_called_once_with("lease-container")
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Running")
		self.assertEqual(self.lease_state(), lease.ACTIVE)

	def test_a_renewal_after_grace_has_lapsed_says_redeploy(self):
		"""A button that fails is worse than one that changed."""
		self.enable_credits()
		self.set_credit_setting("reap_after_days", 1)
		self.stop_the_bench()
		self.age_the_bench(days=3)
		before = self.balance()

		with self.renewing(), self.assertRaises(frappe.ValidationError) as refused:
			api.renew_bench(self.bench.name, self.short_plan, "req-too-late")

		self.assertIn("redeploy", str(refused.exception).lower())
		self.assertEqual(self.balance(), before)

	# --- Renew: the push -------------------------------------------------------

	def test_a_renewal_pushes_the_new_deadline_to_the_owner_alone(self):
		self.enable_credits()
		metering.on_bench_running(self.running_bench())

		with self.renewing() as docker:
			api.renew_bench(self.bench.name, self.short_plan, "req-push")

		events = self.lease_events(docker.publish, lease.RENEWED_EVENT)
		self.assertEqual(len(events), 1)
		payload = events[0].args[1]
		self.assertEqual(events[0].kwargs["user"], self.user)
		self.assertTrue(events[0].kwargs["after_commit"])
		self.assertEqual(payload["bench"], self.bench.name)
		self.assertEqual(payload["expires_at_ts"], self.deadline())
		self.assertGreaterEqual(payload["revision"], payload["server_now_ms"] - 1000)
		self.assertNotIn("ssh_password", payload)

	# --- The free reset, refused explicitly ------------------------------------

	def test_a_redeploy_charges_a_full_lease_and_starts_a_fresh_clock(self):
		"""The reference platform reset the clock free, so their own renew dialog told users to
		redeploy instead and the paid button was pointless."""
		self.enable_credits()
		metering.on_bench_running(self.running_bench())

		with (
			patch.object(deploy_manager, "stop_container"),
			patch.object(deploy_manager, "remove_container"),
			patch.object(deploy_manager, "_delete_instance_route"),
			patch.object(deploy_manager, "_drop_site_database"),
			patch.object(frappe.db, "commit"),
		):
			deploy_manager.teardown_bench(frappe.get_doc(BENCH, self.bench.name))
		self.assertEqual(self.deadline(), 0)

		frappe.db.set_value(BENCH, self.bench.name, "status", "Running", update_modified=False)
		metering.on_bench_running(self.running_bench())

		self.assertEqual(len(self.usage_rows()), 2)
		self.assertEqual(self.balance(), GRANT - 2 * HALF_HOUR_CREDITS)
		self.assertAlmostEqual(self.deadline(), lease.now_ts() + HALF_HOUR * 60, delta=5)

	# --- The deadline is not a client claim ------------------------------------

	def test_a_tenant_cannot_write_its_own_deadline(self):
		"""A writable `expires_at_ts` is a free extension, so the fields sit at permlevel 1."""
		self.enable_credits()
		planted = self.expire(seconds_ago=1)
		frappe.set_user(self.user)
		try:
			frappe.client.set_value(BENCH, self.bench.name, "expires_at_ts", lease.now_ts() + 86400)
		except frappe.PermissionError:
			pass
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(self.deadline(), planted)

	def test_the_switch_is_where_this_module_found_it(self):
		self.assertEqual(
			frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits"),
			self.switch_at_start,
		)


class TestLeaseSweepScope(IntegrationTestCase):
	"""The sweep runs against the whole table, so what it must *not* touch is a test of its own."""

	def test_a_bench_with_no_lease_is_never_claimed(self):
		"""Every row that predates this feature has an empty `lease_state` and a zero deadline."""
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			claimed = lease.claim_due(500)
		unleased = frappe.get_all(
			BENCH, filters={"lease_state": ("in", ["", None])}, pluck="name", limit_page_length=0
		)
		self.assertFalse(set(claimed) & set(unleased))

	def test_the_batch_cap_is_configuration(self):
		"""An operator retunes how many stops one tick may queue without a deploy."""
		self.assertTrue(frappe.get_meta(CREDIT_SETTINGS).has_field("lease_sweep_batch"))

	def test_the_sweep_index_exists(self):
		"""`(lease_state, expires_at_ts)` is the priority queue — equality, then a sorted range."""
		self.assertTrue(frappe.db.has_index(f"tab{BENCH}", lease.SWEEP_INDEX))


class TestLeasePlanCatalog(IntegrationTestCase):
	def test_the_seeded_catalog_runs_from_half_an_hour_to_a_week(self):
		seed_defaults()
		rows = frappe.get_all(PLAN, filters={"is_active": 1}, fields=["minutes"], order_by="minutes asc")
		minutes = [row.minutes for row in rows]
		self.assertIn(HALF_HOUR, minutes)
		self.assertIn(WEEK, minutes)

	def test_a_week_is_cheaper_per_hour_than_half_an_hour(self):
		"""Credits per row, not a rate — selling durations is the point of a catalog."""
		seed_defaults()
		short = frappe.db.get_value(PLAN, {"minutes": HALF_HOUR}, ["minutes", "credits"], as_dict=True)
		week = frappe.db.get_value(PLAN, {"minutes": WEEK}, ["minutes", "credits"], as_dict=True)
		self.assertLess(week.credits / week.minutes, short.credits / short.minutes)

	def test_seeding_twice_leaves_one_catalog(self):
		seed_defaults()
		before = frappe.db.count(PLAN)
		seed_defaults()
		self.assertEqual(frappe.db.count(PLAN), before)


class TestLeaseAccountingSurface(IntegrationTestCase):
	def test_the_module_docstring_no_longer_promises_two_meters(self):
		"""After this phase there is one meter — custom image builds — and one lease charge.

		A docstring that describes a system the code no longer has is the next reader's first
		wrong assumption, so the sentence is pinned rather than trusted.
		"""
		self.assertNotIn("Only two meters exist", metering.__doc__)
		self.assertIn("lease", metering.__doc__.lower())

	def test_no_scheduled_job_can_raise_a_burn_rate(self):
		"""The nightly reconciler re-derives a rate from flags nothing writes any more.

		Left scheduled, it rebuilt one within a minute of credits being switched on against a
		fleet carrying flags from a previous release — a second billing system beside the lease.
		"""
		self.assertNotIn(
			"benchpress.credits.reconcile.reconcile_burn_rates",
			frappe.get_hooks("scheduler_events").get("daily", []),
		)

	def test_no_lifecycle_hook_reaches_the_hourly_meter(self):
		"""Two meters beside each other bill the same hour twice."""
		source = inspect.getsource(metering)
		self.assertNotIn("account.start_burn", source)
		self.assertNotIn("account.stop_burn", source)
