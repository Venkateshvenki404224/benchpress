# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The two scheduled sweeps: the balance check and the reaper.

Both are asserted the same way — the decision, and the fact that the decision is *only* a decision.
Neither job may touch Docker: they run on `queue-short`, which has no socket mounted, so a test
that let one through would pass here and write `Unknown` in production. Every stop and every
teardown is therefore checked as an `frappe.enqueue` to `queue="long"`.

Warnings are asserted for their *cardinality*, not just their content. "At most once per session"
is the property that decides whether these notices get read or muted, and it is the one a refactor
loses silently.

Both sweeps scan the whole site, so every assertion here narrows to the two owners this class
creates before it counts. A second **funded** owner is the control: `enforce_limits` decides per
owner, so a sweep that stopped everything would still satisfy an assertion about one bench under
one owner, and only a neighbour that must survive catches it.

As in `test_credit_guard`, nothing in this module commits: `IntegrationTestCase` rolls back once per
class, so a single commit would make every retuned price durable on the site.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime

from benchpress.credits import account, config, reaper, sweep
from benchpress.credits.seed import seed_defaults

ACCOUNT = "Credit Account"
BENCH = "Bench Instance"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
LEDGER = "Credit Ledger Entry"

GRANT = 40.0
REAP_AFTER_DAYS = 7
USER = "sweep-user@example.com"
NEIGHBOUR = "sweep-neighbour@example.com"

TUNED_SETTINGS = ("reap_after_days", "low_balance_warn_percent")


def _ensure_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Sweep",
				"send_welcome_email": 0,
				"roles": [{"role": "BenchPress User"}],
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
				"title": f"Sweep {lab_id}",
				"frappe_version": "version-15",
				"image_tag": "benchpress/test:latest",
				"instance_size": "Small",
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


def _ensure_database_server() -> str:
	"""A server row for the teardown to drop a database on.

	A dev site already has one from `create_default_database_server`; a CI site does not, and a
	teardown test that silently skipped the database drop was the whole point of the test. Creating
	one is safe — `DatabaseServer.before_insert` only fills defaults and touches no container.
	"""
	existing = frappe.db.get_value("Database Server", {}, "name")
	if existing:
		return existing
	server = frappe.get_doc({"doctype": "Database Server", "container_name": "sweep-mariadb"})
	return server.insert(ignore_permissions=True).name


