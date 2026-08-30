# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""One writer per bench transition, and the side effects that writer must not forget."""

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import api, ingress, lifecycle, vpn_adapter
from benchpress.credits import account, admission, lease
from benchpress.tests.fakes import FakeDockerMixin
from benchpress.tests.test_deploy_manager import (
	_delete_bench_sites,
	_fresh_bench,
	_make_bench_site,
	_make_lab,
	_mounted,
)
from benchpress.tests.test_device_wrappers import RECONCILE_HOOK, ensure_wg0_pool

BENCH = "Bench Instance"
SITE = "Bench Site"
ADMISSION = "Bench Admission"
ALLOCATION = "IP Allocation"
ERROR_LOG = "Error Log"
SETTINGS = "BenchPress Settings"
LIFECYCLE_MODULE = "lifecycle.py"


class TestOneWriterPerStatus(unittest.TestCase):
	def test_only_lifecycle_writes_running(self):
		"""Four call sites used to. A fifth appearing is the bug this whole item exists to stop."""
		self.assertEqual(_status_writers("Running"), {LIFECYCLE_MODULE})

	def test_only_lifecycle_writes_stopped(self):
		"""`Database Server` spells its own statuses the same, so it names them instead."""
		self.assertEqual(_status_writers("Stopped"), {LIFECYCLE_MODULE})


def _status_writers(status: str) -> set[str]:
	"""Every non-test module that assigns or `set_value`s `status` to `status`, by file name."""
	package = Path(lifecycle.__file__).resolve().parent
	writers = set()
	for path in sorted(package.rglob("*.py")):
		if path.parent.name == "tests" or path.name.startswith("test_"):
			continue
		tree = ast.parse(path.read_text())
		if any(_writes_status(node, status) for node in ast.walk(tree)):
			writers.add(str(path.relative_to(package)))
	return writers


def _writes_status(node: ast.AST, status: str) -> bool:
	if isinstance(node, ast.Assign):
		return _assigns_status(node, status)
	if isinstance(node, ast.Call):
		return _set_values_status(node, status)
	return False


def _assigns_status(node: ast.Assign, status: str) -> bool:
	"""`<anything>.status = "Running"`."""
	if not (isinstance(node.value, ast.Constant) and node.value.value == status):
		return False
	return any(isinstance(t, ast.Attribute) and t.attr == "status" for t in node.targets)


def _set_values_status(node: ast.Call, status: str) -> bool:
	"""`set_value(dt, name, "status", <status>)`, or the same as a dict.

	The doctype is not checked: it is a module constant as often as a literal.
	"""
	if getattr(node.func, "attr", None) != "set_value":
		return False
	args = node.args[2:] + [kw.value for kw in node.keywords]
	field, value = (*args, None, None)[:2]
	if _is(field, "status") and _is(value, status):
		return True
	return any(isinstance(arg, ast.Dict) and _dict_maps_status(arg, status) for arg in args)


def _is(node, value: str) -> bool:
	return isinstance(node, ast.Constant) and node.value == value


def _dict_maps_status(node: ast.Dict, status: str) -> bool:
	return any(
		_is(key, "status") and _is(value, status) for key, value in zip(node.keys, node.values, strict=True)
	)


