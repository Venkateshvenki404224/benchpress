# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The listener must not alert on an ordinary stop, and must call an oom-then-die pair one death.

Plain dicts throughout: the drain and flush functions take events, never a Docker client.
"""

import queue
import unittest
from unittest.mock import patch

import frappe

from benchpress import docker_events

BENCH = "bench-001"
SETTLE = 15


def event(action: str, bench: str | None = BENCH, exit_code: int | None = None, at: int = 1787722107):
	attributes = {"benchpress.managed": "true", "image": "benchpress/lab:v16"}
	if bench:
		attributes["benchpress.bench_name"] = bench
	if exit_code is not None:
		attributes["exitCode"] = str(exit_code)
	return {"Action": action, "time": at, "Actor": {"ID": "c0ffee1234567890", "Attributes": attributes}}


def _inbox(*events) -> queue.Queue:
	inbox: queue.Queue = queue.Queue()
	for item in events:
		inbox.put(item)
	return inbox


def _drain(*events) -> tuple[dict, dict]:
	"""Drain the given events and report `(pending, stats)`."""
	pending: dict = {}
	stats = {"events_seen": 0, "orphans": 0, "connected_since": 0}
	with patch("benchpress.docker_events.settle_seconds", return_value=SETTLE):
		docker_events._drain(_inbox(*events), pending, stats)
	return pending, stats


class TestDrain(unittest.TestCase):
	def test_the_label_names_the_bench(self):
		pending, stats = _drain(event("die", exit_code=137))
		self.assertEqual(list(pending), [BENCH])
		self.assertEqual(stats["events_seen"], 1)

	def test_an_event_with_no_bench_label_is_ignored(self):
		pending, stats = _drain(event("die", bench=None))
		self.assertEqual(pending, {})
		self.assertEqual(stats["events_seen"], 1)

	def test_an_unwatched_action_is_ignored(self):
		pending, _stats = _drain(event("start"))
		self.assertEqual(pending, {})

	def test_a_die_alone_is_a_death_carrying_its_exit_code(self):
		pending, _stats = _drain(event("die", exit_code=137))
		self.assertEqual(pending[BENCH]["kind"], "bench_died")
		self.assertEqual(pending[BENCH]["severity"], "error")
		self.assertEqual(pending[BENCH]["exit_code"], 137)
		self.assertEqual(pending[BENCH]["action"], "die")

	def test_an_oom_then_a_die_is_one_incident(self):
		pending, _stats = _drain(event("oom"), event("die", exit_code=137))
		self.assertEqual(len(pending), 1)
		self.assertEqual(pending[BENCH]["kind"], "oom_killed")
		self.assertEqual(pending[BENCH]["exit_code"], 137)

	def test_a_die_then_an_oom_is_the_same_one_incident(self):
		pending, _stats = _drain(event("die", exit_code=137), event("oom"))
		self.assertEqual(len(pending), 1)
		self.assertEqual(pending[BENCH]["kind"], "oom_killed")
		# The exit code survives the kind being overwritten; an oom event carries none.
		self.assertEqual(pending[BENCH]["exit_code"], 137)

	def test_an_action_with_a_state_nobody_named_still_matches_the_action(self):
		pending, _stats = _drain({**event("die"), "Action": "die: whatever"})
		self.assertEqual(pending[BENCH]["kind"], "bench_died")

	def test_a_health_verdict_is_matched_on_its_state(self):
		"""Docker's action carries the state after a colon and a space, and it is the whole point."""
		pending, _stats = _drain(event("health_status: unhealthy"))
		self.assertEqual(pending[BENCH]["kind"], "bench_unhealthy")
		self.assertEqual(pending[BENCH]["severity"], "error")
		self.assertEqual(pending[BENCH]["action"], "health_status: unhealthy")

	def test_a_recovery_is_the_other_verdict_and_is_not_an_error(self):
		pending, _stats = _drain(event("health_status: healthy"))
		self.assertEqual(pending[BENCH]["kind"], "bench_healthy")
		self.assertEqual(pending[BENCH]["severity"], "info")

	def test_a_bare_health_status_names_no_verdict_and_is_dropped(self):
		pending, _stats = _drain(event("health_status"))
		self.assertEqual(pending, {})

	def test_a_death_outranks_a_verdict_it_arrives_with(self):
		"""A site that stopped answering on its way out is one incident, and it is the death."""
		for events in (
			(event("health_status: unhealthy"), event("die", exit_code=137)),
			(event("die", exit_code=137), event("health_status: unhealthy")),
		):
			pending, _stats = _drain(*events)
			self.assertEqual(len(pending), 1)
			self.assertEqual(pending[BENCH]["kind"], "bench_died")

	def test_a_flap_inside_the_window_is_reported_as_the_failure(self):
		pending, _stats = _drain(event("health_status: unhealthy"), event("health_status: healthy"))
		self.assertEqual(pending[BENCH]["kind"], "bench_unhealthy")

	def test_two_benches_are_two_incidents(self):
		pending, _stats = _drain(event("die", bench="a"), event("die", bench="b"))
		self.assertEqual(sorted(pending), ["a", "b"])

	def test_the_settle_window_is_read_once_per_incident(self):
		with patch("benchpress.docker_events.settle_seconds", return_value=SETTLE) as settle:
			pending: dict = {}
			stats = {"events_seen": 0, "orphans": 0, "connected_since": 0}
			docker_events._drain(_inbox(event("oom"), event("die")), pending, stats)
		self.assertEqual(settle.call_count, 1)


