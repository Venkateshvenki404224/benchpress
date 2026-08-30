# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""run_diagnostics contract: twelve rows, fixed order, never raises, never mutates."""

import inspect
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import docker
import frappe

from benchpress import ingress
from benchpress.diagnostics import (
	ROUTE_STATE_UNREPORTED,
	_check_route_directory,
	check_row,
	display_row,
	run_diagnostics,
)
from benchpress.docker_events import HEARTBEAT_STALE_SECONDS
from benchpress.image_cache import clear_cached_tags

CHECK_ORDER = [
	"docker_socket",
	"docker_network",
	"bridge_capacity",
	"kernel_ceilings",
	"mariadb",
	"clock_skew",
	"redis",
	"container_runtimes",
	"golden_images",
	"docker_events",
	"route_directory",
	"vpn_server",
]
COUNT_WORDS = {6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
HOST_RUNTIMES = {"names": {"runc", "sysbox-runc"}, "default": "runc"}
# Small enough that a full bridge leaves the family with no headroom, which is the only
# way `bridge_capacity` reports a fail.
BRIDGE_COUNT = 2
BRIDGE_SLOTS = 1000
# What a tuned host reads back for the three ceilings a container can see.
HEALTHY_CEILINGS = {
	"kernel.pty.max": BRIDGE_SLOTS * 8 + 1024,
	"kernel.pid_max": 4194304,
	"net.netfilter.nf_conntrack_max": 1048576,
}
DB_ROW = frappe._dict(name="db-server-1", status="Running", container_name="benchpress-mariadb")
# (no drifted setting, buffer-pool hit rate) — what `mariadb_drift` answers on a healthy pair.
NO_DRIFT = ([], "99.94%")

# What this host really answers: MariaDB is UTC, Python is Asia/Calcutta.
DB_CLOCK = datetime(2026, 8, 24, 23, 11, 53)
IST_OFFSET = timedelta(hours=5, minutes=30)

FRESH_HEARTBEAT = {"age": 2, "events_seen": 41, "orphans": 0, "pending": 0}

# What a rendered, mounted route directory holds before any bench deploys. Named from `ingress`
# rather than spelled out, so a rename there fails here rather than passing against a stale name.
PROTECTED_FILES = (ingress.CONTROL_PLANE_ROUTE_FILE, ingress.WILDCARD_ANCHOR_FILE)
BASE_DOMAIN = "benchpress.cloud"
# Its own key, so a test run on a live host never clobbers the report its dashboard is reading.
TEST_ROUTE_STATE_KEY = "benchpress:route_directory:test_diagnostics"


def _lab_image(tag, golden=True):
	return MagicMock(tags=[tag], labels={"benchpress.golden": "1"} if golden else {})


def _healthy_client(bridge_endpoints=4):
	client = MagicMock()
	client.containers.get.return_value = MagicMock(status="running")
	client.images.list.return_value = [_lab_image("benchpress/crm:lab")]
	network = MagicMock()
	network.attrs = {"Containers": {f"c{i}": {"Name": f"c{i}"} for i in range(bridge_endpoints)}}
	client.networks.get.return_value = network
	return client


class TestDiagnostics(unittest.TestCase):
	def setUp(self):
		"""The route-directory report is a cache key, so every test starts with none of its own."""
		frappe.cache().delete_value(TEST_ROUTE_STATE_KEY)
		self.addCleanup(frappe.cache().delete_value, TEST_ROUTE_STATE_KEY)

	def _run(
		self,
		client=None,
		client_error=None,
		runtimes=None,
		mariadb_healthy=True,
		db_rows=None,
		installed_apps=None,
		wg_exists=True,
		wg_key="the-key",
		app_clock=None,
		db_clock=None,
		db_clock_error=None,
		ceilings=None,
		mariadb_drift=None,
		redis_drift=None,
		heartbeat=FRESH_HEARTBEAT,
		heartbeat_error=None,
		base_domain=BASE_DOMAIN,
		route_dir_mounted=True,
		route_files=PROTECTED_FILES,
		published_routes=(),
		route_state_reported=True,
	):
		"""Run run_diagnostics with everything healthy unless overridden.

		Returns ({check: row}, ordered rows)."""
		client = client or _healthy_client()
		ceilings = HEALTHY_CEILINGS if ceilings is None else ceilings
		with (
			# A real directory recorded through the real recorder, rather than a patched
			# `directory_state`: what is on disk is the subject, and the empty-directory case
			# this row exists to catch is invisible to a mocked answer.
			tempfile.TemporaryDirectory() as tmp,
			patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", Path(tmp) / "dynamic"),
			patch.object(ingress, "ROUTE_STATE_KEY", TEST_ROUTE_STATE_KEY),
			patch("benchpress.diagnostics.get_client", side_effect=client_error, return_value=client),
			# A separate patch, because the runtime check reads `docker info` through
			# its own memoised helper rather than through this client.
			patch(
				"benchpress.diagnostics.host_runtimes",
				side_effect=client_error,
				return_value=HOST_RUNTIMES if runtimes is None else runtimes,
			),
			patch("benchpress.diagnostics.check_mariadb_health", return_value=mariadb_healthy),
			patch("benchpress.diagnostics.mariadb_drift", return_value=mariadb_drift or NO_DRIFT),
			patch("benchpress.diagnostics.redis_drift", return_value=redis_drift or []),
			# The capacity check reaches the daemon through docker_manager's own client rather
			# than the one above, so the same client is injected there — and left unmocked
			# beyond that, so `networks.create.assert_not_called()` really covers it.
			patch("benchpress.docker_manager.get_client", side_effect=client_error, return_value=client),
			patch("benchpress.placement.bridge_count", return_value=BRIDGE_COUNT),
			patch("benchpress.placement.slots_per_bridge", return_value=BRIDGE_SLOTS),
			patch("benchpress.diagnostics._read_sysctl", side_effect=ceilings.get),
			patch(
				"benchpress.diagnostics.heartbeat_value",
				side_effect=heartbeat_error,
				return_value=heartbeat,
			),
			patch("benchpress.diagnostics.frappe") as frappe_mock,
		):
			if route_dir_mounted:
				ingress.TRAEFIK_DYNAMIC_DIR.mkdir()
				for name in (*route_files, *(f"{route}.yml" for route in published_routes)):
					(ingress.TRAEFIK_DYNAMIC_DIR / name).write_text("")
			if route_state_reported:
				# What queue-long does on every deploy and every reconcile pass.
				ingress.record_directory_state()
			frappe_mock.get_cached_doc.return_value = frappe._dict(base_domain=base_domain)
			frappe_mock.get_all.return_value = [DB_ROW] if db_rows is None else db_rows
			frappe_mock.get_installed_apps.return_value = installed_apps or [
				"frappe",
				"benchpress",
				"vpn_management",
			]
			frappe_mock.db.exists.return_value = wg_exists
			frappe_mock.db.get_value.return_value = wg_key
			frappe_mock.utils.now_datetime.return_value = app_clock or DB_CLOCK
			frappe_mock.qb.select.side_effect = db_clock_error
			frappe_mock.qb.select.return_value.run.return_value = ((db_clock or DB_CLOCK,),)
			# The golden row reads the memoised image list, which outlives one `_run`.
			clear_cached_tags()
			rows = run_diagnostics()
		return {row["check"]: row for row in rows}, rows

	def test_all_checks_pass(self):
		_by_check, rows = self._run()
		self.assertEqual([row["check"] for row in rows], CHECK_ORDER)
		for row in rows:
			self.assertEqual(row["status"], "pass")
			self.assertEqual(set(row), {"check", "status", "hint", "severity"})

	def test_docker_down_marks_docker_checks_failed_without_raising(self):
		# completing without an exception IS the core assertion
		by_check, rows = self._run(client_error=Exception("socket unreachable"))
		self.assertEqual(len(rows), len(CHECK_ORDER))
		for check in ("docker_socket", "docker_network", "bridge_capacity", "redis"):
			self.assertEqual(by_check[check]["status"], "fail")

	def test_missing_network_fails_with_hint(self):
		client = _healthy_client()
		client.networks.get.side_effect = docker.errors.NotFound("no network")
		by_check, _rows = self._run(client=client)
		self.assertEqual(by_check["docker_network"]["status"], "fail")
		self.assertIn("created automatically on first deploy", by_check["docker_network"]["hint"])

	def test_mariadb_unhealthy_and_missing_server(self):
		by_check, _rows = self._run(mariadb_healthy=False)
		self.assertEqual(by_check["mariadb"]["status"], "fail")

		by_check, _rows = self._run(db_rows=[])
		self.assertEqual(by_check["mariadb"]["status"], "fail")
		self.assertIn("No Database Server record", by_check["mariadb"]["hint"])

	def test_redis_not_running_fails(self):
		client = _healthy_client()
		client.containers.get.return_value = MagicMock(status="exited")
		by_check, _rows = self._run(client=client)
		self.assertEqual(by_check["redis"]["status"], "fail")
		self.assertIn("exited", by_check["redis"]["hint"])

		client = _healthy_client()
		client.containers.get.side_effect = docker.errors.NotFound("gone")
		by_check, _rows = self._run(client=client)
		self.assertEqual(by_check["redis"]["status"], "fail")

	def test_unregistered_runtime_fails_and_names_it(self):
		"""The cheap check: registered or not. Whether it works takes preflight_runtime."""
		by_check, _rows = self._run(runtimes={"names": {"runc"}, "default": "runc"})
		self.assertEqual(by_check["container_runtimes"]["status"], "fail")
		self.assertIn("sysbox-runc", by_check["container_runtimes"]["hint"])

	def test_vpn_missing_app_fails(self):
		by_check, _rows = self._run(installed_apps=["frappe", "benchpress"])
		self.assertEqual(by_check["vpn_server"]["status"], "fail")
		self.assertIn("vpn_management", by_check["vpn_server"]["hint"])

	def test_never_calls_mutating_docker_apis(self):
		client = _healthy_client()
		client.ping.side_effect = Exception("down")
		client.networks.get.side_effect = docker.errors.NotFound("no network")
		client.containers.get.side_effect = docker.errors.NotFound("gone")
		client.images.list.side_effect = Exception("down")
		_by_check, rows = self._run(
			client=client,
			runtimes={"names": set(), "default": "runc"},
			mariadb_healthy=False,
			db_rows=[],
			installed_apps=["frappe"],
			db_clock_error=Exception("down"),
			ceilings={},
			heartbeat=None,
			route_dir_mounted=False,
		)
		# Capacity is the one exception: a family with no bridge yet is the lazy-creation
		# invariant, not a broken environment.
		self.assertEqual(
			[row["status"] for row in rows if row["check"] != "bridge_capacity"],
			["fail"] * (len(CHECK_ORDER) - 1),
		)
		client.networks.create.assert_not_called()
		client.containers.create.assert_not_called()
		client.containers.run.assert_not_called()

	def test_clock_skew_passes_when_the_clocks_agree(self):
		by_check, _rows = self._run(app_clock=DB_CLOCK + timedelta(seconds=1))
		self.assertEqual(by_check["clock_skew"]["status"], "pass")

	def test_clock_skew_fails_beyond_the_tolerance(self):
		"""The live condition on this host, and what silently buys 5h30m of free compute."""
		app_clock = DB_CLOCK + IST_OFFSET
		by_check, _rows = self._run(app_clock=app_clock)

		hint = by_check["clock_skew"]["hint"]
		self.assertEqual(by_check["clock_skew"]["status"], "fail")
		self.assertIn("19800", hint)
		self.assertIn(app_clock.strftime("%Y-%m-%d %H:%M:%S"), hint)
		self.assertIn(DB_CLOCK.strftime("%Y-%m-%d %H:%M:%S"), hint)

	def test_clock_skew_never_raises(self):
		"""A database that refuses the query is a fail row, not an exception."""
		by_check, rows = self._run(db_clock_error=Exception("db refuses the query"))
		self.assertEqual(len(rows), len(CHECK_ORDER))
		self.assertEqual(by_check["clock_skew"]["status"], "fail")
		self.assertIn("db refuses the query", by_check["clock_skew"]["hint"])

	def test_a_family_with_no_room_left_is_a_fail_row(self):
		by_check, _rows = self._run(client=_healthy_client(bridge_endpoints=BRIDGE_SLOTS))
		self.assertEqual(by_check["bridge_capacity"]["status"], "fail")
		self.assertIn(f"{BRIDGE_SLOTS} used / 0 free", by_check["bridge_capacity"]["hint"])

	def test_a_family_with_no_bridge_yet_is_not_a_failure(self):
		"""Bridges are lazy, so an install that has never deployed reports room, not a problem."""
		client = _healthy_client()
		client.networks.get.side_effect = docker.errors.NotFound("no network")
		by_check, _rows = self._run(client=client)
		self.assertEqual(by_check["bridge_capacity"]["status"], "pass")

	def test_kernel_ceilings_names_the_low_knob_and_what_raises_it(self):
		by_check, _rows = self._run(ceilings={**HEALTHY_CEILINGS, "kernel.pty.max": 4096})
		hint = by_check["kernel_ceilings"]["hint"]
		self.assertEqual(by_check["kernel_ceilings"]["status"], "fail")
		self.assertIn("kernel.pty.max is 4096, below 9024", hint)
		self.assertIn("tune-host.sh", hint)

	def test_kernel_ceilings_says_the_neighbour_table_is_not_visible_from_here(self):
		"""A row that quietly omitted it would read as checked and fine."""
		by_check, _rows = self._run()
		self.assertEqual(by_check["kernel_ceilings"]["status"], "pass")
		self.assertIn("neighbour table is not visible", by_check["kernel_ceilings"]["hint"])

	def test_a_knob_this_namespace_cannot_read_is_a_fail_not_a_pass(self):
		by_check, _rows = self._run(ceilings={})
		self.assertEqual(by_check["kernel_ceilings"]["status"], "fail")
		self.assertIn("unreadable", by_check["kernel_ceilings"]["hint"])

	def test_a_lab_with_no_golden_is_named_and_is_never_an_error(self):
		client = _healthy_client()
		client.images.list.return_value = [
			_lab_image("benchpress/crm:lab"),
			_lab_image("benchpress/erpnext:lab", golden=False),
		]

		by_check, _rows = self._run(client=client)

		row = by_check["golden_images"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertIn("1 of 2 built labs carry a golden dump", row["hint"])
		self.assertIn("benchpress/erpnext:lab", row["hint"])

	def test_a_warning_row_reaches_the_screen_as_a_warning(self):
		row = check_row("golden_images", False, "1 of 2", severity="Warning")

		self.assertEqual(display_row(row, "Golden images")["status"], "Warning")

	def test_a_failed_check_with_no_severity_still_reads_as_an_error(self):
		self.assertEqual(
			display_row({"check": "redis", "status": "fail", "hint": ""}, "Redis")["status"], "Error"
		)

	def test_a_fresh_heartbeat_passes_and_reports_what_the_listener_has_seen(self):
		by_check, _rows = self._run()
		row = by_check["docker_events"]
		self.assertEqual(row["status"], "pass")
		self.assertIn("2s ago", row["hint"])
		self.assertIn("41 events seen", row["hint"])

	def test_a_stale_heartbeat_fails_and_names_the_service_to_start(self):
		"""The row this phase exists for: a listener that dies otherwise looks like a quiet fleet."""
		stale = {**FRESH_HEARTBEAT, "age": HEARTBEAT_STALE_SECONDS + 1}
		by_check, _rows = self._run(heartbeat=stale)

		row = by_check["docker_events"]
		self.assertEqual(row["status"], "fail")
		self.assertIn(f"{HEARTBEAT_STALE_SECONDS + 1}s ago", row["hint"])
		self.assertIn("docker compose up -d docker-events", row["hint"])

	def test_a_heartbeat_exactly_at_the_threshold_is_still_believed(self):
		by_check, _rows = self._run(heartbeat={**FRESH_HEARTBEAT, "age": HEARTBEAT_STALE_SECONDS})
		self.assertEqual(by_check["docker_events"]["status"], "pass")

	def test_no_heartbeat_at_all_fails_and_names_the_service_to_start(self):
		by_check, _rows = self._run(heartbeat=None)

		row = by_check["docker_events"]
		self.assertEqual(row["status"], "fail")
		self.assertIn("no heartbeat", row["hint"])
		self.assertIn("docker compose up -d docker-events", row["hint"])

	def test_an_unreachable_cache_is_a_fail_row_not_an_exception(self):
		by_check, rows = self._run(heartbeat_error=Exception("redis is gone"))

		self.assertEqual(len(rows), len(CHECK_ORDER))
		self.assertEqual(by_check["docker_events"]["status"], "fail")
		self.assertIn("redis is gone", by_check["docker_events"]["hint"])

	def test_the_diagnostics_row_count_moved_in_both_places(self):
		"""One count, stated twice: the test_api fixture and the overview docstring."""
		from benchpress.overview import _infrastructure
		from benchpress.tests.test_api import DIAGNOSTICS_ROWS

		self.assertEqual([row["check"] for row in DIAGNOSTICS_ROWS], CHECK_ORDER)
		self.assertIn(COUNT_WORDS[len(CHECK_ORDER)], inspect.getdoc(_infrastructure))

	def test_the_mariadb_row_always_reports_the_buffer_pool_hit_rate(self):
		"""The 128M pool rests on one measurement, so the number stays in front of the operator."""
		by_check, _rows = self._run()

		self.assertEqual(by_check["mariadb"]["status"], "pass")
		self.assertIn("99.94%", by_check["mariadb"]["hint"])

	def test_a_drifted_mariadb_is_a_warning_that_names_the_setting(self):
		by_check, _rows = self._run(mariadb_drift=(["max_connections is 151, declared 500"], "88.00%"))

		row = by_check["mariadb"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertIn("max_connections is 151, declared 500", row["hint"])
		self.assertIn("88.00%", row["hint"])
		self.assertIn("docker compose up -d", row["hint"])

	def test_a_missing_route_directory_fails_and_names_what_mounts_it(self):
		"""The stock install: Base Domain is required, so it is filled on a host with no mount."""
		by_check, _rows = self._run(route_dir_mounted=False)

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Error")
		self.assertIn("queue-long", row["hint"])
		self.assertIn("docker-compose.prod.yml", row["hint"])
		self.assertIn("./entry.py --domain", row["hint"])

	def test_the_row_reads_a_workers_report_never_this_containers_filesystem(self):
		"""`backend` serves this screen and mounts no route directory — only queue-long and
		traefik do — so a stat here would fail on a correctly configured host."""
		with tempfile.TemporaryDirectory() as tmp:
			route_dir = Path(tmp) / "dynamic"
			route_dir.mkdir()
			for name in PROTECTED_FILES:
				(route_dir / name).write_text("")
			with (
				patch.object(ingress, "ROUTE_STATE_KEY", TEST_ROUTE_STATE_KEY),
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", route_dir),
			):
				ingress.record_directory_state()

			# The reader's own view of the path: absent, exactly as in `backend`.
			with (
				patch.object(ingress, "ROUTE_STATE_KEY", TEST_ROUTE_STATE_KEY),
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", Path(tmp) / "not-here"),
				patch("benchpress.diagnostics.frappe") as frappe_mock,
			):
				frappe_mock.get_cached_doc.return_value = frappe._dict(base_domain=BASE_DOMAIN)
				row = _check_route_directory()

		self.assertEqual(row["status"], "pass")
		self.assertIn(f"*.{BASE_DOMAIN} anchored", row["hint"])

	def test_no_report_at_all_is_a_warning_that_names_what_writes_one(self):
		"""A public install nothing has reported on is unverified, not healthy."""
		by_check, _rows = self._run(route_state_reported=False)

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertEqual(row["hint"], ROUTE_STATE_UNREPORTED)

	def test_a_stale_report_is_named_by_its_age_and_not_believed(self):
		"""The reconcile pass refreshes it, so a report this old means the pass stopped running."""
		age = ingress.ROUTE_STATE_STALE_SECONDS + 60
		with patch.object(ingress, "ROUTE_STATE_KEY", TEST_ROUTE_STATE_KEY):
			frappe.cache().set_value(
				TEST_ROUTE_STATE_KEY,
				{"ts": int(time.time()) - age, "mounted": True, "missing": [], "published": 3},
			)
			with patch("benchpress.diagnostics.frappe") as frappe_mock:
				frappe_mock.get_cached_doc.return_value = frappe._dict(base_domain=BASE_DOMAIN)
				row = _check_route_directory()

		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertIn(f"{age}s ago", row["hint"])
		self.assertIn(str(ingress.ROUTE_STATE_STALE_SECONDS), row["hint"])

	def test_an_empty_route_directory_is_a_fail_not_a_mounted_pass(self):
		"""Docker turns a bind source that does not exist into an empty directory, which is how
		this bug hides from every check that only asks whether the path is there."""
		by_check, _rows = self._run(route_files=())

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "fail")
		self.assertIn(ingress.CONTROL_PLANE_ROUTE_FILE, row["hint"])
		self.assertIn("never rendered", row["hint"])

	def test_a_rendered_directory_passes_and_counts_what_is_published(self):
		by_check, _rows = self._run(published_routes=("inst-1", "inst-2"))

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "pass")
		self.assertIn("2 bench routes published", row["hint"])
		self.assertIn(f"*.{BASE_DOMAIN} anchored", row["hint"])

	def test_an_install_that_has_never_deployed_is_not_a_failure(self):
		"""The anchor is written by the first deploy, so its absence before one is normal."""
		by_check, _rows = self._run(route_files=(ingress.CONTROL_PLANE_ROUTE_FILE,))

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "pass")
		self.assertIn("no bench route published yet", row["hint"])

	def test_published_routes_with_no_anchor_are_a_warning_naming_the_certificate(self):
		by_check, _rows = self._run(
			route_files=(ingress.CONTROL_PLANE_ROUTE_FILE,), published_routes=("inst-1",)
		)

		row = by_check["route_directory"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertIn("fail TLS", row["hint"])

	def test_a_dev_checkout_advertising_no_public_url_passes(self):
		for base_domain in ("localhost", ""):
			with self.subTest(base_domain=base_domain):
				by_check, _rows = self._run(base_domain=base_domain, route_dir_mounted=False)

				self.assertEqual(by_check["route_directory"]["status"], "pass")
				self.assertIn("No public base domain", by_check["route_directory"]["hint"])

	def test_the_route_directory_check_writes_nothing(self):
		"""Every diagnostics check is read-only, and this one names a directory Traefik reads live
		and a report the workers own — it must leave both exactly as it found them."""
		with tempfile.TemporaryDirectory() as tmp:
			route_dir = Path(tmp) / "dynamic"
			route_dir.mkdir()
			for name in PROTECTED_FILES:
				(route_dir / name).write_text("")

			with (
				patch.object(ingress, "ROUTE_STATE_KEY", TEST_ROUTE_STATE_KEY),
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", route_dir),
			):
				ingress.record_directory_state()
				before = {path.name: path.stat().st_mtime_ns for path in route_dir.iterdir()}
				reported = frappe.cache().get_value(TEST_ROUTE_STATE_KEY)

				with patch("benchpress.diagnostics.frappe") as frappe_mock:
					frappe_mock.get_cached_doc.return_value = frappe._dict(base_domain=BASE_DOMAIN)
					self.assertEqual(_check_route_directory()["status"], "pass")

				self.assertEqual(frappe.cache().get_value(TEST_ROUTE_STATE_KEY), reported)

			self.assertEqual({path.name: path.stat().st_mtime_ns for path in route_dir.iterdir()}, before)

	def test_a_redis_on_the_declared_settings_passes(self):
		by_check, _rows = self._run()

		self.assertEqual(by_check["redis"]["status"], "pass")
		self.assertIn("declared settings", by_check["redis"]["hint"])

	def test_a_running_but_unbounded_redis_is_a_warning_naming_both_settings(self):
		"""Running was the whole old check, and a stock Redis passed it."""
		by_check, _rows = self._run(
			redis_drift=[
				"maxmemory is 0, declared 268435456",
				"maxmemory-policy is noeviction, declared allkeys-lru",
			]
		)

		row = by_check["redis"]
		self.assertEqual(row["status"], "fail")
		self.assertEqual(row["severity"], "Warning")
		self.assertIn("maxmemory is 0", row["hint"])
		self.assertIn("noeviction", row["hint"])
		self.assertIn("docker compose up -d", row["hint"])