class TransitionFixtures:
	"""A lab of its own per transition, and benches durable enough to outlive a commit."""

	lab_id = ""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab(cls.lab_id)
		frappe.db.commit()  # nosemgrep -- the fixtures outlive the per-test rollback

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all(BENCH, filters={"lab": cls.lab.name}, pluck="name"):
			frappe.db.delete("Deploy Log", {"bench": name})
			_delete_bench_sites(name)
			frappe.delete_doc(BENCH, name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the teardown must outlive the per-test rollback too
		super().tearDownClass()

	def _claimed_bench(self, bench):
		"""Give this bench a slot, so a release has something to give back."""
		account.ensure_account(bench.owner)
		admission.claim(bench.owner, bench.name, 0)
		self.addCleanup(self._drop_claim, bench.name)
		frappe.db.commit()  # nosemgrep -- the transition commits, so the claim it releases must be durable
		return bench

	def _drop_claim(self, bench_name: str) -> None:
		admission.release(bench_name)
		frappe.db.commit()  # nosemgrep -- a leaked slot would outlive the rollback and the test

	def _slots(self, owner: str) -> int:
		return frappe.utils.cint(frappe.db.get_value("Credit Account", owner, "active_instances"))

	def _forget_error_logs(self, bench_name: str) -> None:
		"""One bench name serves every test here, and `log_error` commits past the rollback."""
		frappe.db.delete(ERROR_LOG, {"method": ("like", f"%{bench_name}%")})
		frappe.db.commit()  # nosemgrep -- the row the assertion reads was committed too

	def _bench(self, status: str, container_status: str, *, container: bool = True):
		bench = _fresh_bench(self, self.lab.name)
		if container:
			bench.container_id = self.docker.add_container(bench.bench_name, status=container_status).id
		bench.status = status
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the transition under test commits, so its fixture has to be durable
		self.addCleanup(frappe.db.commit)
		return bench


class TestRunning(TransitionFixtures, FakeDockerMixin, IntegrationTestCase):
	"""The four side effects, driven through the transition itself."""

	lab_id = "test-lab-lifecycle-running"

	def _stopped_bench(self):
		return self._bench("Stopped", "exited")

	def test_a_start_stamps_started_at_and_writes_running(self):
		bench = self._stopped_bench()
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.running(bench)
		bench.reload()
		self.assertEqual(bench.status, "Running")
		self.assertIsNotNone(bench.started_at)

	def test_a_restart_keeps_the_started_at_it_already_had(self):
		bench = self._stopped_bench()
		stamped = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-2)
		frappe.db.set_value(BENCH, bench.name, "started_at", stamped)
		bench.reload()
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.running(bench, action="restart")
		bench.reload()
		self.assertEqual(bench.status, "Running")
		self.assertEqual(frappe.utils.get_datetime(bench.started_at), stamped)

	def test_the_route_sync_is_enqueued_after_the_status_is_committed(self):
		"""The job re-reads `status`, so a route synced before the commit routes a stopped bench."""
		bench = self._stopped_bench()
		seen = {}

		def record(bench_name):
			seen["status"] = frappe.db.get_value(BENCH, bench_name, "status")

		with patch.object(lifecycle.ingress, "enqueue_route_sync", new=record):
			lifecycle.running(bench)
		self.assertEqual(seen["status"], "Running")

	def test_metering_runs_before_the_save(self):
		"""The deadline and the status it pays for are written in one transaction."""
		bench = self._stopped_bench()
		seen = {}

		def record(doc):
			seen["status"] = frappe.db.get_value(BENCH, doc.name, "status")

		with (
			patch.object(lifecycle.metering, "on_bench_running", new=record),
			patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True),
		):
			lifecycle.running(bench)
		self.assertEqual(seen["status"], "Stopped")

	def _enable_credits(self) -> None:
		"""Armed for this test only, and restored through a commit because the code commits."""
		original = frappe.db.get_single_value(SETTINGS, "enable_credits")
		self.addCleanup(self._write_credits_switch, original)
		self._write_credits_switch(1)

	def _write_credits_switch(self, value) -> None:
		frappe.db.set_single_value(SETTINGS, "enable_credits", value)
		frappe.db.commit()  # nosemgrep -- the restore must outlive the per-test rollback
		frappe.clear_cache(doctype=SETTINGS)

	def test_a_passed_deadline_is_replaced_rather_than_carried_into_running(self):
		"""The grace-restart observable: the next sweep stopped a bench that kept the old one."""
		self._enable_credits()
		bench = self._stopped_bench()
		lease.arm_at(bench, lease.now_ts() - 60)
		lease.disarm(bench)
		bench.reload()
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.running(bench)
		bench.reload()
		self.assertGreater(frappe.utils.cint(bench.expires_at_ts), lease.now_ts())

	def test_the_grace_restart_buys_its_metering_window(self):
		"""`_restart_in_grace` reached `Running` without one, so the next sweep stopped it again."""
		self._enable_credits()
		bench = self._stopped_bench()
		lease.arm_at(bench, lease.now_ts() - 60)
		lease.disarm(bench)
		row = frappe.db.get_value(BENCH, bench.name, api.RENEW_FIELDS, as_dict=True)
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			api._restart_in_grace(row)
		self.assertEqual(row.status, "Running")
		self.assertGreater(
			frappe.utils.cint(frappe.db.get_value(BENCH, bench.name, "expires_at_ts")), lease.now_ts()
		)