def _ensure_bench(lab, owner: str, **extra):
	from benchpress.benchpress.doctype.bench_instance import get_instance_id

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
				"container_id": "sweep-container",
				"started_at": now_datetime(),
				**extra,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestCreditSweep(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.settings_at_start = {
			field: frappe.db.get_single_value(CREDIT_SETTINGS, field) for field in TUNED_SETTINGS
		}
		cls.database_server = _ensure_database_server()
		cls.user = _ensure_user(USER)
		cls.lab = _ensure_lab("sweep-lab", cls.user)
		cls.bench = _ensure_bench(cls.lab, cls.user)
		cls.neighbour = _ensure_user(NEIGHBOUR)
		cls.neighbour_lab = _ensure_lab("sweep-neighbour-lab", cls.neighbour)
		cls.neighbour_bench = _ensure_bench(cls.neighbour_lab, cls.neighbour)
		cls.owned = {cls.bench.name, cls.neighbour_bench.name}
		# Not committed: the class rollback takes these with it, and one commit here would make
		# every retuned cap and price durable on the site.

	def setUp(self):
		frappe.set_user("Administrator")
		self.restore_economics()
		self.wipe_credits()
		self.reset_benches()
		self.fund(GRANT, self.neighbour)  # before the spies: funding an account enqueues nothing
		self.enqueued = self.spy("frappe.enqueue")
		self.alerts = self.spy("benchpress.notifications.notify_owner")
		self.emails = self.spy("benchpress.notifications.email_owner")

	def spy(self, target: str):
		patcher = patch(target)
		self.addCleanup(patcher.stop)
		return patcher.start()

	# --- The switch off means neither job exists ------------------------------

	def test_neither_job_does_anything_when_credits_are_off(self):
		self.set_credits_enabled(0)
		self.fund(0)
		self.assertEqual(sweep.enforce_limits(), {"checked": 0, "stopped": [], "warned": []})
		self.assertEqual(reaper.reap_stopped_instances(), {"reaped": [], "warned": []})
		self.enqueued.assert_not_called()

	# --- The balance ----------------------------------------------------------

	def test_a_spent_balance_stops_a_running_instance(self):
		self.enable_credits()
		self.fund(0)
		self.assertEqual(self.ours(sweep.enforce_limits()["stopped"]), [self.bench.name])
		self.assert_enqueued("benchpress.lifecycle.stopped")

	def test_a_funded_owner_keeps_running(self):
		self.enable_credits()
		self.fund(GRANT)
		self.assertEqual(self.ours(sweep.enforce_limits()["stopped"]), [])

	def test_an_owner_with_no_account_row_is_not_stopped(self):
		"""Credits were only just switched on; there is no balance to be out of yet."""
		self.enable_credits()
		self.assertFalse(frappe.db.exists(ACCOUNT, self.user))
		self.assertEqual(self.ours(sweep.enforce_limits()["stopped"]), [])

	# --- The two rules the sweep must never break ----------------------------

	def test_the_sweep_never_calls_docker(self):
		self.enable_credits()
		self.fund(0)
		with patch("benchpress.docker_manager.get_client") as get_client:
			sweep.enforce_limits()
		get_client.assert_not_called()

	def test_the_stop_goes_to_the_only_worker_that_can_reach_a_container(self):
		self.enable_credits()
		self.fund(0)
		sweep.enforce_limits()
		stop = self.enqueue_for(self.bench.name)
		self.assertEqual(stop.kwargs["queue"], "long")
		self.assertTrue(stop.kwargs["deduplicate"])

	def test_the_stop_cannot_start_before_the_decision_commits(self):
		"""`lifecycle.stopped` re-reads the row, so a job that runs first acts on a decision that may roll back."""
		sweep._enqueue_stop(self.bench.name)
		self.assertTrue(self.enqueue_for(self.bench.name).kwargs["enqueue_after_commit"])

	def test_the_sweep_does_not_scale_in_query_count(self):
		"""One query per load, whatever the fleet size — never a `get_doc` per instance."""
		self.enable_credits()
		self.fund(GRANT)
		sweep.enforce_limits()  # warm the DocType meta this would otherwise count
		one = self.count_queries(sweep.enforce_limits)

		extra = [_ensure_lab(f"sweep-lab-{index}", self.user) for index in range(2)]
		benches = [_ensure_bench(lab, self.user) for lab in extra]
		self.addCleanup(self.delete_docs, BENCH, [bench.name for bench in benches])
		self.addCleanup(self.delete_docs, "Lab", [lab.name for lab in extra])

		config.clear_size_index()
		self.assertEqual(self.count_queries(sweep.enforce_limits), one)

	# --- Warnings, and how often -------------------------------------------

	def test_the_low_balance_warning_is_sent_once_per_depletion(self):
		self.enable_credits()
		self.fund(self.warn_threshold() / 2)

		sweep.enforce_limits()
		sweep.enforce_limits()
		warnings = self.alerts_for(self.user)
		self.assertEqual(len(warnings), 1)
		self.assertIn("Credits running low", warnings[0].args[1])
		self.assertEqual(self.alerts_for(self.neighbour), [], "the funded owner is the control")

	def test_the_low_balance_warning_re_arms_when_the_balance_recovers(self):
		self.enable_credits()
		self.fund(self.warn_threshold() / 2)
		sweep.enforce_limits()
		self.assertTrue(frappe.db.get_value(ACCOUNT, self.user, "low_balance_warned"))

		self.fund(GRANT)
		sweep.enforce_limits()
		self.assertFalse(frappe.db.get_value(ACCOUNT, self.user, "low_balance_warned"))

	def test_a_healthy_balance_is_never_warned_about(self):
		self.enable_credits()
		self.fund(GRANT)
		sweep.enforce_limits()
		self.assertEqual(self.alerts_for(self.user), [])

	# --- The reaper -----------------------------------------------------------

	def test_the_reaper_takes_only_what_is_past_the_window(self):
		self.enable_credits()
		self.stopped_for_days(REAP_AFTER_DAYS + 1)
		result = reaper.reap_stopped_instances()
		self.assertEqual(self.ours(result["reaped"]), [self.bench.name])
		self.assert_enqueued("benchpress.credits.reaper.reap_bench")

	def test_a_recently_stopped_instance_is_left_alone(self):
		self.enable_credits()
		self.stopped_for_days(1)
		result = reaper.reap_stopped_instances()
		self.assertEqual(self.ours(result["reaped"]), [])
		self.assertEqual(self.ours(result["warned"]), [])

	def test_a_running_instance_is_never_reaped(self):
		self.enable_credits()
		self.stopped_for_days(REAP_AFTER_DAYS + 1)
		frappe.db.set_value(BENCH, self.bench.name, "status", "Running", update_modified=False)
		self.assertEqual(self.ours(reaper.reap_stopped_instances()["reaped"]), [])

	def test_the_reaper_emails_two_days_out_exactly_once(self):
		self.enable_credits()
		self.stopped_for_days(REAP_AFTER_DAYS - 1)

		self.assertEqual(self.ours(reaper.reap_stopped_instances()["warned"]), [self.bench.name])
		self.assertEqual(self.ours(reaper.reap_stopped_instances()["warned"]), [])
		notices = self.emails_for(self.user)
		self.assertEqual(len(notices), 1, "an email a day about the same deletion is spam")
		self.assertIn("will be deleted", notices[0].args[1])

	def test_the_reaper_does_not_warn_before_the_window(self):
		self.enable_credits()
		self.stopped_for_days(REAP_AFTER_DAYS - 4)
		self.assertEqual(self.ours(reaper.reap_stopped_instances()["warned"]), [])
		self.assertEqual(self.emails_for(self.user), [])

	def test_a_zero_reap_window_never_reaps(self):
		self.enable_credits()
		self.set_setting("reap_after_days", 0)
		self.stopped_for_days(100)
		self.assertEqual(reaper.reap_stopped_instances(), {"reaped": [], "warned": []})

	def test_reaping_removes_the_container_and_database_and_keeps_the_lab(self):
		self.enable_credits()
		self.stopped_for_days(REAP_AFTER_DAYS + 1)
		frappe.db.set_value(
			BENCH, self.bench.name, "database_server", self.database_server, update_modified=False
		)

		with (
			patch("frappe.db.commit"),
			patch("benchpress.lifecycle.stop_container") as stop,
			patch("benchpress.lifecycle.remove_container") as remove,
			patch("benchpress.docker_manager.get_client") as client,
			patch("benchpress.mariadb_manager.drop_site_database") as drop,
		):
			reaper.reap_bench(self.bench.name)

		stop.assert_called_once()
		remove.assert_called_once()
		drop.assert_called_once()
		client.return_value.volumes.get.assert_not_called()
		self.assertTrue(frappe.db.exists("Lab", self.lab.name), "the recipe must survive the reap")
		self.assertEqual(frappe.db.get_value(BENCH, self.bench.name, "status"), "Draft")

	def test_reaping_skips_an_instance_that_was_started_again(self):
		"""Between the decision and the job, one click can make the decision wrong."""
		self.enable_credits()
		frappe.db.set_value(BENCH, self.bench.name, "status", "Running", update_modified=False)
		with patch("benchpress.lifecycle.torn_down") as teardown:
			reaper.reap_bench(self.bench.name)
		teardown.assert_not_called()

	# --- Helpers -------------------------------------------------------------

	def restore_economics(self) -> None:
		self.set_credits_enabled(self.switch_at_start)
		for field, value in self.settings_at_start.items():
			self.set_setting(field, value)

	def enable_credits(self) -> None:
		self.set_credits_enabled(1)

	def set_credits_enabled(self, value) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def set_setting(self, field: str, value) -> None:
		frappe.db.set_single_value(CREDIT_SETTINGS, field, value)
		frappe.clear_cache(doctype=CREDIT_SETTINGS)

	def fund(self, credits, user: str | None = None) -> None:
		user = user or self.user
		account.ensure_account(user)
		frappe.db.set_value(
			ACCOUNT,
			user,
			{"balance": credits, "low_balance_warned": 0},
			update_modified=False,
		)

	# --- The fixture universe -------------------------------------------------
	#
	# Both sweeps return every bench on the site, and both notify every owner on it. Narrowing to
	# the rows this class owns keeps the cardinality assertions meaningful instead of vacuous.

	def ours(self, bench_names: list) -> list:
		return [name for name in bench_names if name in self.owned]

	def alerts_for(self, user: str) -> list:
		return [call for call in self.alerts.call_args_list if call.args[0] == user]

	def emails_for(self, user: str) -> list:
		return [call for call in self.emails.call_args_list if call.args[0] == user]

	def enqueue_for(self, bench_name: str):
		"""This bench's own enqueue call. On a site with real rows it is never the last one."""
		calls = [call for call in self.enqueued.call_args_list if call.kwargs.get("bench_name") == bench_name]
		self.assertEqual(len(calls), 1, f"expected exactly one enqueue for {bench_name}")
		return calls[0]

	def warn_threshold(self) -> float:
		percent = config.settings().low_balance_warn_percent
		return GRANT * percent / 100.0

	def stopped_for_days(self, days) -> None:
		"""`modified` is stopped-since, so the reap window is set by writing it directly."""
		frappe.db.set_value(BENCH, self.bench.name, "status", "Stopped", update_modified=False)
		frappe.db.set_value(
			BENCH, self.bench.name, "modified", add_days(now_datetime(), -days), update_modified=False
		)

	def reset_benches(self) -> None:
		for name in self.owned:
			frappe.db.set_value(
				BENCH,
				name,
				{
					"status": "Running",
					"started_at": now_datetime(),
					"reap_warned_at": None,
					"database_server": None,
				},
				update_modified=True,
			)

	def assert_enqueued(self, method: str) -> None:
		call = self.enqueue_for(self.bench.name)
		self.assertEqual(call.args[0], method)
		self.assertEqual(call.kwargs["queue"], "long")

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
		frappe.set_user("Administrator")
		for name in names:
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	def wipe_credits(self) -> None:
		frappe.db.delete(LEDGER, {"account": ("in", [USER, NEIGHBOUR])})
		frappe.db.delete(ACCOUNT, {"user": ("in", [USER, NEIGHBOUR])})
