# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The stats poll must stop a Running bench whose container died — `status` drives billing."""

import unittest
from unittest.mock import patch

BENCH = {"name": "bench-001", "container_id": "c0ffee", "owner": "user@example.com"}


class TestStopIfDead(unittest.TestCase):
	def _run(self, health, gone=False):
		"""Run one poll over a single Running bench and report what it did."""
		with (
			patch("benchpress.stats_collector.frappe") as frappe_mock,
			patch("benchpress.stats_collector.get_container_stats", side_effect=Exception("no stats")),
			patch("benchpress.stats_collector.get_container_health", return_value=health),
			patch("benchpress.stats_collector.container_is_gone", return_value=gone) as gone_mock,
			patch("benchpress.lifecycle.stopped") as stop_mock,
			patch("benchpress.notifications.notify_owner") as notify_mock,
		):
			frappe_mock.get_all.return_value = [dict(BENCH)]
			frappe_mock._ = lambda s: s

			from benchpress.stats_collector import collect_bench_stats

			collect_bench_stats()
		return stop_mock, notify_mock, gone_mock

	def test_healthy_bench_is_left_alone(self):
		stop_mock, notify_mock, _ = self._run("Healthy")
		stop_mock.assert_not_called()
		notify_mock.assert_not_called()

	def test_unhealthy_container_stops_the_bench_and_tells_the_owner(self):
		stop_mock, notify_mock, _ = self._run("Unhealthy")
		stop_mock.assert_called_once_with(BENCH["name"])
		notify_mock.assert_called_once()
		self.assertEqual(notify_mock.call_args.args[0], BENCH["owner"])

	def test_vanished_container_stops_the_bench(self):
		stop_mock, _notify, _ = self._run("Unknown", gone=True)
		stop_mock.assert_called_once_with(BENCH["name"])

	def test_inspect_error_never_stops_a_bench(self):
		# Unknown can mean a socket hiccup, not a missing container.
		stop_mock, notify_mock, gone_mock = self._run("Unknown", gone=False)
		gone_mock.assert_called_once_with(BENCH["container_id"])
		stop_mock.assert_not_called()
		notify_mock.assert_not_called()

	def test_reconciliation_failure_does_not_kill_the_poll(self):
		second = {"name": "bench-002", "container_id": "dec0de", "owner": "user@example.com"}
		with (
			patch("benchpress.stats_collector.frappe") as frappe_mock,
			patch("benchpress.stats_collector.get_container_stats", side_effect=Exception("no stats")),
			patch("benchpress.stats_collector.get_container_health", return_value="Unhealthy"),
			patch("benchpress.lifecycle.stopped", side_effect=[Exception("boom"), None]) as stop_mock,
			patch("benchpress.notifications.notify_owner"),
		):
			frappe_mock.get_all.return_value = [dict(BENCH), second]
			frappe_mock._ = lambda s: s

			from benchpress.stats_collector import collect_bench_stats

			collect_bench_stats()

		self.assertEqual(stop_mock.call_count, 2)
