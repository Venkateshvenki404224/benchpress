# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""run_diagnostics contract: six rows, fixed order, never raises, never mutates."""

import unittest
from unittest.mock import MagicMock, patch

import docker
import frappe

from benchpress.diagnostics import run_diagnostics

CHECK_ORDER = ["docker_socket", "docker_network", "mariadb", "redis", "container_runtimes", "vpn_server"]
HOST_RUNTIMES = {"names": {"runc", "sysbox-runc"}, "default": "runc"}
DB_ROW = frappe._dict(name="db-server-1", status="Running", container_name="benchpress-mariadb")


def _healthy_client():
	client = MagicMock()
	client.containers.get.return_value = MagicMock(status="running")
	return client


class TestDiagnostics(unittest.TestCase):
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
	):
		"""Run run_diagnostics with everything healthy unless overridden.

		Returns ({check: row}, ordered rows)."""
		client = client or _healthy_client()
		with (
			patch("benchpress.diagnostics.get_client", side_effect=client_error, return_value=client),
			# A separate patch, because the runtime check reads `docker info` through
			# its own memoised helper rather than through this client.
			patch(
				"benchpress.diagnostics.host_runtimes",
				side_effect=client_error,
				return_value=HOST_RUNTIMES if runtimes is None else runtimes,
			),
			patch("benchpress.diagnostics.check_mariadb_health", return_value=mariadb_healthy),
			patch("benchpress.diagnostics.frappe") as frappe_mock,
		):
			frappe_mock.get_all.return_value = [DB_ROW] if db_rows is None else db_rows
			frappe_mock.get_installed_apps.return_value = installed_apps or [
				"frappe",
				"benchpress",
				"vpn_management",
			]
			frappe_mock.db.exists.return_value = wg_exists
			frappe_mock.db.get_value.return_value = wg_key
			rows = run_diagnostics()
		return {row["check"]: row for row in rows}, rows

	def test_all_checks_pass(self):
		_by_check, rows = self._run()
		self.assertEqual([row["check"] for row in rows], CHECK_ORDER)
		for row in rows:
			self.assertEqual(row["status"], "pass")
			self.assertEqual(set(row), {"check", "status", "hint"})

	def test_docker_down_marks_docker_checks_failed_without_raising(self):
		# completing without an exception IS the core assertion
		by_check, rows = self._run(client_error=Exception("socket unreachable"))
		self.assertEqual(len(rows), 6)
		for check in ("docker_socket", "docker_network", "redis"):
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
		_by_check, rows = self._run(
			client=client,
			runtimes={"names": set(), "default": "runc"},
			mariadb_healthy=False,
			db_rows=[],
			installed_apps=["frappe"],
		)
		self.assertEqual([row["status"] for row in rows], ["fail"] * 6)
		client.networks.create.assert_not_called()
		client.containers.create.assert_not_called()
		client.containers.run.assert_not_called()