class TestStopped(TransitionFixtures, FakeDockerMixin, IntegrationTestCase):
	"""The five side effects a stop must not forget, driven through the transition itself."""

	lab_id = "test-lab-lifecycle-stopped"

	def _running_bench(self, *, container: bool = True):
		return self._bench("Running", "running", container=container)

	def test_a_stop_writes_stopped_and_stops_the_container(self):
		bench = self._running_bench()
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.stopped(bench.name)
		bench.reload()
		self.assertEqual(bench.status, "Stopped")
		# The fake records the container name, which is what `bench_name` holds.
		self.assertEqual(self.docker.stopped, [bench.bench_name])

	def test_a_bench_with_no_container_still_reaches_stopped(self):
		bench = self._running_bench(container=False)
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.stopped(bench.name)
		bench.reload()
		self.assertEqual(bench.status, "Stopped")
		self.assertEqual(self.docker.stopped, [])

	def test_a_stop_deactivates_every_site_and_repeats_harmlessly(self):
		"""Nothing answers inside a stopped container, so no row may stay Active."""
		bench = self._running_bench()
		_make_bench_site(bench.name, "one.localhost")
		_make_bench_site(bench.name, "two.localhost")
		frappe.db.commit()  # nosemgrep -- the transition commits, so the rows it reads must be durable

		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.stopped(bench.name)
			lifecycle.stopped(bench.name)

		statuses = frappe.get_all(SITE, filters={"bench": bench.name}, pluck="status")
		self.assertEqual(statuses, ["Inactive", "Inactive"])

	def test_a_stop_gives_back_the_admission_slot(self):
		"""Stopped is free: a caller at their cap who stopped everything could never start again."""
		bench = self._claimed_bench(self._running_bench())
		before = self._slots(bench.owner)
		with patch.object(lifecycle.ingress, "enqueue_route_sync", autospec=True):
			lifecycle.stopped(bench.name)
		self.assertEqual(self._slots(bench.owner), before - 1)
		self.assertFalse(frappe.db.exists(ADMISSION, bench.name))

	def test_the_route_sync_is_enqueued_after_the_status_is_committed(self):
		"""The job re-reads `status`, so a route synced before the commit keeps routing a live bench."""
		bench = self._running_bench()
		seen = {}

		def record(bench_name):
			seen["status"] = frappe.db.get_value(BENCH, bench_name, "status")

		with patch.object(lifecycle.ingress, "enqueue_route_sync", new=record):
			lifecycle.stopped(bench.name)
		self.assertEqual(seen["status"], "Stopped")

	def test_a_failed_stop_commits_the_lease_release_before_re_raising(self):
		"""Read back through a rollback: what survives one is what the retry will see."""
		bench = self._running_bench()
		frappe.db.set_value(BENCH, bench.name, "lease_state", lease.STOPPING, update_modified=False)
		frappe.db.commit()  # nosemgrep -- the claim must be durable before the transition reads it

		with (
			patch.object(lifecycle, "stop_container", side_effect=Exception("docker is down")),
			self.assertRaises(Exception),
		):
			lifecycle.stopped(bench.name)

		frappe.db.rollback()
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "expiry_attempts"), 1)
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Running")


