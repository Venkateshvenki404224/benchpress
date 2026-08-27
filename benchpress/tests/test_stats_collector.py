# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The stats poll must stop a Running bench whose container died — `status` drives billing."""

import unittest
from unittest.mock import patch

import frappe

from benchpress import stats_collector

BENCH = {"name": "bench-001", "container_id": "c0ffee", "owner": "user@example.com"}


class TestStopIfDead(unittest.TestCase):
	def _run(self, health, down=False):
		"""Run one poll over a single Running bench and report what it did."""
		with (
			patch("benchpress.stats_collector.frappe") as frappe_mock,
			patch("benchpress.stats_collector.get_container_stats", side_effect=Exception("no stats")),
			patch("benchpress.stats_collector.get_container_health", return_value=health),
			patch("benchpress.stats_collector.container_is_down", return_value=down) as down_mock,
			patch("benchpress.lifecycle.stopped") as stop_mock,
			patch("benchpress.notifications.notify_owner") as notify_mock,
		):
			frappe_mock.get_all.return_value = [dict(BENCH)]
			frappe_mock._ = lambda s: s

			from benchpress.stats_collector import collect_bench_stats

			collect_bench_stats()
		return stop_mock, notify_mock, down_mock

	def test_healthy_bench_is_left_alone(self):
		stop_mock, notify_mock, _ = self._run("Healthy")
		stop_mock.assert_not_called()
		notify_mock.assert_not_called()

	def test_a_container_that_stopped_stops_the_bench_and_tells_the_owner(self):
		stop_mock, notify_mock, _ = self._run("Unhealthy", down=True)
		stop_mock.assert_called_once_with(BENCH["name"])
		notify_mock.assert_called_once()
		self.assertEqual(notify_mock.call_args.args[0], BENCH["owner"])

	def test_a_dead_site_in_a_running_container_is_never_stopped(self):
		"""Unhealthy now also means the site went quiet, which is a bench to route around."""
		stop_mock, notify_mock, down_mock = self._run("Unhealthy", down=False)
		down_mock.assert_called_once_with(BENCH["container_id"])
		stop_mock.assert_not_called()
		notify_mock.assert_not_called()

	def test_vanished_container_stops_the_bench(self):
		stop_mock, _notify, _ = self._run("Unknown", down=True)
		stop_mock.assert_called_once_with(BENCH["name"])

	def test_inspect_error_never_stops_a_bench(self):
		# Unknown can mean a socket hiccup, not a missing container.
		stop_mock, notify_mock, down_mock = self._run("Unknown", down=False)
		down_mock.assert_called_once_with(BENCH["container_id"])
		stop_mock.assert_not_called()
		notify_mock.assert_not_called()

	def test_reconciliation_failure_does_not_kill_the_poll(self):
		second = {"name": "bench-002", "container_id": "dec0de", "owner": "user@example.com"}
		with (
			patch("benchpress.stats_collector.frappe") as frappe_mock,
			patch("benchpress.stats_collector.get_container_stats", side_effect=Exception("no stats")),
			patch("benchpress.stats_collector.get_container_health", return_value="Unhealthy"),
			patch("benchpress.stats_collector.container_is_down", return_value=True),
			patch("benchpress.lifecycle.stopped", side_effect=[Exception("boom"), None]) as stop_mock,
			patch("benchpress.notifications.notify_owner"),
		):
			frappe_mock.get_all.return_value = [dict(BENCH), second]
			frappe_mock._ = lambda s: s

			from benchpress.stats_collector import collect_bench_stats

			collect_bench_stats()

		self.assertEqual(stop_mock.call_count, 2)


class TestPollBound(unittest.TestCase):
	"""At 1.7 s a bench an unbounded pass cannot finish inside the `*/1` cron that starts it."""

	def _get_all_kwargs(self, limit):
		with (
			patch("benchpress.stats_collector.frappe") as frappe_mock,
			patch("benchpress.stats_collector._poll_max_benches", return_value=limit),
		):
			frappe_mock.get_all.return_value = []
			stats_collector._benches_to_poll()
			return frappe_mock.get_all.call_args.kwargs

	def test_the_stalest_benches_go_first_so_a_bounded_pass_still_reaches_them_all(self):
		kwargs = self._get_all_kwargs(50)
		self.assertEqual(kwargs["order_by"], "last_health_check asc")
		self.assertEqual(kwargs["limit_page_length"], 50)

	def test_zero_removes_the_bound(self):
		self.assertEqual(self._get_all_kwargs(0)["limit_page_length"], 0)

	def _limit(self, **settings):
		with patch("benchpress.stats_collector.frappe") as frappe_mock:
			frappe_mock.get_cached_doc.return_value = frappe._dict(settings)
			return stats_collector._poll_max_benches()

	def test_an_install_that_never_saved_its_settings_gets_the_default(self):
		self.assertEqual(self._limit(), stats_collector.DEFAULT_POLL_MAX_BENCHES)

	def test_a_configured_zero_is_kept_rather_than_defaulted_away(self):
		self.assertEqual(self._limit(stats_poll_max_benches=0), 0)

	def test_a_configured_bound_is_used(self):
		self.assertEqual(self._limit(stats_poll_max_benches=5), 5)