class TestFlush(unittest.TestCase):
	def _flush(self, status, health="Healthy", settled=True):
		"""Flush one parked incident against a bench row reading `status` and `health`."""
		due = 0 if settled else float("inf")
		pending = {BENCH: {"due": due, "kind": "bench_died", "severity": "error", "exit_code": 137}}
		stats = {"events_seen": 1, "orphans": 0, "connected_since": 0}
		row = None if status is None else frappe._dict(status=status, container_health=health)
		with (
			patch("benchpress.docker_events.frappe") as frappe_mock,
			patch("benchpress.docker_events.record") as record_mock,
		):
			frappe_mock.db.get_value.return_value = row
			docker_events._flush(pending, stats)
		return record_mock, stats, pending

	def test_a_running_bench_is_recorded_once(self):
		record_mock, _stats, pending = self._flush("Running")
		record_mock.assert_called_once()
		self.assertEqual(record_mock.call_args.args[0], BENCH)
		self.assertEqual(pending, {})

	def test_a_bench_stopped_on_request_writes_nothing(self):
		"""The negative control: a stop keeps the health it had while it was serving."""
		record_mock, _stats, _pending = self._flush("Stopped", health="Healthy")
		record_mock.assert_not_called()

	def test_a_bench_never_polled_and_then_stopped_writes_nothing(self):
		record_mock, _stats, _pending = self._flush("Stopped", health="")
		record_mock.assert_not_called()

	def test_a_bench_the_poll_stopped_because_it_died_is_recorded(self):
		"""`_stop_if_dead` can beat the settle window, and it stamps what it found first."""
		for health in ("Unhealthy", "Unknown"):
			record_mock, _stats, _pending = self._flush("Stopped", health=health)
			record_mock.assert_called_once()

	def test_a_deploying_bench_writes_nothing(self):
		record_mock, _stats, _pending = self._flush("Deploying")
		record_mock.assert_not_called()

	def test_a_bench_with_no_row_is_counted_and_dropped(self):
		record_mock, stats, pending = self._flush(None)
		record_mock.assert_not_called()
		self.assertEqual(stats["orphans"], 1)
		self.assertEqual(pending, {})

	def test_an_incident_still_settling_is_left_alone(self):
		record_mock, _stats, pending = self._flush("Running", settled=False)
		record_mock.assert_not_called()
		self.assertEqual(list(pending), [BENCH])