class TestTornDown(TransitionFixtures, FakeDockerMixin, IntegrationTestCase):
	"""Teardown's effects, and the two things it must leave behind for the next click."""

	lab_id = "test-lab-lifecycle-teardown"

	def _deployed_bench(self):
		return self._bench("Running", "running")

	def test_a_teardown_writes_draft_and_removes_the_container(self):
		bench = self._deployed_bench()

		lifecycle.torn_down(bench)

		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")
		self.assertIsNone(bench.container_id)
		self.assertEqual(self.docker.stopped, [bench.bench_name])
		self.assertEqual(self.docker.removed, [bench.bench_name])

	def test_a_teardown_of_a_reaped_instance_repeats_harmlessly(self):
		"""The reaper and a redeploy can both reach an instance whose container is already gone."""
		bench = self._bench("Stopped", "exited", container=False)

		lifecycle.torn_down(bench)

		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")
		self.assertEqual(self.docker.removed, [])

	def test_a_teardown_deactivates_every_site(self):
		bench = self._deployed_bench()
		_make_bench_site(bench.name, f"one-{bench.name}.localhost")
		_make_bench_site(bench.name, f"two-{bench.name}.localhost")

		lifecycle.torn_down(bench)

		statuses = frappe.get_all(SITE, filters={"bench": bench.name}, pluck="status")
		self.assertEqual(set(statuses), {"Inactive"})

	def test_a_teardown_keeps_the_site_rows_it_deactivated(self):
		"""The row is the site-name claim, so deleting it would lose the name to the next caller."""
		bench = self._deployed_bench()
		_make_bench_site(bench.name, f"claim-{bench.name}.localhost")

		lifecycle.torn_down(bench)

		self.assertEqual(frappe.db.count(SITE, {"bench": bench.name}), 1)

	def test_a_teardown_never_touches_volumes(self):
		"""A reaped instance is one click from running, and the volume is what holds the work."""
		bench = self._deployed_bench()

		lifecycle.torn_down(bench)

		self.assertEqual(self.docker.volume_gets, [])

	def test_a_teardown_gives_back_the_admission_slot(self):
		bench = self._claimed_bench(self._deployed_bench())
		before = self._slots(bench.owner)

		lifecycle.torn_down(bench)

		self.assertEqual(self._slots(bench.owner), before - 1)
		self.assertFalse(frappe.db.exists(ADMISSION, bench.name))

	def test_a_redeploy_holds_its_slot_across_the_teardown(self):
		"""Releasing between the two halves hands the slot away and leaves the caller over cap."""
		bench = self._claimed_bench(self._deployed_bench())
		before = self._slots(bench.owner)

		lifecycle.torn_down(bench, release_admission=False)

		self.assertEqual(self._slots(bench.owner), before)
		self.assertTrue(frappe.db.exists(ADMISSION, bench.name))

	def test_a_teardown_clears_the_metering_deadline(self):
		"""The container it was burning for is gone, so the window must not survive into the next."""
		bench = self._claimed_bench(self._deployed_bench())
		frappe.db.set_value(BENCH, bench.name, "expires_at_ts", lease.now_ts() + 3600, update_modified=False)
		frappe.db.commit()  # nosemgrep -- the transition reads the row it clears
		bench.reload()

		lifecycle.torn_down(bench)

		self.assertEqual(frappe.utils.cint(frappe.db.get_value(BENCH, bench.name, "expires_at_ts")), 0)

	def test_a_teardown_removes_the_instance_route_file(self):
		"""Freed container IPs get reused by Docker, so a stale route file would keep pointing the
		old public hostname at whoever gets that IP next."""
		bench = self._bench("Running", "running", container=False)

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				ingress.publish(bench.name, "benchpress.cloud")
				route_file = Path(tmp) / "instances" / f"{bench.name}.yml"
				self.assertTrue(route_file.exists())

				lifecycle.torn_down(bench)

				self.assertFalse(route_file.exists())

	def test_a_teardown_keeps_the_wildcard_anchor(self):
		"""The anchor outlives every bench — it is what keeps the certificate renewing, so a
		reaper that tidied it away would silently stop renewal."""
		bench = self._bench("Running", "running", container=False)

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				ingress.ensure_anchor("benchpress.cloud")
				ingress.publish(bench.name, "benchpress.cloud")
				anchor = Path(tmp) / "instances" / "wildcard-anchor.yml"

				lifecycle.torn_down(bench)

				self.assertFalse((Path(tmp) / "instances" / f"{bench.name}.yml").exists())
				self.assertTrue(anchor.exists())

	def test_a_teardown_does_not_raise_when_no_route_file_exists(self):
		"""The `base_domain = localhost` case: nothing wrote a route file, so teardown no-ops."""
		bench = self._bench("Running", "running", container=False)

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				lifecycle.torn_down(bench)

		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")

	def test_the_route_goes_directly_rather_than_through_a_job(self):
		"""Teardown already runs on `queue-long`; live routing must not depend on a second job."""
		bench = self._deployed_bench()

		with patch("frappe.enqueue") as enqueue:
			lifecycle.torn_down(bench)

		enqueue.assert_not_called()


