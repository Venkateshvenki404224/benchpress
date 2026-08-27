# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""One writer per bench transition, and the side effects that writer must not forget."""

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import api, lifecycle
from benchpress.credits import account, admission, lease
from benchpress.tests.fakes import FakeDockerMixin
from benchpress.tests.test_deploy_manager import (
	_delete_bench_sites,
	_fresh_bench,
	_make_bench_site,
	_make_lab,
)

BENCH = "Bench Instance"
SITE = "Bench Site"
ADMISSION = "Bench Admission"
SETTINGS = "BenchPress Settings"
LIFECYCLE_MODULE = "lifecycle.py"
DB_SERVER_MODULE = "mariadb_manager.py"


class TestOneWriterPerStatus(unittest.TestCase):
	def test_only_lifecycle_writes_running(self):
		"""Four call sites used to. A fifth appearing is the bug this whole item exists to stop."""
		self.assertEqual(_status_writers("Running"), {LIFECYCLE_MODULE})

	def test_only_lifecycle_writes_stopped(self):
		"""`mariadb_manager` writes it too, on `Database Server` — a different doctype's status."""
		self.assertEqual(_status_writers("Stopped"), {LIFECYCLE_MODULE, DB_SERVER_MODULE})


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

	def _claimed_bench(self):
		"""A running bench holding a slot, so the release has something to give back."""
		bench = self._running_bench()
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
		bench = self._claimed_bench()
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