class TestHealthVerdicts(unittest.TestCase):
	def _flush(self, kind, status="Running", last_event=None):
		"""Flush one parked health verdict and report what it recorded and what it wrote."""
		pending = {BENCH: {"due": 0, "kind": kind, "severity": "error", "exit_code": 0}}
		stats = {"events_seen": 1, "orphans": 0, "connected_since": 0}
		with (
			patch("benchpress.docker_events.frappe") as frappe_mock,
			patch("benchpress.docker_events.record") as record_mock,
			patch("benchpress.docker_events._last_event", return_value=last_event),
			patch("benchpress.docker_events.now_datetime", return_value="2026-08-27 12:00:00"),
		):
			frappe_mock.db.get_value.return_value = frappe._dict(status=status, container_health="Healthy")
			docker_events._flush(pending, stats)
		return record_mock, frappe_mock.db.set_value

	def test_a_failure_freshens_the_field_and_is_recorded(self):
		record_mock, set_value = self._flush("bench_unhealthy")
		record_mock.assert_called_once()
		self.assertEqual(set_value.call_args.args[2]["container_health"], "Unhealthy")

	def test_a_recovery_after_a_recorded_failure_is_news(self):
		record_mock, set_value = self._flush("bench_healthy", last_event="bench_unhealthy")
		record_mock.assert_called_once()
		self.assertEqual(set_value.call_args.args[2]["container_health"], "Healthy")

	def test_a_recovery_with_no_failure_behind_it_writes_the_field_and_no_row(self):
		"""Every deploy's first verdict is `starting -> healthy`, which is noise and not news."""
		record_mock, set_value = self._flush("bench_healthy", last_event=None)
		record_mock.assert_not_called()
		self.assertEqual(set_value.call_args.args[2]["container_health"], "Healthy")

	def test_a_recovery_after_a_death_is_not_a_recovery_from_anything_said(self):
		record_mock, _set_value = self._flush("bench_healthy", last_event="bench_died")
		record_mock.assert_not_called()

	def test_a_verdict_about_a_bench_the_platform_stopped_writes_nothing(self):
		record_mock, set_value = self._flush("bench_unhealthy", status="Stopped")
		record_mock.assert_not_called()
		set_value.assert_not_called()

	def test_a_verdict_mid_deploy_writes_nothing(self):
		record_mock, set_value = self._flush("bench_unhealthy", status="Deploying")
		record_mock.assert_not_called()
		set_value.assert_not_called()


class TestRecord(unittest.TestCase):
	def _record(self, kind="bench_died", owner="tenant@example.com"):
		incident = {
			"kind": kind,
			"severity": "error",
			"action": "die",
			"at": 1787722107,
			"exit_code": 137,
			"detail": "container c0ffee123456 image benchpress/lab:v16",
		}
		with (
			patch("benchpress.docker_events.frappe") as frappe_mock,
			patch("benchpress.docker_events.notifications") as notify_mock,
			patch("benchpress.docker_events._stamp", return_value="2026-08-27 12:00:00"),
			patch("benchpress.docker_events._", lambda text: text),
		):
			frappe_mock.db.get_value.return_value = owner
			docker_events.record(BENCH, incident)
			doc = frappe_mock.get_doc.call_args.args[0]
		return doc, frappe_mock.get_doc.return_value.insert, notify_mock.notify_owner

	def test_the_row_carries_the_incident(self):
		doc, insert, _notify = self._record()
		self.assertEqual(doc["doctype"], "Bench Event")
		self.assertEqual(doc["bench"], BENCH)
		self.assertEqual(doc["event_type"], "bench_died")
		self.assertEqual(doc["exit_code"], 137)
		self.assertEqual(doc["docker_action"], "die")
		insert.assert_called_once_with(ignore_permissions=True)

	def test_every_incident_can_be_ranked_and_has_something_to_say_to_the_owner(self):
		"""An unranked kind raises inside the drain, and a subject-less one inside the record."""
		kinds = {kind for kind, _severity in docker_events.INCIDENTS.values()}
		self.assertEqual(kinds, set(docker_events.SUBJECTS))
		self.assertEqual(kinds, set(docker_events.PRECEDENCE))

	def test_the_owner_is_told(self):
		_doc, _insert, notify = self._record()
		notify.assert_called_once()
		self.assertEqual(notify.call_args.args[0], "tenant@example.com")
		self.assertIn(BENCH, notify.call_args.args[1])

	def test_an_ownerless_bench_is_still_recorded(self):
		_doc, insert, notify = self._record(owner=None)
		insert.assert_called_once()
		notify.assert_not_called()


class TestHeartbeat(unittest.TestCase):
	def test_the_reader_gets_the_age_the_writer_could_not_know(self):
		with (
			patch("benchpress.docker_events.frappe") as frappe_mock,
			patch("benchpress.docker_events.time") as time_mock,
		):
			time_mock.time.return_value = 1000.0
			frappe_mock.cache.return_value.get_value.return_value = {"ts": 940, "events_seen": 3}
			self.assertEqual(docker_events.heartbeat_value(), {"ts": 940, "events_seen": 3, "age": 60})

	def test_nothing_published_is_none_and_not_a_stale_zero(self):
		with patch("benchpress.docker_events.frappe") as frappe_mock:
			frappe_mock.cache.return_value.get_value.return_value = None
			self.assertIsNone(docker_events.heartbeat_value())