class TestTeardownReports(TransitionFixtures, FakeDockerMixin, IntegrationTestCase):
	"""What went and what did not: a teardown used to report the same silence either way."""

	lab_id = "test-lab-lifecycle-teardown-reports"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Database Server", {"container_name": "test-db-teardown"}):
			frappe.get_doc(
				{
					"doctype": "Database Server",
					"container_name": "test-db-teardown",
					"mariadb_version": "10.6",
					"status": "Active",
					"mariadb_root_password": "test-root-password",
				}
			).insert(ignore_permissions=True)
		cls.db_server_name = frappe.db.get_value(
			"Database Server", {"container_name": "test-db-teardown"}, "name"
		)
		frappe.db.commit()  # nosemgrep -- the fixture outlives the per-test rollback

	@classmethod
	def tearDownClass(cls):
		# After the benches, which link this server: Frappe refuses to delete a linked row.
		super().tearDownClass()
		frappe.set_user("Administrator")
		frappe.delete_doc("Database Server", cls.db_server_name, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the fixture was committed, so its removal has to be too

	def _deployed_bench(self, *, with_database: bool = False):
		bench = self._bench("Running", "running")
		if with_database:
			frappe.db.set_value(BENCH, bench.name, "database_server", self.db_server_name)
			bench.reload()
		self._forget_error_logs(bench.name)
		self.addCleanup(self._forget_error_logs, bench.name)
		return bench

	def _container(self, bench):
		return self.docker.containers.get(bench.container_id)

	def test_a_clean_teardown_reports_every_removal_gone(self):
		bench = self._deployed_bench()

		removals = lifecycle.torn_down(bench)

		self.assertEqual(set(removals), {"stop", "container", "database", "vpn_peer", "route"})
		self.assertEqual(set(removals.values()), {lifecycle.GONE})

	def test_a_refused_stop_is_named_with_the_reason_the_daemon_gave(self):
		bench = self._deployed_bench()
		self._container(bench).stop_refusal = "daemon is wedged"

		removals = lifecycle.torn_down(bench)

		self.assertIn("daemon is wedged", removals["stop"])
		self.assertEqual(removals["container"], lifecycle.GONE)

	def test_a_refused_container_removal_is_named_with_the_reason_the_daemon_gave(self):
		bench = self._deployed_bench()
		self._container(bench).remove_refusal = "container is in use"

		removals = lifecycle.torn_down(bench)

		self.assertIn("container is in use", removals["container"])
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")

	def test_a_container_removed_by_hand_first_is_named_rather_than_passed_over(self):
		"""The reaper's own case: the row still names a container the daemon no longer has."""
		bench = self._deployed_bench()
		self._container(bench).remove()

		removals = lifecycle.torn_down(bench)

		self.assertTrue(removals["container"].startswith("failed"))
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")

	def test_a_failed_database_drop_is_named_with_its_reason(self):
		bench = self._deployed_bench(with_database=True)

		with patch("benchpress.mariadb_manager.drop_site_database", side_effect=Exception("db unreachable")):
			removals = lifecycle.torn_down(bench)

		self.assertIn("db unreachable", removals["database"])

	def test_a_failed_route_removal_is_named_with_its_reason(self):
		bench = self._deployed_bench()

		with patch.object(ingress, "withdraw", side_effect=Exception("route mount is missing")):
			removals = lifecycle.torn_down(bench)

		self.assertIn("route mount is missing", removals["route"])

	def test_a_teardown_whose_every_removal_failed_still_reaches_draft(self):
		"""The swallowing stays: an instance must not be left describing what it no longer has."""
		bench = self._deployed_bench(with_database=True)
		container = self._container(bench)
		container.stop_refusal = "daemon is wedged"
		container.remove_refusal = "container is in use"

		with (
			patch("benchpress.mariadb_manager.drop_site_database", side_effect=Exception("db unreachable")),
			patch("benchpress.vpn_adapter.remove_bench_peer", side_effect=Exception("wg agent down")),
			patch.object(ingress, "withdraw", side_effect=Exception("route mount is missing")),
		):
			removals = lifecycle.torn_down(bench)

		self.assertEqual([step for step, result in removals.items() if result == lifecycle.GONE], [])
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")

	def test_a_failed_removal_is_written_down_where_an_operator_reads_it(self):
		"""A failure nobody records is the same failure as the one that was swallowed."""
		bench = self._deployed_bench()
		self._container(bench).remove_refusal = "container is in use"

		lifecycle.torn_down(bench)

		logged = frappe.get_all(ERROR_LOG, filters={"method": ("like", f"%{bench.name}%")}, pluck="error")
		self.assertEqual(len(logged), 1)
		self.assertIn("container is in use", logged[0])

	def test_a_clean_teardown_writes_no_error_log(self):
		bench = self._deployed_bench()

		lifecycle.torn_down(bench)

		self.assertEqual(frappe.db.count(ERROR_LOG, {"method": ("like", f"%{bench.name}%")}), 0)


class TestTeardownFreesTheTunnelIP(TransitionFixtures, FakeDockerMixin, IntegrationTestCase):
	"""The leak: every reaped bench used to hold its WireGuard address forever."""

	lab_id = "test-lab-lifecycle-teardown-vpn"

	def setUp(self):
		super().setUp()
		ensure_wg0_pool()

	def _peered_bench(self):
		bench = self._bench("Running", "running")
		with patch("vpn_management.tasks.reconcile_interface"):
			peer = vpn_adapter.create_container_peer(bench)
		bench.wg_ip = peer["assigned_ip"]
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the teardown under test commits, so its fixture has to be durable
		self.addCleanup(self._drop_peer, peer["peer"])
		self.addCleanup(self._forget_error_logs, bench.name)
		return bench, peer

	def _drop_peer(self, peer_name: str) -> None:
		if frappe.db.exists("VPN Peer", peer_name):
			with patch(RECONCILE_HOOK):
				frappe.delete_doc("VPN Peer", peer_name, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- a leaked peer would outlive the rollback and the test

	@patch(RECONCILE_HOOK)
	def test_a_teardown_gives_the_tunnel_address_back_to_the_pool(self, _reconcile):
		bench, peer = self._peered_bench()
		self.assertEqual(frappe.db.count(ALLOCATION, {"ip_address": peer["assigned_ip"], "allocated": 1}), 1)

		removals = lifecycle.torn_down(bench)

		self.assertEqual(removals["vpn_peer"], lifecycle.GONE)
		self.assertFalse(frappe.db.exists("VPN Peer", peer["peer"]))
		self.assertEqual(frappe.db.count(ALLOCATION, {"ip_address": peer["assigned_ip"], "allocated": 1}), 0)

	@patch(RECONCILE_HOOK)
	def test_a_teardown_forgets_the_address_it_gave_back(self, _reconcile):
		"""The pool hands the address to the next claim, so a bench still showing it is lying."""
		bench, _peer = self._peered_bench()

		lifecycle.torn_down(bench)

		self.assertIsNone(frappe.db.get_value(BENCH, bench.name, "wg_ip"))
		self.assertIsNone(frappe.db.get_value(BENCH, bench.name, "vpn_peer"))

	@patch(RECONCILE_HOOK)
	def test_a_peer_the_teardown_could_not_remove_is_left_linked_for_the_next_deploy(self, _reconcile):
		"""`_setup_container_vpn` removes before it claims, so the link is what lets it retry."""
		bench, peer = self._peered_bench()

		with patch("benchpress.vpn_adapter.remove_bench_peer", side_effect=Exception("wg agent down")):
			removals = lifecycle.torn_down(bench)

		self.assertIn("wg agent down", removals["vpn_peer"])
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "vpn_peer"), peer["peer"])
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "status"), "Draft")


