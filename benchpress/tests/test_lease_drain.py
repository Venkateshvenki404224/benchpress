# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Precision and drain: the gauge, the reclaim, the parking, the node and the grace period.

Phase 3 left a correct lease on a slow, narrow path. Four failures that path cannot see are what
this module pins, and each of them is silent in production rather than loud.

**Overflow writes nothing anywhere.** If leases fall due faster than `batch cap x cadence`, every
one of them overruns, forever, and no log records it. The gauge is the only alarm there can be.

**A worker killed mid-batch strands its claims.** The claim succeeded, so the next sweep does not
see those rows at all — they sit in `Stopping` until somebody notices a bench that will not die.

**A stop that can never succeed must stop asking.** A row whose Docker call keeps failing takes a
batch slot on every tick and delays the leases queued behind it.

**A stop routed to the wrong daemon reports success.** `docker_manager.stop_container` swallows
`NotFound`, so a bench held on another host is marked `Stopped` while its container keeps running.
There is one node today; the field and the guard land before there are two, because the alternative
is backfilling from Docker inspection across live hosts.

Nothing here commits. `claim_due` and `reclaim_stalled` do, once per row, so every test that reaches
them mocks `frappe.db.commit`.
"""

import inspect
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from benchpress import deploy_manager, docker_manager, hooks, lifecycle
from benchpress.credits import drain, lease, warden
from benchpress.credits.seed import seed_defaults
from benchpress.tests.test_lease import _ensure_bench, _ensure_lab, _ensure_plan, _ensure_user

BENCH = "Bench Instance"
BENCHPRESS_SETTINGS = "BenchPress Settings"
CREDIT_SETTINGS = "Credit Settings"
PLAN = "Lease Plan"

HALF_HOUR = 30
USER = "lease-drain-owner@example.com"
OTHER_NODE = "worker-b"


class TestLeaseDrain(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		cls.default_plan_at_start = frappe.db.get_single_value(CREDIT_SETTINGS, "default_lease_plan")
		cls.user = _ensure_user(USER, "Lease Drain Owner")
		cls.plan = _ensure_plan("Lease Drain 30 Minutes", HALF_HOUR, 0.0)
		cls.labs = [_ensure_lab(f"lease-drain-{index}", cls.user) for index in range(3)]
		cls.benches = [_ensure_bench(lab, cls.user) for lab in cls.labs]
		cls.bench = cls.benches[0]
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		try:
			frappe.db.set_single_value(CREDIT_SETTINGS, "default_lease_plan", cls.default_plan_at_start)
			frappe.delete_doc(PLAN, cls.plan, force=True, ignore_permissions=True)
			frappe.clear_cache(doctype=CREDIT_SETTINGS)
		finally:
			for bench in cls.benches:
				frappe.delete_doc(BENCH, bench.name, force=True, ignore_permissions=True)
			for lab in cls.labs:
				frappe.delete_doc("Lab", lab.name, force=True, ignore_permissions=True)
			if frappe.db.exists("User", cls.user):
				frappe.delete_doc("User", cls.user, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- fixtures were committed, so the cleanup must be too
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		self.reset_benches()
		self.set_credits_enabled(1)
		# Reclaim and parking are asserted against the default attempt limit, not against whatever
		# the site this runs on has configured. The live site sets it to 1.
		self.set_credit_setting("lease_max_attempts", lease.DEFAULT_MAX_ATTEMPTS)
		frappe.cache().delete_value(drain.OVERFLOW_STREAK_KEY)

	# --- Fixtures -------------------------------------------------------------

	def reset_benches(self) -> None:
		for bench in self.benches:
			frappe.db.set_value(
				BENCH,
				bench.name,
				{
					"status": "Running",
					"container_id": "drain-container",
					"node": None,
					"expires_at_ts": 0,
					"lease_state": "",
					"stop_claimed_at": None,
					"expiry_attempts": 0,
					"stop_started_at": None,
					"container_stopped_at": None,
					"expiry_lateness": None,
				},
				update_modified=False,
			)

	def set_credits_enabled(self, value: int) -> None:
		original = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		self.addCleanup(self.write_single, BENCHPRESS_SETTINGS, "enable_credits", original)
		self.write_single(BENCHPRESS_SETTINGS, "enable_credits", value)

	def set_credit_setting(self, field: str, value) -> None:
		original = frappe.db.get_single_value(CREDIT_SETTINGS, field)
		self.addCleanup(self.write_single, CREDIT_SETTINGS, field, original)
		self.write_single(CREDIT_SETTINGS, field, value)

	def write_single(self, doctype: str, field: str, value) -> None:
		"""Committed, because the code under test commits and would otherwise strand the restore."""
		frappe.db.set_single_value(doctype, field, value)
		frappe.db.commit()  # nosemgrep -- see above: the restore must outlive the rollback
		frappe.clear_cache(doctype=doctype)

	def expire(self, bench_name: str, seconds_ago: int = 60) -> int:
		deadline = lease.now_ts() - seconds_ago
		frappe.db.set_value(
			BENCH,
			bench_name,
			{"expires_at_ts": deadline, "lease_state": lease.ACTIVE, "expiry_attempts": 0},
			update_modified=False,
		)
		return deadline

	def expire_all(self, seconds_ago: int = 60) -> None:
		for bench in self.benches:
			self.expire(bench.name, seconds_ago)

	def claim(self, limit: int = 50) -> list[str]:
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			return lease.claim_due(limit)

	def sweep(self) -> dict:
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			return drain.sweep_expired_leases()

	def row(self, bench_name: str, field: str):
		return frappe.db.get_value(BENCH, bench_name, field)

	def age_the_claim(self, bench_name: str, seconds: int) -> None:
		frappe.db.set_value(
			BENCH,
			bench_name,
			"stop_claimed_at",
			add_to_date(now_datetime(), seconds=-seconds),
			update_modified=False,
		)

	def failing_stop(self, bench_name: str) -> None:
		with (
			patch.object(lifecycle, "stop_container", side_effect=RuntimeError("docker is down")),
			patch.object(frappe.db, "commit"),
		):
			self.assertRaises(RuntimeError, lifecycle.stopped, bench_name, from_claim=True)

	# --- The backlog gauge ----------------------------------------------------

	def test_the_gauge_reports_what_the_batch_cap_left_behind(self):
		"""The silent failure this whole phase exists to make loud.

		Arrivals above `cap x cadence` mean every lease overruns forever and nothing is written
		anywhere. The overflow is the only number that shows it.
		"""
		self.expire_all()
		self.set_credit_setting("lease_sweep_batch", 1)
		result = self.sweep()

		self.assertEqual(result["due"], 3)
		self.assertEqual(result["cap"], 1)
		self.assertEqual(result["overflow"], 2)
		self.assertEqual(len(result["claimed"]), 1)

	def test_a_backlog_inside_the_cap_reports_no_overflow(self):
		self.expire(self.bench.name)
		self.set_credit_setting("lease_sweep_batch", 50)
		result = self.sweep()

		self.assertEqual(result["due"], 1)
		self.assertEqual(result["overflow"], 0)

	def test_two_consecutive_overflows_raise_an_alarm(self):
		"""One tick behind is a burst. Two in a row is arrivals outrunning the drain."""
		self.expire_all()
		self.set_credit_setting("lease_sweep_batch", 1)
		with patch("frappe.log_error") as log_error:
			self.sweep()
			self.assertEqual(log_error.call_count, 0)
			self.sweep()
			self.assertEqual(log_error.call_count, 1)

	def test_a_cleared_backlog_resets_the_streak(self):
		self.expire_all()
		self.set_credit_setting("lease_sweep_batch", 1)
		self.sweep()
		self.reset_benches()
		self.sweep()
		self.expire_all()
		with patch("frappe.log_error") as log_error:
			self.sweep()
		log_error.assert_not_called()

	def test_the_gauge_counts_the_fleet_not_the_batch(self):
		"""`due` is measured before the claim, or a full batch always reports a clear backlog."""
		self.expire_all()
		self.assertEqual(drain.backlog(), 3)

	# --- Reclaim --------------------------------------------------------------

	def test_a_claim_older_than_the_reclaim_interval_is_re_enqueued(self):
		"""A worker killed mid-batch leaves rows the next sweep cannot see: they are not `Active`."""
		self.expire(self.bench.name)
		self.claim()
		self.set_credit_setting("lease_reclaim_seconds", 300)
		self.age_the_claim(self.bench.name, 600)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			reclaimed = drain.reclaim_stalled()

		self.assertEqual(reclaimed, [self.bench.name])
		self.assertEqual(enqueue.call_args.kwargs["bench_name"], self.bench.name)
		self.assertTrue(enqueue.call_args.kwargs["from_claim"])

	def test_a_reclaim_counts_against_the_attempt_limit(self):
		"""Otherwise a permanently stuck row is re-enqueued every interval until somebody looks."""
		self.expire(self.bench.name)
		self.claim()
		self.set_credit_setting("lease_reclaim_seconds", 300)
		self.age_the_claim(self.bench.name, 600)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			drain.reclaim_stalled()

		self.assertEqual(self.row(self.bench.name, "expiry_attempts"), 1)

	def test_a_reclaim_refreshes_the_claim_it_re_enqueued(self):
		"""Without a new stamp the next interval reclaims the same row while its job is in flight."""
		self.expire(self.bench.name)
		self.claim()
		self.set_credit_setting("lease_reclaim_seconds", 300)
		self.age_the_claim(self.bench.name, 600)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			drain.reclaim_stalled()
			self.assertEqual(drain.reclaim_stalled(), [])

	def test_a_fresh_claim_is_left_alone(self):
		"""A stop can sit behind a two-hour deploy. Reclaiming it early is a second stop job."""
		self.expire(self.bench.name)
		self.claim()
		self.set_credit_setting("lease_reclaim_seconds", 300)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			self.assertEqual(drain.reclaim_stalled(), [])
		enqueue.assert_not_called()

	def test_a_claim_with_no_stamp_is_reclaimable(self):
		"""There is no path that writes one, and a row that has none is stranded forever."""
		self.expire(self.bench.name)
		self.claim()
		frappe.db.set_value(BENCH, self.bench.name, "stop_claimed_at", None, update_modified=False)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertEqual(drain.reclaim_stalled(), [self.bench.name])

	def test_the_reclaim_interval_is_configuration(self):
		self.expire(self.bench.name)
		self.claim()
		self.age_the_claim(self.bench.name, 120)
		self.set_credit_setting("lease_reclaim_seconds", 60)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertEqual(drain.reclaim_stalled(), [self.bench.name])

	def test_the_sweep_reclaims_as_well_as_claims(self):
		self.expire(self.bench.name)
		self.claim()
		self.set_credit_setting("lease_reclaim_seconds", 300)
		self.age_the_claim(self.bench.name, 600)

		self.assertEqual(self.sweep()["reclaimed"], [self.bench.name])

	# --- Parking --------------------------------------------------------------

	def test_a_stop_that_keeps_failing_parks_rather_than_going_quiet(self):
		"""Skipping the row hides it. Parking it is an error state somebody can query for."""
		self.set_credit_setting("lease_max_attempts", 2)
		self.expire(self.bench.name)
		self.claim()
		self.failing_stop(self.bench.name)
		self.assertEqual(self.row(self.bench.name, "lease_state"), lease.ACTIVE)

		self.claim()
		self.failing_stop(self.bench.name)
		self.assertEqual(self.row(self.bench.name, "lease_state"), lease.FAILED)
		self.assertEqual(self.row(self.bench.name, "expiry_attempts"), 2)

	def test_a_parked_row_takes_no_further_batch_slot(self):
		self.expire(self.bench.name)
		frappe.db.set_value(BENCH, self.bench.name, "lease_state", lease.FAILED, update_modified=False)
		self.assertEqual(self.claim(), [])

	def test_a_parked_row_is_not_reclaimed(self):
		"""It left `Stopping`, so the reclaim must not pull it back into the queue every interval."""
		self.expire(self.bench.name)
		frappe.db.set_value(
			BENCH,
			self.bench.name,
			{"lease_state": lease.FAILED, "stop_claimed_at": add_to_date(now_datetime(), seconds=-9999)},
			update_modified=False,
		)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue"):
			self.assertEqual(drain.reclaim_stalled(), [])

	def test_a_parked_row_does_not_count_as_backlog(self):
		"""It is not going to be claimed, so counting it would leave the alarm on forever."""
		self.expire_all()
		frappe.db.set_value(BENCH, self.bench.name, "lease_state", lease.FAILED, update_modified=False)
		self.assertEqual(drain.backlog(), 2)

	def test_a_reclaim_at_the_attempt_limit_parks_instead_of_re_enqueueing(self):
		self.set_credit_setting("lease_max_attempts", 1)
		self.expire(self.bench.name)
		self.claim()
		self.age_the_claim(self.bench.name, 9999)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			self.assertEqual(drain.reclaim_stalled(), [])
		enqueue.assert_not_called()
		self.assertEqual(self.row(self.bench.name, "lease_state"), lease.FAILED)

	def test_the_attempt_limit_is_configuration(self):
		self.set_credit_setting("lease_max_attempts", 1)
		self.assertEqual(lease.max_attempts(), 1)

	def test_a_renewal_clears_a_parked_lease(self):
		"""Parking is a stuck stop, not a verdict. Arming the clock again must reset the state."""
		frappe.db.set_value(
			BENCH,
			self.bench.name,
			{"lease_state": lease.FAILED, "expiry_attempts": 9},
			update_modified=False,
		)
		bench = frappe.get_doc(BENCH, self.bench.name)
		lease.extend(bench, {"minutes": HALF_HOUR})

		self.assertEqual(self.row(self.bench.name, "lease_state"), lease.ACTIVE)
		self.assertEqual(self.row(self.bench.name, "expiry_attempts"), 0)

	# --- Node routing ---------------------------------------------------------

	def test_a_stop_is_enqueued_to_the_queue_of_the_node_holding_the_container(self):
		frappe.db.set_value(BENCH, self.bench.name, "node", OTHER_NODE, update_modified=False)
		self.expire(self.bench.name)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			lease.claim_due(50)

		self.assertEqual(enqueue.call_args.kwargs["queue"], f"{lease.STOP_QUEUE}_{OTHER_NODE}")

	def test_an_empty_node_keeps_the_local_stop_queue(self):
		"""Every row today. The field arrives before the second node, and changes nothing until then."""
		self.expire(self.bench.name)

		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			lease.claim_due(50)

		self.assertEqual(enqueue.call_args.kwargs["queue"], lease.STOP_QUEUE)

	def test_a_stop_never_queues_behind_a_deploy(self):
		"""`queue-long` carries `deploy_bench` with a two-hour timeout and one worker."""
		self.assertNotEqual(lease.STOP_QUEUE, "long")

	def test_the_local_node_names_its_own_queue(self):
		with patch.object(lease, "local_node", return_value=OTHER_NODE):
			self.assertEqual(lease.stop_queue_for(OTHER_NODE), lease.STOP_QUEUE)

	def test_the_node_comes_from_the_site_config(self):
		with patch.dict(frappe.conf, {"benchpress_node": OTHER_NODE}):
			self.assertEqual(lease.local_node(), OTHER_NODE)

	def test_a_stop_on_the_wrong_node_refuses_instead_of_reporting_success(self):
		"""`stop_container` swallows `NotFound`, so the wrong daemon marks the row `Stopped` while
		the container keeps running somewhere else — free compute, invisible in every log."""
		frappe.db.set_value(BENCH, self.bench.name, "node", OTHER_NODE, update_modified=False)
		self.expire(self.bench.name)
		self.claim()

		with (
			patch.object(lifecycle, "stop_container") as stop,
			patch.object(frappe.db, "commit"),
		):
			self.assertRaises(frappe.ValidationError, lifecycle.stopped, self.bench.name, True)

		stop.assert_not_called()
		self.assertEqual(self.row(self.bench.name, "status"), "Running")

	def test_a_bench_on_this_node_stops_normally(self):
		frappe.db.set_value(BENCH, self.bench.name, "node", OTHER_NODE, update_modified=False)
		self.expire(self.bench.name)
		self.claim()

		with (
			patch.object(lease, "local_node", return_value=OTHER_NODE),
			patch.object(lifecycle, "stop_container") as stop,
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			lifecycle.stopped(self.bench.name, from_claim=True)

		stop.assert_called_once()
		self.assertEqual(self.row(self.bench.name, "status"), "Stopped")

	def test_a_deploy_stamps_the_node_beside_the_container_id(self):
		"""Backfilling this later means inspecting Docker across live hosts while benches run."""
		source = inspect.getsource(lifecycle._deploy_bench)
		self.assertIn("bench.node = lease.local_node()", source)

	# --- The warden -----------------------------------------------------------

	def test_the_warden_claims_through_the_same_protocol_as_the_cron(self):
		"""One claim, two callers. A second protocol is a second set of races to get right."""
		with (
			patch.object(lease, "claim_due", return_value=[]) as claim_due,
			patch.object(drain, "reclaim_stalled", return_value=[]),
		):
			warden.tick()
			self.assertEqual(claim_due.call_count, 1)
			drain.sweep_expired_leases()
			self.assertEqual(claim_due.call_count, 2)

	def test_the_warden_sleeps_until_the_next_deadline(self):
		now = lease.now_ts()
		self.assertEqual(warden.sleep_for(now + 3, now), 3)

	def test_the_warden_never_sleeps_past_its_ceiling(self):
		"""The ceiling is what makes it safe to restart: a long sleep is a long blind spot."""
		now = lease.now_ts()
		self.assertEqual(warden.sleep_for(now + 86400, now), warden.POLL_CEILING)

	def test_an_empty_fleet_sleeps_the_ceiling(self):
		now = lease.now_ts()
		self.assertEqual(warden.sleep_for(None, now), warden.POLL_CEILING)

	def test_a_deadline_already_past_still_yields_the_floor(self):
		"""Zero would spin the loop against the database at whatever rate Python manages."""
		now = lease.now_ts()
		self.assertEqual(warden.sleep_for(now - 500, now), warden.POLL_FLOOR)

	def test_the_warden_reads_the_earliest_deadline_on_the_fleet(self):
		self.expire(self.benches[1].name, seconds_ago=-600)
		self.expire(self.benches[2].name, seconds_ago=-300)
		self.assertEqual(warden.next_deadline(), lease.now_ts() + 300)

	def test_the_warden_sleeps_the_ceiling_when_credits_are_off(self):
		self.set_credits_enabled(0)
		self.expire(self.bench.name)
		with patch.object(frappe.db, "commit"), patch("frappe.enqueue") as enqueue:
			self.assertEqual(warden.tick(), warden.POLL_CEILING)
		enqueue.assert_not_called()

	def test_the_cron_still_sweeps_with_no_warden_running(self):
		"""The warden is an accelerator. Deleting the cron because it is faster removes the net
		that makes restarting the warden safe."""
		self.assertIn(
			"benchpress.credits.drain.sweep_expired_leases",
			[job for jobs in hooks.scheduler_events["cron"].values() for job in jobs],
		)
		self.expire(self.bench.name)
		self.assertEqual(self.sweep()["claimed"], [self.bench.name])

	def test_the_warden_drops_the_caches_a_request_would_have_dropped(self):
		"""The difference between a service and a request, and it is not academic.

		`frappe.local` never resets in a long-lived process, and `frappe.cache.get_value` reads
		`frappe.local.cache` before Redis. A warden started while credits were off therefore
		reads `enable_credits` once and never again: it sleeps its ceiling forever while leases
		fall due, and the only evidence is that expiry is back to the four-minute cron.
		"""
		frappe.local.cache["lease-drain-stale"] = "stale"
		frappe.db.value_cache["Lease Drain Stale"] = {"stale": "stale"}
		with patch.object(drain, "sweep_expired_leases"):
			warden.tick()

		self.assertNotIn("lease-drain-stale", frappe.local.cache)
		self.assertNotIn("Lease Drain Stale", frappe.db.value_cache)

	def test_the_warden_is_not_a_scheduled_job(self):
		"""It is a long-lived service. On the scheduler it would be a four-minute loop again."""
		scheduled = repr(hooks.scheduler_events)
		self.assertNotIn("warden", scheduled)

	# --- The SLO --------------------------------------------------------------

	def test_a_stop_records_how_late_it_was_against_the_deadline(self):
		"""`container_stopped_at - expires_at_ts` is the SLO for this whole feature."""
		self.expire(self.bench.name, seconds_ago=90)
		self.claim()

		with (
			patch.object(lifecycle, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			lifecycle.stopped(self.bench.name, from_claim=True)

		lateness = self.row(self.bench.name, "expiry_lateness")
		self.assertIsNotNone(lateness)
		self.assertGreaterEqual(lateness, 90)
		self.assertTrue(self.row(self.bench.name, "container_stopped_at"))
		self.assertTrue(self.row(self.bench.name, "stop_started_at"))

	def test_recorded_lateness_is_never_negative(self):
		"""A clock that moved backwards must not report the platform stopping leases early."""
		self.expire(self.bench.name, seconds_ago=-600)
		frappe.db.set_value(BENCH, self.bench.name, "lease_state", lease.STOPPING, update_modified=False)
		bench = frappe.get_doc(BENCH, self.bench.name)
		lease.record_stopped(bench, expired=True)

		self.assertEqual(self.row(self.bench.name, "expiry_lateness"), 0)

	def test_a_user_pressed_stop_records_no_lateness(self):
		"""It was not late — nothing was due. A zero here would flatter the histogram."""
		with (
			patch.object(lifecycle, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			lifecycle.stopped(self.bench.name)

		self.assertIsNone(self.row(self.bench.name, "expiry_lateness"))
		self.assertTrue(self.row(self.bench.name, "container_stopped_at"))

	def test_the_histogram_reads_back_what_the_stops_recorded(self):
		self.expire(self.bench.name, seconds_ago=90)
		self.claim()
		with (
			patch.object(lifecycle, "stop_container"),
			patch.object(frappe.db, "commit"),
			patch("frappe.publish_realtime"),
		):
			lifecycle.stopped(self.bench.name, from_claim=True)

		report = drain.stop_slo()
		self.assertGreaterEqual(report["count"], 1)
		self.assertGreaterEqual(report["max"], 90)
		self.assertGreaterEqual(report["p50"], 0)
		self.assertEqual(sum(report["buckets"].values()), report["count"])

	def test_an_empty_window_reports_zeroes_rather_than_failing(self):
		report = drain.stop_slo(hours=0)
		self.assertEqual(report["count"], 0)
		self.assertEqual(report["max"], 0)

	# --- The grace period -----------------------------------------------------

	def test_the_stop_grace_period_is_configuration(self):
		with (
			patch.object(docker_manager, "get_client") as client,
			patch.object(docker_manager, "stop_grace_seconds", return_value=7),
		):
			docker_manager.stop_container("drain-container")

		client.return_value.containers.get.return_value.stop.assert_called_once_with(timeout=7)

	def test_the_grace_default_is_not_the_thirty_seconds_phase_one_measured(self):
		"""Every bench container exits 137: PID 1 is `tail`, which installs no SIGTERM handler,
		so the grace period is waited out in full and then SIGKILLed. Thirty seconds of that per
		stop is the drain rate, and it buys nothing."""
		self.assertLessEqual(docker_manager.stop_grace_seconds(), 10)
