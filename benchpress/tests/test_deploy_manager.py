# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import re
import ssl
import tempfile
import unittest
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
import yaml
from frappe.tests import IntegrationTestCase

from benchpress import ingress
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.tests.fakes import FakeDockerMixin
from benchpress.tests.test_docker_manager import exec_commands, exec_environments

# Any dotted quad, anywhere in the rendered file. The property routes must hold is that no
# address of any kind appears — asserting one known IP is absent would pass for the next one.
IPV4_IN_TEXT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _make_lab(lab_id="test-lab-deploy-mgr"):
	if frappe.db.exists("Lab", lab_id):
		return frappe.get_doc("Lab", lab_id)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": "Test Lab (Deploy Manager)",
			"frappe_version": "version-15",
		}
	).insert(ignore_permissions=True)


def _make_bench(lab_name):
	bench = frappe.get_doc(
		{
			"doctype": "Bench Instance",
			"lab": lab_name,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return bench


def _delete_bench_sites(bench_name):
	"""Drop the `Bench Site` rows a deploy records, before the instance they point at.

	A deploy under test commits, so these outlive the class rollback that discards the
	instance. Cleaned explicitly rather than relied on being rolled back.
	"""
	for name in frappe.get_all("Bench Site", filters={"bench": bench_name}, pluck="name"):
		frappe.delete_doc("Bench Site", name, force=True, ignore_permissions=True)


def _make_bench_site(bench_name, site_name, status="Active"):
	"""A `Bench Site` row a deploy would have recorded, for tests about what happens to it."""
	return frappe.get_doc(
		{
			"doctype": "Bench Site",
			"bench": bench_name,
			"site_name": site_name,
			"status": status,
		}
	).insert(ignore_permissions=True)


def _fresh_bench(case, lab_name):
	frappe.set_user("Administrator")
	existing = get_instance_id("Administrator", lab_name)
	if frappe.db.exists("Bench Instance", existing):
		_delete_bench_sites(existing)
		frappe.delete_doc("Bench Instance", existing, force=True, ignore_permissions=True)
		frappe.db.commit()
	bench = _make_bench(lab_name)
	case.addCleanup(
		lambda n=bench.name: (
			frappe.delete_doc("Bench Instance", n, force=True, ignore_permissions=True)
			if frappe.db.exists("Bench Instance", n)
			else None
		)
	)
	case.addCleanup(lambda n=bench.name: _delete_bench_sites(n))
	case.addCleanup(frappe.db.commit)
	return bench


def _mounted(tmp) -> Path:
	"""The route directory arranged the way production has it: a bind mount that exists.

	Tests create it rather than relying on the writers to, so the missing-mount guard is
	exercised by the tests that are about it instead of bypassed by every other test.
	"""
	target_dir = Path(tmp) / "instances"
	target_dir.mkdir()
	return target_dir


@contextmanager
def _cached_image(lab_name):
	"""Make `lab_name` deploy-ready: `Ready`, with an `image_tag` matching what resolve reports.

	The image step now fails fast unless the lab is `Ready` *and* its stored `image_tag` matches
	the freshly resolved tag — so this sets both together, rather than leaving a caller to pick a
	fixture string that has to happen to match. Every deploy that reaches step 2 in this file
	uses this instead of a real Docker socket.
	"""
	tag = f"benchpress/{lab_name}:lab"
	frappe.db.set_value("Lab", lab_name, {"status": "Ready", "image_tag": tag})
	frappe.db.commit()
	with patch("benchpress.deploy_manager.image_cache.resolve", return_value=(tag, True)):
		yield tag


def _ensure_owner(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Notify Owner",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	return email


def _exec_results(failures: dict | None):
	"""An `exec_in_container` stand-in that fails only the commands a test named."""

	def run(container_id, command, *args, **kwargs):
		for fragment, result in (failures or {}).items():
			if fragment in command:
				return result
		return (0, "")

	return run


class TestDeployManager(FakeDockerMixin, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab()
		if not frappe.db.exists("Database Server", "test-db-server"):
			frappe.get_doc(
				{
					"doctype": "Database Server",
					"container_name": "test-db-server",
					"mariadb_version": "10.6",
				}
			).insert(ignore_permissions=True)
		cls.db_server_name = frappe.db.get_value(
			"Database Server", {"container_name": "test-db-server"}, "name"
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		if cls.db_server_name and frappe.db.exists("Database Server", cls.db_server_name):
			frappe.delete_doc("Database Server", cls.db_server_name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _fresh_bench(self):
		return _fresh_bench(self, self.lab.name)

	# --- stop_bench ---

	@patch("benchpress.deploy_manager.stop_container")
	def test_stop_bench_sets_status_stopped(self, mock_stop):
		from benchpress.deploy_manager import stop_bench

		bench = self._fresh_bench()
		bench.container_id = "container-xyz"
		bench.status = "Running"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		stop_bench(bench.name)
		bench.reload()
		self.assertEqual(bench.status, "Stopped")

	@patch("benchpress.deploy_manager.stop_container")
	def test_stop_bench_calls_stop_container(self, mock_stop):
		from benchpress.deploy_manager import stop_bench

		bench = self._fresh_bench()
		bench.container_id = "container-stop-test"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		stop_bench(bench.name)
		mock_stop.assert_called_once_with("container-stop-test")

	@patch("benchpress.deploy_manager.stop_container")
	def test_stop_bench_skips_container_stop_when_no_container_id(self, mock_stop):
		from benchpress.deploy_manager import stop_bench

		bench = self._fresh_bench()
		bench.container_id = None
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		stop_bench(bench.name)
		mock_stop.assert_not_called()
		bench.reload()
		self.assertEqual(bench.status, "Stopped")

	@patch("benchpress.deploy_manager.stop_container")
	def test_stop_bench_deactivates_every_site_on_the_bench(self, mock_stop):
		"""Nothing answers inside a stopped container, so no row may stay Active."""
		from benchpress.deploy_manager import stop_bench

		bench = self._fresh_bench()
		bench.container_id = "container-stop-sites"
		bench.status = "Running"
		bench.save(ignore_permissions=True)
		_make_bench_site(bench.name, "one.localhost")
		_make_bench_site(bench.name, "two.localhost")
		frappe.db.commit()

		stop_bench(bench.name)
		stop_bench(bench.name)  # a second stop is a no-op, not an error

		statuses = frappe.get_all("Bench Site", filters={"bench": bench.name}, pluck="status")
		self.assertEqual(statuses, ["Inactive", "Inactive"])

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	@patch("benchpress.deploy_manager.stop_container")
	def test_redeploy_bench_resets_status_to_draft_before_deploy(self, mock_stop, mock_remove, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		bench.container_id = "old-container"
		bench.status = "Running"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		status_at_deploy = {}

		def capture_status(bench_name):
			status_at_deploy["status"] = frappe.db.get_value("Bench Instance", bench_name, "status")

		mock_deploy.side_effect = capture_status

		redeploy_bench(bench.name)

		mock_deploy.assert_called_once_with(bench.name)
		self.assertEqual(status_at_deploy["status"], "Draft")

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	@patch("benchpress.deploy_manager.stop_container")
	def test_redeploy_bench_never_touches_volumes(self, mock_stop, mock_remove, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		bench.container_id = "old-container"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		redeploy_bench(bench.name)

		self.assertEqual(self.docker.volume_gets, [])

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	@patch("benchpress.deploy_manager.stop_container")
	@patch("benchpress.mariadb_manager.drop_site_database")
	def test_redeploy_bench_drops_site_database(self, mock_drop_db, mock_stop, mock_remove, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		frappe.db.set_value("Bench Instance", bench.name, "container_id", "old-container")
		frappe.db.set_value("Bench Instance", bench.name, "database_server", self.db_server_name)
		frappe.db.commit()
		bench.reload()

		redeploy_bench(bench.name)
		mock_drop_db.assert_called_once_with(self.db_server_name, bench.site_name)

	# --- deploy concurrency lock (issue #92) ---

	def _held_deploy_lock(self, bench_name):
		from frappe.utils.synchronization import filelock

		return filelock(f"bench_deploy_{bench_name}", timeout=1)

	def _cleanup_deploy_logs(self, bench_name):
		def _purge():
			frappe.db.delete("Deploy Log", {"bench": bench_name})
			frappe.db.commit()

		self.addCleanup(_purge)

	@patch("benchpress.deploy_manager._deploy_bench")
	def test_deploy_skipped_when_lock_held(self, mock_deploy):
		from benchpress.deploy_manager import deploy_bench

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)
		status_before = frappe.db.get_value("Bench Instance", bench.name, "status")

		with self._held_deploy_lock(bench.name):
			deploy_bench(bench.name)

		mock_deploy.assert_not_called()
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), status_before)
		skip_message = frappe.db.get_value(
			"Deploy Log", {"bench": bench.name, "log_type": "warning"}, "message"
		)
		self.assertIn("skipped", skip_message)

	@patch("benchpress.deploy_manager._deploy_bench")
	def test_deploy_lock_released_after_run(self, mock_deploy):
		from benchpress.deploy_manager import deploy_bench

		bench = self._fresh_bench()
		deploy_bench(bench.name)
		deploy_bench(bench.name)

		self.assertEqual(mock_deploy.call_count, 2)

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	def test_redeploy_skipped_when_lock_held(self, mock_remove, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)

		with self._held_deploy_lock(bench.name):
			redeploy_bench(bench.name)

		mock_remove.assert_not_called()
		mock_deploy.assert_not_called()

	def _deploy_log(self, bench_name):
		logs = frappe.get_all(
			"Deploy Log",
			filters={"bench": bench_name},
			fields=["message"],
			order_by="creation desc",
			limit_page_length=1,
		)
		return logs[0].message if logs else ""

	def test_deploy_failure_after_container_creation_cleans_up(self):
		from benchpress import deploy_manager

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)
		frappe.db.set_value(
			"Bench Instance",
			bench.name,
			{"container_ip": "172.30.0.50", "wg_ip": "10.8.0.20"},
		)
		frappe.db.commit()

		with (
			_cached_image(self.lab.name),
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(ingress, "ensure_anchor", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "host_runtimes", autospec=True) as mock_runtimes,
			patch.object(deploy_manager, "container_runtime", autospec=True) as mock_runtime_of,
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			# The deploy starts through the roll wrapper, so the bridge it lands on is a
			# read-back rather than the id that went in.
			patch.object(deploy_manager, "start_bench_container", new=lambda cid, bench, lab: cid),
			patch.object(deploy_manager, "container_network", new=lambda cid: "benchpress-0"),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			patch.object(deploy_manager, "remove_container", autospec=True) as mock_remove_container,
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			patch("benchpress.vpn_adapter.remove_bench_peer", autospec=True) as mock_remove_peer,
		):
			mock_infra.return_value = self.db_server_name
			mock_runtimes.return_value = {"names": {"runc", "sysbox-runc"}, "default": "runc"}
			mock_runtime_of.return_value = "sysbox-runc"
			mock_create.return_value = "cid-cleanup"
			mock_wait.side_effect = Exception("container did not report running")

			deploy_manager.deploy_bench(bench.name)

		mock_remove_container.assert_called_once_with("cid-cleanup")
		mock_remove_peer.assert_called_once()
		bench.reload()
		self.assertEqual(bench.status, "Error")
		self.assertIsNone(bench.container_id)
		self.assertIsNone(bench.container_ip)
		self.assertIsNone(bench.wg_ip)
		# The screen reporting the failure reads the outcome, never infers it.
		self.assertIn("Cleanup: removed container created by this run", self._deploy_log(bench.name))

	def test_deploy_failure_before_container_skips_cleanup(self):
		from benchpress import deploy_manager

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)
		frappe.db.set_value(
			"Bench Instance",
			bench.name,
			{
				"container_id": "old-container",
				"container_ip": "172.30.0.50",
				"wg_ip": "10.8.0.20",
			},
		)
		frappe.db.commit()

		with (
			_cached_image(self.lab.name),
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "remove_container", autospec=True) as mock_remove_container,
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			patch("benchpress.vpn_adapter.remove_bench_peer", autospec=True) as mock_remove_peer,
		):
			mock_infra.side_effect = Exception("infrastructure unavailable")

			deploy_manager.deploy_bench(bench.name)

		mock_remove_container.assert_not_called()
		mock_remove_peer.assert_not_called()
		self.assertIn(deploy_manager.NOTHING_TO_ROLL_BACK, self._deploy_log(bench.name))
		bench.reload()
		self.assertEqual(bench.status, "Error")
		self.assertEqual(bench.container_id, "old-container")
		self.assertEqual(bench.container_ip, "172.30.0.50")
		self.assertEqual(bench.wg_ip, "10.8.0.20")

	# --- enqueue-time dedupe (issue #92 phase 2) ---

	@patch("frappe.enqueue")
	def test_deploy_enqueues_carry_dedupe_job_id(self, mock_enqueue):
		from benchpress.api import create_bench

		mock_enqueue.return_value = MagicMock()
		bench = self._fresh_bench()

		bench.enqueue_deploy()
		bench.enqueue_redeploy()
		create_bench(frappe.as_json({"lab": self.lab.name}))

		self.assertEqual(mock_enqueue.call_count, 3)
		for call in mock_enqueue.call_args_list:
			self.assertEqual(call.kwargs["job_id"], f"deploy_bench:{bench.name}")
			self.assertTrue(call.kwargs["deduplicate"])

	@patch("frappe.msgprint")
	@patch("frappe.enqueue")
	@patch(
		"benchpress.benchpress.doctype.bench_instance.bench_instance.is_job_enqueued",
		return_value=True,
	)
	def test_deduped_enqueue_messages_user(self, mock_enqueued, mock_enqueue, mock_msgprint):
		bench = self._fresh_bench()

		bench.enqueue_deploy()
		bench.enqueue_redeploy()

		mock_enqueue.assert_not_called()
		for call in mock_msgprint.call_args_list:
			self.assertIn("already in progress", str(call.args[0]))

	# --- build_linkuser_args (Lab.shell wiring) ---

	def test_build_linkuser_args_includes_lab_shell(self):
		from benchpress.deploy_manager import build_linkuser_args

		bench = self._fresh_bench()
		bench.ssh_username = "tester"
		self.lab.shell = "/bin/zsh"
		settings = frappe.get_single("BenchPress Settings")

		args = build_linkuser_args(bench, self.lab, settings)

		# 7 args: mount_target was removed, and SSH_PASSWORD now travels in the environment.
		self.assertEqual(len(args), 7)
		self.assertEqual(args[5], settings.base_domain or "localhost")  # BASE_DOMAIN position
		self.assertEqual(args[-1], "/bin/zsh")  # LOGIN_SHELL position (right after BASE_DOMAIN)

	def test_build_linkuser_args_defaults_shell_to_bash(self):
		from benchpress.deploy_manager import build_linkuser_args

		bench = self._fresh_bench()
		bench.ssh_username = "tester"
		self.lab.shell = None
		settings = frappe.get_single("BenchPress Settings")

		args = build_linkuser_args(bench, self.lab, settings)

		self.assertEqual(args[-1], "/bin/bash")

	def test_linkuser_command_survives_hostile_arguments(self):
		import shlex

		from benchpress.deploy_manager import linkuser_command

		args = ["tester", "o'brien@example.com", "Venki's Lab; rm -rf /", "$(id)", "`id`", ""]
		command = linkuser_command(args)

		parsed = shlex.split(command)
		self.assertEqual(parsed[0:2], ["bash", "/opt/benchpress/scripts/linkuser.sh"])
		self.assertEqual(parsed[2:], args)


class TestDeployStepMarkers(IntegrationTestCase):
	"""Phase 4: the run reports its eleven steps, in the order the code runs them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-steps")
		if not frappe.db.exists("Database Server", "test-db-steps"):
			frappe.get_doc(
				{
					"doctype": "Database Server",
					"container_name": "test-db-steps",
					"mariadb_version": "10.6",
				}
			).insert(ignore_permissions=True)
		cls.db_server_name = frappe.db.get_value(
			"Database Server", {"container_name": "test-db-steps"}, "name"
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.db.delete("Deploy Log", {"bench": name})
			_delete_bench_sites(name)
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		if cls.db_server_name and frappe.db.exists("Database Server", cls.db_server_name):
			frappe.delete_doc("Database Server", cls.db_server_name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _bench(self):
		bench = _fresh_bench(self, self.lab.name)
		self.addCleanup(frappe.db.commit)
		self.addCleanup(lambda name=bench.name: frappe.db.delete("Deploy Log", {"bench": name}))
		return bench

	def _run_deploy(
		self,
		bench,
		site_result=(0, "site created"),
		cache_hit=True,
		exec_failures=None,
		write_error=None,
		cert_error=None,
		registered_runtimes=("runc", "sysbox-runc"),
	):
		"""A whole deploy with every side effect mocked but the log itself.

		`cache_hit=False` leaves the lab `Draft` with no `image_tag`, so the image step fails
		fast — deploy never builds.
		`exec_failures` maps a fragment of a container command to the result that command
		returns, so one exec can fail while the rest of the run succeeds. `write_error` makes
		every `write_file_to_container` raise, the way a read-only target path would.
		`cert_error` is what the certificate check reports; only the socket is mocked, so the
		line the log carries is still written by the real `ingress.log_certificate_state`.
		`registered_runtimes` is what the daemon claims to have, so a test can starve the
		pre-build gate without depending on what this host happens to run.
		"""
		from benchpress import deploy_manager

		# Traefik's route directory is mounted into queue-long, not into the container the
		# tests run in, so it is redirected rather than mocked — the real anchor and route
		# writers run, and `self.route_dir` is what they wrote.
		route_dir = tempfile.TemporaryDirectory()
		self.addCleanup(route_dir.cleanup)
		self.route_dir = Path(route_dir.name) / "dynamic"
		self.route_dir.mkdir()

		with (
			_cached_image(self.lab.name) if cache_hit else nullcontext(),
			patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", self.route_dir),
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "host_runtimes", autospec=True) as mock_runtimes,
			patch.object(deploy_manager, "container_runtime", autospec=True) as mock_runtime_of,
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			# The deploy starts through the roll wrapper, so the bridge it lands on is a
			# read-back rather than the id that went in.
			patch.object(deploy_manager, "start_bench_container", new=lambda cid, bench, lab: cid),
			patch.object(deploy_manager, "container_network", new=lambda cid: "benchpress-0"),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			# Only the socket is mocked, not the reporting around it: a unit test must not
			# depend on a running Traefik, but the log line must still be the real one.
			patch.object(ingress, "_certificate_error", autospec=True, return_value=cert_error) as mock_cert,
			patch.object(deploy_manager, "write_file_to_container", autospec=True) as mock_write,
			patch.object(deploy_manager, "exec_in_container", autospec=True) as mock_exec,
			patch.object(deploy_manager, "create_site_in_container", autospec=True) as mock_site,
			patch.object(deploy_manager, "remove_container", autospec=True),
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			patch("benchpress.vpn_adapter.remove_bench_peer", autospec=True),
			patch("benchpress.vpn_adapter.configure_container", autospec=True),
			patch("benchpress.vpn_adapter.create_container_peer", autospec=True) as mock_peer,
		):
			self.cert_check = mock_cert
			self.execs = mock_exec
			mock_infra.return_value = self.db_server_name
			mock_runtimes.return_value = {"names": set(registered_runtimes), "default": "runc"}
			mock_runtime_of.return_value = "sysbox-runc"
			mock_create.return_value = "cid-steps"
			mock_wait.return_value = "172.30.0.11"
			mock_exec.side_effect = _exec_results(exec_failures)
			if write_error:
				mock_write.side_effect = Exception(write_error)
			mock_peer.return_value = {
				"peer": "peer-steps",
				"assigned_ip": "172.27.0.11",
				"private_key": "private",
			}
			if isinstance(site_result, Exception):
				mock_site.side_effect = site_result
			else:
				mock_site.return_value = site_result

			deploy_manager.deploy_bench(bench.name)

	def _log(self, bench_name):
		logs = frappe.get_all(
			"Deploy Log",
			filters={"bench": bench_name},
			fields=["message"],
			order_by="creation desc",
			limit_page_length=1,
		)
		return logs[0].message if logs else ""

	def _emitted_steps(self, bench_name):
		from benchpress.deploy_pipeline import parse_step_line

		parsed = [parse_step_line(line) for line in self._log(bench_name).splitlines()]
		return [step for step in parsed if step]

	def test_all_eleven_steps_are_emitted_in_the_code_s_order(self):
		from benchpress.deploy_pipeline import DEPLOY_STEPS

		bench = self._bench()
		self._run_deploy(bench)

		emitted = self._emitted_steps(bench.name)
		self.assertEqual([step["step_key"] for step in emitted], [step.key for step in DEPLOY_STEPS])
		self.assertEqual([step["step_index"] for step in emitted], list(range(1, 12)))

	def test_the_three_steps_that_had_no_marker_now_emit_one(self):
		bench = self._bench()
		self._run_deploy(bench)

		keys = {step["step_key"] for step in self._emitted_steps(bench.name)}
		self.assertTrue({"container_ip", "site_config", "assets"} <= keys)

	def test_every_step_line_keeps_the_legacy_marker_prefix(self):
		bench = self._bench()
		self._run_deploy(bench)

		for line in self._log(bench.name).splitlines():
			if "Step " in line and "===" in line:
				self.assertTrue(line.startswith("=== ") and line.endswith(" ==="), line)

	def test_elapsed_times_never_go_backwards(self):
		bench = self._bench()
		self._run_deploy(bench)

		elapsed = [step["step_elapsed"] for step in self._emitted_steps(bench.name)]
		self.assertEqual(elapsed, sorted(elapsed))

	def test_a_failure_marks_the_failing_step_and_no_later_one(self):
		bench = self._bench()
		self._run_deploy(bench, site_result=Exception("bench new-site exploded"))

		keys = [step["step_key"] for step in self._emitted_steps(bench.name)]
		self.assertEqual(keys[-1], "site")
		self.assertFalse({"assets", "ssh_user", "code_server", "complete"} & set(keys))
		self.assertIn("=== Deploy failed:", self._log(bench.name))

	def test_a_disabled_code_server_still_reports_its_step(self):
		bench = self._bench()
		frappe.db.set_value("Lab", self.lab.name, "enable_code_server", 0)
		self.addCleanup(frappe.db.set_value, "Lab", self.lab.name, "enable_code_server", 1)
		frappe.db.commit()

		self._run_deploy(bench)

		log = self._log(bench.name)
		self.assertIn("Step 10/11", log)
		self.assertIn("Code server is disabled for this lab", log)

	def test_an_unregistered_runtime_fails_before_the_image_step(self):
		"""The image build is where the minutes go; a doomed deploy must not pay for one."""
		bench = self._bench()
		frappe.db.set_value("Bench Instance", bench.name, "runtime", "sysbox")
		frappe.db.commit()

		self._run_deploy(bench, registered_runtimes=("runc",))

		log = self._log(bench.name)
		keys = [step["step_key"] for step in self._emitted_steps(bench.name)]
		self.assertEqual(keys, ["infrastructure"])
		self.assertNotIn("Step 2/11", log)
		self.assertIn("sysbox-runc", log)
		self.assertIn("runc", log)
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")

	def test_a_registered_runtime_passes_the_gate(self):
		"""The negative control: a gate that only ever sees failing input is not a gate."""
		bench = self._bench()
		frappe.db.set_value("Bench Instance", bench.name, "runtime", "sysbox")
		frappe.db.commit()

		self._run_deploy(bench)

		keys = [step["step_key"] for step in self._emitted_steps(bench.name)]
		self.assertEqual(keys[-1], "complete")

	def test_the_log_records_the_runtime_the_container_actually_ran_under(self):
		"""Read back off the container, so a bench's isolation is answerable from the log."""
		bench = self._bench()

		self._run_deploy(bench)

		self.assertIn("container runtime sysbox-runc", self._log(bench.name))

	def _deploy_messages(self, publish):
		"""Only our own events: a deploy also saves docs, and every save publishes."""
		return [
			call.kwargs for call in publish.call_args_list if call.kwargs.get("event") == "bench_deploy_log"
		]

	def test_a_second_user_never_receives_another_user_s_deploy(self):
		bench = self._bench()
		frappe.db.set_value("Bench Instance", bench.name, "owner", "Administrator")
		frappe.db.commit()

		with patch("frappe.publish_realtime") as publish:
			self._run_deploy(bench)

		published = self._deploy_messages(publish)
		self.assertTrue(published)
		self.assertEqual({call["user"] for call in published}, {"Administrator"})
		# A room would broadcast past the user scoping the leak fix relies on.
		self.assertFalse(any(call.get("room") for call in published))

	def test_an_unbuilt_lab_fails_the_image_step_without_touching_the_build_log(self):
		"""Deploy is a lookup now, never a build — Phase 3. The image step fails fast at step
		2/11 and the Build Log tab (a separate action's log) is never written by a deploy.
		"""
		from benchpress import deploy_manager

		bench = self._bench()
		self.addCleanup(frappe.db.delete, "Build Log", {"lab": self.lab.name})

		with patch.object(deploy_manager, "build_lab_image", autospec=True) as mock_build:
			self._run_deploy(bench, cache_hit=False)

		mock_build.assert_not_called()
		deploy_log = self._log(bench.name)
		self.assertIn("Step 2/11", deploy_log)
		self.assertIn("No built image", deploy_log)
		self.assertEqual(frappe.db.count("Build Log", {"lab": self.lab.name}), 0)

	# --- Phase 3: a command the run does not check is a claim it cannot make ---

	def _enable_code_server(self):
		before = frappe.db.get_value("Lab", self.lab.name, "enable_code_server")
		frappe.db.set_value("Lab", self.lab.name, "enable_code_server", 1)
		self.addCleanup(frappe.db.set_value, "Lab", self.lab.name, "enable_code_server", before)
		frappe.db.commit()

	def _bench_field(self, bench, field):
		return frappe.db.get_value("Bench Instance", bench.name, field)

	def test_a_failed_restart_fails_step_ten_and_stores_no_ide_address(self):
		"""An address that answers nothing is worse than a deploy that admits it broke."""
		bench = self._bench()
		self._enable_code_server()
		frappe.db.set_value("Bench Instance", bench.name, "code_server_url", "http://stale:8080/")
		frappe.db.commit()

		self._run_deploy(bench, exec_failures={"restart.sh": (1, "code-server: no such unit")})

		log = self._log(bench.name)
		self.assertIn("restart.sh failed (exit 1): code-server: no such unit", log)
		self.assertNotIn("code-server ready at", log)
		self.assertEqual(self._bench_field(bench, "status"), "Error")
		# The empty field is the contract: `LabHeader.showCodeServer` reads it to hide the button.
		self.assertFalse(self._bench_field(bench, "code_server_url"))

	def test_a_failed_config_permission_fix_fails_step_ten(self):
		"""A config code-server cannot read, or that every account can, is not a working IDE."""
		bench = self._bench()
		self._enable_code_server()

		self._run_deploy(bench, exec_failures={"chown -R": (1, "Operation not permitted")})

		log = self._log(bench.name)
		self.assertIn("Securing the code-server config failed (exit 1)", log)
		self.assertNotIn("code-server ready at", log)
		self.assertFalse(self._bench_field(bench, "code_server_url"))

	@patch("benchpress.deploy_manager.secrets.token_urlsafe")
	def test_the_ssh_password_goes_into_the_environment_and_into_no_command(self, token):
		"""Docker publishes every exec command line, and linkuser.sh read the password from argv."""
		sentinel = "sS1XnOtAr3alPassw0rd"
		token.return_value = sentinel
		bench = self._bench()

		self._run_deploy(bench)

		linkuser = [call for call in self.execs.call_args_list if "linkuser.sh" in call.args[1]]
		self.assertEqual(len(linkuser), 1)
		self.assertEqual(linkuser[0].kwargs.get("environment"), {"SSH_PASSWORD": sentinel})
		for call in self.execs.call_args_list:
			self.assertNotIn(sentinel, call.args[1])

	@patch("benchpress.deploy_manager.secrets.token_urlsafe")
	@patch("benchpress.docker_manager.get_client")
	def test_the_code_server_password_goes_into_the_environment_and_into_no_command(self, get_client, token):
		"""Docker publishes every exec command line, and the IDE password was in one."""
		from benchpress import deploy_manager

		sentinel = "cS1XnOtAr3alPassw0rd"
		token.return_value = sentinel
		container = get_client.return_value.containers.get.return_value
		container.exec_run.return_value = (0, b"")
		bench = self._bench()
		bench.ssh_username = "tenant"

		deploy_manager._start_code_server(
			bench, "cid-cs", MagicMock(), SimpleNamespace(base_domain="localhost")
		)

		written = [env for env in exec_environments(container) if sentinel in str(env)]
		self.assertEqual(len(written), 1)
		for command in exec_commands(container):
			self.assertNotIn(sentinel, command)

	def test_a_working_step_ten_stores_the_tunnel_address_on_localhost(self):
		bench = self._bench()
		self._enable_code_server()
		self._set_base_domain("localhost")

		self._run_deploy(bench)

		log = self._log(bench.name)
		self.assertEqual(log.count("code-server ready at"), 1)
		self.assertEqual(self._bench_field(bench, "code_server_url"), "http://172.27.0.11:8080/")
		self.assertEqual(self._bench_field(bench, "status"), "Running")

	def test_a_working_step_ten_stores_the_public_ide_hostname(self):
		bench = self._bench()
		self._enable_code_server()
		self._set_base_domain("benchpress.cloud")

		self._run_deploy(bench)

		log = self._log(bench.name)
		self.assertEqual(log.count("code-server ready at"), 1)
		self.assertEqual(
			self._bench_field(bench, "code_server_url"), f"https://ide-{bench.name}.benchpress.cloud"
		)
		self.assertEqual(self._bench_field(bench, "status"), "Running")

	# --- public_url (phase 1: public site hostname) ---

	def _set_base_domain(self, value):
		before = frappe.db.get_single_value("BenchPress Settings", "base_domain")
		frappe.db.set_single_value("BenchPress Settings", "base_domain", value)
		frappe.clear_cache(doctype="BenchPress Settings")
		self.addCleanup(frappe.db.set_single_value, "BenchPress Settings", "base_domain", before)
		self.addCleanup(frappe.clear_cache, doctype="BenchPress Settings")
		frappe.db.commit()

	def test_public_url_set_when_base_domain_is_configured(self):
		bench = self._bench()
		self._set_base_domain("benchpress.cloud")

		self._run_deploy(bench)

		self.assertEqual(self._bench_field(bench, "public_url"), f"https://{bench.name}.benchpress.cloud")

	def test_public_url_stays_unset_with_localhost_base_domain(self):
		bench = self._bench()
		self._set_base_domain("localhost")

		self._run_deploy(bench)

		self.assertFalse(self._bench_field(bench, "public_url"))

	def test_a_localhost_deploy_writes_no_traefik_config_at_all(self):
		"""A dev checkout has no Traefik: the deploy completes and puts nothing in the route
		directory — skipped silently, not attempted and failed."""
		bench = self._bench()
		self._set_base_domain("localhost")

		self._run_deploy(bench)

		self.assertIn("Step 11/11", self._log(bench.name))
		self.assertEqual(list(self.route_dir.iterdir()), [])

	def test_a_public_deploy_writes_the_anchor_beside_the_instance_route(self):
		"""The two halves ship together: without the anchor the instance routers name no
		resolver and nothing has asked for the wildcard, which is the 526 that reverted
		this shape once already."""
		bench = self._bench()
		self._set_base_domain("benchpress.cloud")

		self._run_deploy(bench)

		written = sorted(p.name for p in self.route_dir.iterdir())
		self.assertEqual(written, sorted(["wildcard-anchor.yml", f"{bench.name}.yml"]))
		self.assertIn("Traefik wildcard anchor written for *.benchpress.cloud", self._log(bench.name))
		self.assertNotIn("certResolver", (self.route_dir / f"{bench.name}.yml").read_text())

	def test_a_public_deploy_states_which_certificate_serves_the_url(self):
		"""Phase 2: the routers name no resolver, so the deploy has to say the store held a
		certificate — otherwise the first evidence it did not is a user meeting a 526."""
		bench = self._bench()
		self._set_base_domain("benchpress.cloud")

		self._run_deploy(bench)

		self.cert_check.assert_called_once_with(f"{bench.name}.benchpress.cloud")
		self.assertIn(
			f"TLS ready for {bench.name}.benchpress.cloud on the *.benchpress.cloud wildcard",
			self._log(bench.name),
		)

	def test_a_bad_certificate_warns_without_failing_the_deploy(self):
		"""Non-fatal by design. The container is up and the site exists, so the owner can still
		work over the VPN — turning a cosmetic problem into a failed deploy would cost more
		than it reports."""
		bench = self._bench()
		self._set_base_domain("benchpress.cloud")

		self._run_deploy(bench, cert_error=f"certificate does not cover {bench.name}.benchpress.cloud")

		log = self._log(bench.name)
		self.assertIn(f"WARNING: certificate does not cover {bench.name}.benchpress.cloud", log)
		self.assertIn("the public URL will fail in a browser", log)
		# The deploy still finished: eleven steps, and the bench is usable.
		self.assertIn("Step 11/11", log)
		self.assertEqual(self._bench_field(bench, "status"), "Running")

	def test_a_localhost_deploy_opens_no_socket_and_logs_no_certificate_line(self):
		"""A dev checkout has no Traefik, so checking would time out to say nothing. Matches
		the anchor and route writers: skipped silently, not attempted and failed."""
		bench = self._bench()
		self._set_base_domain("localhost")

		self._run_deploy(bench)

		self.cert_check.assert_not_called()
		self.assertNotIn("TLS ready", self._log(bench.name))

	def test_a_failed_file_write_fails_the_deploy_at_the_step_that_wrote_it(self):
		"""Hole 4: a silently unwritten `common_site_config.json` is a site that cannot find redis."""
		bench = self._bench()

		self._run_deploy(bench, write_error="Writing common_site_config.json failed (exit 1): read-only")

		keys = [step["step_key"] for step in self._emitted_steps(bench.name)]
		self.assertEqual(keys[-1], "site_config")
		self.assertIn("common_site_config.json failed", self._log(bench.name))
		self.assertEqual(self._bench_field(bench, "status"), "Error")

	def test_the_assets_step_never_builds_in_the_container(self):
		"""Assets ship in the image; the deploy must never run `bench build` itself."""
		bench = self._bench()

		self._run_deploy(bench, exec_failures={"bench build": (1, "must never be called")})

		log = self._log(bench.name)
		self.assertIn("Assets ship in the image", log)
		self.assertNotIn("must never be called", log)
		self.assertEqual(self._bench_field(bench, "status"), "Running")
		self.assertIn("Step 11/11", log)

	def test_a_clean_deploy_writes_no_warning_lines(self):
		"""The checks above must not turn a healthy run into a noisy one."""
		bench = self._bench()
		self._enable_code_server()

		self._run_deploy(bench)

		self.assertNotIn("failed", self._log(bench.name))

	def test_an_unbuilt_image_is_attributed_to_the_deploy_not_a_build(self):
		"""Phase 3: deploy never builds, so its own failure is never redirected to a Build Log —
		there isn't one to redirect to, and there never will be for this failure mode.
		"""
		from benchpress import lab_detail

		bench = self._bench()
		frappe.db.set_value("Lab", self.lab.name, {"status": "Draft", "image_tag": None})
		frappe.db.commit()

		self._run_deploy(bench, cache_hit=False)

		failure = lab_detail.get_lab(self.lab.name)["failure"]
		self.assertEqual(failure["source"], "deploy")
		self.assertIn("No built image", failure["reason"])

	def test_a_deploy_that_broke_after_the_image_still_blames_the_deploy(self):
		"""A failure past the image step is a deploy failure, plainly — nothing to redirect."""
		from benchpress import lab_detail

		bench = self._bench()
		self._run_deploy(bench, site_result=Exception("bench new-site exploded"))

		failure = lab_detail.get_lab(self.lab.name)["failure"]
		self.assertEqual(failure["source"], "deploy")
		self.assertIn("bench new-site exploded", failure["reason"])

	def test_step_lines_are_published_as_the_step_type(self):
		bench = self._bench()

		with patch("frappe.publish_realtime") as publish:
			self._run_deploy(bench)

		messages = [call["message"] for call in self._deploy_messages(publish)]
		types = {message["step_key"]: message["type"] for message in messages if message.get("step_key")}
		self.assertEqual(types["infrastructure"], "step")
		# The eleventh step is also the run's success line.
		self.assertEqual(types["complete"], "success")


class TestTerminalStateNotifications(IntegrationTestCase):
	"""Phase 3 (#98): every terminal deploy/build state desk-notifies the owner, best-effort."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-notify")
		cls.owner = _ensure_owner("notify-owner@example.com")
		if not frappe.db.exists("Database Server", "test-db-notify"):
			frappe.get_doc(
				{
					"doctype": "Database Server",
					"container_name": "test-db-notify",
					"mariadb_version": "10.6",
				}
			).insert(ignore_permissions=True)
		cls.db_server_name = frappe.db.get_value(
			"Database Server", {"container_name": "test-db-notify"}, "name"
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		if cls.db_server_name and frappe.db.exists("Database Server", cls.db_server_name):
			frappe.delete_doc("Database Server", cls.db_server_name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _owned_bench(self):
		bench = _fresh_bench(self, self.lab.name)
		frappe.db.set_value("Bench Instance", bench.name, "owner", self.owner)
		frappe.db.commit()
		self._cleanup_side_effects(bench_name=bench.name)
		return bench

	def _cleanup_side_effects(self, bench_name=None, lab_name=None):
		# deploy/build commit mid-flight, so test-transaction rollback can't
		# undo these rows — the file's manual-cleanup idiom.
		def _purge():
			frappe.db.delete("Notification Log", {"for_user": self.owner})
			if bench_name:
				frappe.db.delete("Deploy Log", {"bench": bench_name})
			if lab_name:
				frappe.db.delete("Build Log", {"lab": lab_name})
			frappe.db.commit()

		self.addCleanup(_purge)

	def _owner_notification(self, document_type, document_name):
		return frappe.db.get_value(
			"Notification Log",
			{"for_user": self.owner, "document_type": document_type, "document_name": document_name},
			["type", "subject"],
			as_dict=True,
		)

	@patch("benchpress.deploy_manager.ensure_infrastructure", autospec=True)
	def test_deploy_failure_notifies_owner(self, mock_infra):
		from benchpress.deploy_manager import deploy_bench

		bench = self._owned_bench()
		mock_infra.side_effect = Exception("mariadb container refused to start")

		deploy_bench(bench.name)

		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")
		notification = self._owner_notification("Bench Instance", bench.name)
		self.assertIsNotNone(notification)
		self.assertEqual(notification.type, "Alert")
		self.assertIn("failed", notification.subject)

	def test_deploy_success_notifies_owner(self):
		from benchpress import deploy_manager

		bench = self._owned_bench()
		frappe.db.commit()

		with (
			_cached_image(self.lab.name),
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "host_runtimes", autospec=True) as mock_runtimes,
			patch.object(deploy_manager, "container_runtime", autospec=True) as mock_runtime_of,
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			# The deploy starts through the roll wrapper, so the bridge it lands on is a
			# read-back rather than the id that went in.
			patch.object(deploy_manager, "start_bench_container", new=lambda cid, bench, lab: cid),
			patch.object(deploy_manager, "container_network", new=lambda cid: "benchpress-0"),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			patch.object(ingress, "publish", autospec=True),
			patch.object(ingress, "ensure_anchor", autospec=True),
			patch.object(ingress, "_certificate_error", autospec=True, return_value=None),
			patch.object(deploy_manager, "_setup_container_vpn", autospec=True),
			patch.object(deploy_manager, "write_file_to_container", autospec=True),
			patch.object(deploy_manager, "exec_in_container", autospec=True) as mock_exec,
			patch.object(deploy_manager, "create_site_in_container", autospec=True) as mock_site,
		):
			mock_infra.return_value = self.db_server_name
			mock_runtimes.return_value = {"names": {"runc", "sysbox-runc"}, "default": "runc"}
			mock_runtime_of.return_value = "sysbox-runc"
			mock_create.return_value = "cid-notify"
			mock_wait.return_value = "172.30.0.9"
			mock_exec.return_value = (0, "")
			mock_site.return_value = (0, "site created")

			deploy_manager.deploy_bench(bench.name)

		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Running")
		notification = self._owner_notification("Bench Instance", bench.name)
		self.assertIsNotNone(notification)
		self.assertIn("deployed", notification.subject)

	@patch("benchpress.deploy_manager.build_lab_image", autospec=True)
	def test_build_lab_success_notifies_lab_owner(self, mock_build):
		from benchpress.deploy_manager import build_lab

		frappe.db.set_value("Lab", self.lab.name, "owner", self.owner)
		frappe.db.commit()
		self._cleanup_side_effects(lab_name=self.lab.name)
		mock_build.return_value = "benchpress/x:latest"

		build_lab(self.lab.name)

		notification = self._owner_notification("Lab", self.lab.name)
		self.assertIsNotNone(notification)
		self.assertEqual(notification.type, "Alert")
		self.assertIn("complete", notification.subject)

	@patch("benchpress.deploy_manager.build_lab_image", autospec=True)
	def test_build_lab_failure_notifies_lab_owner(self, mock_build):
		from benchpress.deploy_manager import build_lab

		frappe.db.set_value("Lab", self.lab.name, "owner", self.owner)
		frappe.db.commit()
		self._cleanup_side_effects(lab_name=self.lab.name)
		mock_build.side_effect = Exception("docker build blew up")

		build_lab(self.lab.name)

		self.assertEqual(frappe.db.get_value("Lab", self.lab.name, "status"), "Error")
		notification = self._owner_notification("Lab", self.lab.name)
		self.assertIsNotNone(notification)
		self.assertIn("failed", notification.subject)

	@patch(
		"frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification",
		autospec=True,
	)
	@patch("benchpress.deploy_manager.ensure_infrastructure", autospec=True)
	def test_notification_failure_does_not_break_deploy(self, mock_infra, mock_notify):
		from benchpress.deploy_manager import deploy_bench

		bench = self._owned_bench()
		mock_infra.side_effect = Exception("infrastructure down")
		mock_notify.side_effect = Exception("redis down")

		deploy_bench(bench.name)  # must not raise: _notify_owner swallows the failure

		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")
		self.assertFalse(frappe.db.exists("Notification Log", {"for_user": self.owner}))


class TestRecordPrimarySite(IntegrationTestCase):
	"""The site a deploy makes must be visible, and pressing Deploy twice must not duplicate it."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-primary-site")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _bench(self):
		bench = _fresh_bench(self, self.lab.name)
		bench.site_name = f"{bench.name}.localhost"
		bench.save(ignore_permissions=True)
		return bench

	def test_records_the_site_the_deploy_created(self):
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench()

		_record_primary_site(bench, self.lab, "secret-one")

		site = frappe.get_doc("Bench Site", {"bench": bench.name})
		self.assertEqual(site.site_name, bench.site_name)
		self.assertEqual(site.status, "Active")
		self.assertEqual([row.app_name for row in site.apps_installed], ["frappe"])

	def test_a_caller_chosen_site_name_carries_through_to_the_bench_site_row(self):
		"""Closes the loop on issue #125: the row must carry the chosen name, not just a hash."""
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench()
		bench.site_name = "acme.benchpress.cloud"
		bench.save(ignore_permissions=True)

		_record_primary_site(bench, self.lab, "secret-one")

		site = frappe.get_doc("Bench Site", {"bench": bench.name})
		self.assertEqual(site.site_name, "acme.benchpress.cloud")
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "site_name"), site.site_name)

	def test_relabelling_the_instance_leaves_the_site_name_alone(self):
		"""`site_name` is the name the database was created under, so a relabel must not move it."""
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench()
		_record_primary_site(bench, self.lab, "secret-one")

		frappe.db.set_value("Bench Instance", bench.name, "domain", "relabelled.example")
		_record_primary_site(bench, self.lab, "secret-one")

		site = frappe.get_doc("Bench Site", {"bench": bench.name})
		self.assertEqual(site.site_name, bench.site_name)

	def test_a_second_deploy_refreshes_the_row_instead_of_duplicating_it(self):
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench()

		_record_primary_site(bench, self.lab, "secret-one")
		_record_primary_site(bench, self.lab, "secret-two")

		self.assertEqual(frappe.db.count("Bench Site", {"bench": bench.name}), 1)

	def test_teardown_marks_the_site_inactive(self):
		from benchpress.deploy_manager import _deactivate_bench_sites, _record_primary_site

		bench = self._bench()
		_record_primary_site(bench, self.lab, "secret-one")

		_deactivate_bench_sites(bench)

		self.assertEqual(frappe.db.get_value("Bench Site", {"bench": bench.name}, "status"), "Inactive")

	@patch("benchpress.deploy_manager.stop_container")
	def test_a_deploy_returns_a_stopped_site_to_active(self, mock_stop):
		"""The round trip, which needs no code of its own: `_record_primary_site` already writes
		`Active`, so a stop followed by a deploy must land back where it started."""
		from benchpress.deploy_manager import _record_primary_site, stop_bench

		bench = self._bench()
		bench.container_id = "container-round-trip"
		bench.save(ignore_permissions=True)
		_record_primary_site(bench, self.lab, "secret-one")
		frappe.db.commit()

		stop_bench(bench.name)
		self.assertEqual(frappe.db.get_value("Bench Site", {"bench": bench.name}, "status"), "Inactive")

		bench.reload()
		_record_primary_site(bench, self.lab, "secret-one")

		self.assertEqual(frappe.db.get_value("Bench Site", {"bench": bench.name}, "status"), "Active")

	@patch("benchpress.mariadb_manager.drop_site_database")
	def test_teardown_drops_only_the_name_the_site_was_created_under(self, mock_drop):
		"""Editing the instance domain must not add a second candidate name for teardown to drop."""
		from benchpress.api import _drop_bench_site_databases
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench()
		# The database is created under the bare site_name (deploy passes `bench.site_name`).
		frappe.db.set_value("Bench Instance", bench.name, "domain", "example.com")
		_record_primary_site(bench, self.lab, "secret-one")

		bench.database_server = "db-any"
		_drop_bench_site_databases(bench)

		dropped = {call.args[1] for call in mock_drop.call_args_list}
		self.assertEqual(dropped, {bench.site_name})
		self.assertNotIn(f"{bench.site_name}.example.com", dropped)

	def test_teardown_removes_the_instance_route_file(self):
		"""Freed container IPs get reused by Docker — a stale route file left after teardown
		would keep pointing the old public hostname at whoever gets that IP next. See
		phase-3-teardown-cleanup.md."""
		from benchpress import deploy_manager
		from benchpress.deploy_manager import teardown_bench

		bench = self._bench()

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				ingress.publish(bench.name, "benchpress.cloud")
				route_file = Path(tmp) / "instances" / f"{bench.name}.yml"
				self.assertTrue(route_file.exists())

				teardown_bench(bench)

				self.assertFalse(route_file.exists())

	def test_teardown_keeps_the_wildcard_anchor(self):
		"""The anchor outlives every bench — it is what keeps the certificate renewing,
		so a reaper that tidies it away would silently stop renewal."""
		from benchpress import deploy_manager
		from benchpress.deploy_manager import teardown_bench

		bench = self._bench()

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				ingress.ensure_anchor("benchpress.cloud")
				ingress.publish(bench.name, "benchpress.cloud")
				anchor = Path(tmp) / "instances" / "wildcard-anchor.yml"

				teardown_bench(bench)

				self.assertFalse((Path(tmp) / "instances" / f"{bench.name}.yml").exists())
				self.assertTrue(anchor.exists())

	def test_teardown_does_not_raise_when_no_route_file_exists(self):
		"""The `base_domain = localhost` case: phase 1 never wrote a route file, so teardown
		must no-op cleanly rather than raising on a missing path."""
		from benchpress import deploy_manager
		from benchpress.deploy_manager import teardown_bench

		bench = self._bench()

		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				teardown_bench(bench)