class TestDeployLogHandover(TransitionFixtures, IntegrationTestCase):
	"""A launch opens the run's log before it builds, and the deploy has to write into that row."""

	lab_id = "test-lab-lifecycle-log"

	def _bench_for_deploy(self):
		bench = _fresh_bench(self, self.lab.name)
		self.addCleanup(frappe.db.commit)
		self.addCleanup(lambda name=bench.name: frappe.db.delete("Deploy Log", {"bench": name}))
		self.addCleanup(self._forget_error_logs, bench.name)
		return bench

	def _failed_deploy(self, bench_name, deploy_log=None):
		"""A deploy that stops at the first step, so only the log handling is under test."""
		with (
			patch.object(lifecycle.placement, "pick_network", return_value="benchpress-0") as pick,
			patch.object(lifecycle, "ensure_infrastructure", side_effect=Exception("mariadb down")),
			patch.object(lifecycle, "notify_owner", autospec=True),
		):
			lifecycle._deploy_bench(bench_name, None, deploy_log)
		return pick

	def test_a_pre_opened_log_is_the_only_log_the_deploy_writes(self):
		bench = self._bench_for_deploy()
		_writer, deploy_log = lifecycle.open_deploy_log(bench.name)

		self._failed_deploy(bench.name, deploy_log)

		logs = frappe.get_all("Deploy Log", filters={"bench": bench.name}, fields=["name", "message"])
		self.assertEqual([log.name for log in logs], [deploy_log])
		self.assertIn("mariadb down", logs[0].message)

	def test_a_deploy_given_no_log_still_opens_its_own(self):
		"""The positive control: `create_bench` passes none, and that path must not change."""
		bench = self._bench_for_deploy()

		self._failed_deploy(bench.name)

		logs = frappe.get_all("Deploy Log", filters={"bench": bench.name}, pluck="message")
		self.assertEqual(len(logs), 1)
		self.assertIn("=== Deploy started ===", logs[0])

	def test_a_retry_of_an_errored_bench_re_picks_its_bridge(self):
		"""The guard asks for a container, not for `Draft` — an `Error` retry is pinned to nothing."""
		bench = self._bench_for_deploy()
		frappe.db.set_value(
			BENCH,
			bench.name,
			{"status": "Error", "container_id": None, "bridge_network": "benchpress-7"},
			update_modified=False,
		)
		frappe.db.commit()

		pick = self._failed_deploy(bench.name)

		pick.assert_called_once()
		self.assertEqual(frappe.db.get_value(BENCH, bench.name, "bridge_network"), "benchpress-0")
