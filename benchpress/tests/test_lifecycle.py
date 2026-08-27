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
from benchpress.credits import lease
from benchpress.tests.fakes import FakeDockerMixin
from benchpress.tests.test_deploy_manager import _delete_bench_sites, _fresh_bench, _make_lab

BENCH = "Bench Instance"
SETTINGS = "BenchPress Settings"
LIFECYCLE_MODULE = "lifecycle.py"


class TestOneWriterPerStatus(unittest.TestCase):
	def test_only_lifecycle_writes_running(self):
		"""Four call sites used to. A fifth appearing is the bug this whole item exists to stop."""
		self.assertEqual(_status_writers("Running"), {LIFECYCLE_MODULE})


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
	"""`set_value(dt, name, "status", "Running")`, or the same as a dict.

	The doctype is not checked: it is a module constant as often as a literal, and no other
	doctype in the app carries a `Running` status.
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


class TestRunning(FakeDockerMixin, IntegrationTestCase):
	"""The four side effects, driven through the transition itself."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-lifecycle")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all(BENCH, filters={"lab": cls.lab.name}, pluck="name"):
			frappe.db.delete("Deploy Log", {"bench": name})
			_delete_bench_sites(name)
			frappe.delete_doc(BENCH, name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _stopped_bench(self):
		bench = _fresh_bench(self, self.lab.name)
		container = self.docker.add_container(bench.bench_name, status="exited")
		bench.container_id = container.id
		bench.status = "Stopped"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		self.addCleanup(frappe.db.commit)
		return bench

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
