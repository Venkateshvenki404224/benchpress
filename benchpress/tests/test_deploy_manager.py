# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.bench_instance import get_instance_id


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


def _fresh_bench(case, lab_name):
	frappe.set_user("Administrator")
	existing = get_instance_id("Administrator", lab_name)
	if frappe.db.exists("Bench Instance", existing):
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
	case.addCleanup(frappe.db.commit)
	return bench


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


class TestDeployManager(IntegrationTestCase):
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

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	@patch("benchpress.deploy_manager.stop_container")
	@patch("benchpress.docker_manager.get_client")
	def test_redeploy_bench_resets_status_to_draft_before_deploy(
		self, mock_client, mock_stop, mock_remove, mock_deploy
	):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		bench.container_id = "old-container"
		bench.status = "Running"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		mock_client.return_value.volumes.get.return_value = MagicMock()

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
	@patch("benchpress.docker_manager.get_client")
	def test_redeploy_bench_removes_data_volume(self, mock_client, mock_stop, mock_remove, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		bench.container_id = "old-container"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		mock_vol = MagicMock()
		mock_client.return_value.volumes.get.return_value = mock_vol

		redeploy_bench(bench.name)

		mock_client.return_value.volumes.get.assert_called_with(f"benchpress-{bench.bench_name}-data")
		mock_vol.remove.assert_called_once_with(force=True)

	@patch("benchpress.deploy_manager._deploy_bench")
	@patch("benchpress.deploy_manager.remove_container")
	@patch("benchpress.deploy_manager.stop_container")
	@patch("benchpress.docker_manager.get_client")
	@patch("benchpress.mariadb_manager.drop_site_database")
	def test_redeploy_bench_drops_site_database(
		self, mock_drop_db, mock_client, mock_stop, mock_remove, mock_deploy
	):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		frappe.db.set_value("Bench Instance", bench.name, "container_id", "old-container")
		frappe.db.set_value("Bench Instance", bench.name, "database_server", self.db_server_name)
		frappe.db.commit()
		bench.reload()

		mock_client.return_value.volumes.get.return_value = MagicMock()

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
	@patch("benchpress.deploy_manager.remove_bench_volume")
	def test_redeploy_skipped_when_lock_held(self, mock_volume, mock_deploy):
		from benchpress.deploy_manager import redeploy_bench

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)

		with self._held_deploy_lock(bench.name):
			redeploy_bench(bench.name)

		mock_volume.assert_not_called()
		mock_deploy.assert_not_called()

	def test_deploy_failure_after_container_creation_cleans_up(self):
		from benchpress import deploy_manager

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": "benchpress/test:latest"})
		frappe.db.set_value(
			"Bench Instance",
			bench.name,
			{"container_ip": "172.30.0.50", "wg_ip": "10.8.0.20"},
		)
		frappe.db.commit()

		with (
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			patch.object(deploy_manager, "start_container", autospec=True),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			patch.object(deploy_manager, "remove_container", autospec=True) as mock_remove_container,
			patch.object(deploy_manager, "remove_bench_volume", autospec=True) as mock_remove_volume,
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			patch("benchpress.vpn_adapter.remove_bench_peer", autospec=True) as mock_remove_peer,
		):
			mock_infra.return_value = self.db_server_name
			mock_create.return_value = "cid-cleanup"
			mock_wait.side_effect = Exception("container did not report running")

			deploy_manager.deploy_bench(bench.name)

		mock_remove_container.assert_called_once_with("cid-cleanup")
		mock_remove_peer.assert_called_once()
		mock_remove_volume.assert_not_called()
		bench.reload()
		self.assertEqual(bench.status, "Error")
		self.assertIsNone(bench.container_id)
		self.assertIsNone(bench.container_ip)
		self.assertIsNone(bench.wg_ip)

	def test_deploy_failure_before_container_skips_cleanup(self):
		from benchpress import deploy_manager

		bench = self._fresh_bench()
		self._cleanup_deploy_logs(bench.name)
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": "benchpress/test:latest"})
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
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "remove_container", autospec=True) as mock_remove_container,
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			patch("benchpress.vpn_adapter.remove_bench_peer", autospec=True) as mock_remove_peer,
		):
			mock_infra.side_effect = Exception("infrastructure unavailable")

			deploy_manager.deploy_bench(bench.name)

		mock_remove_container.assert_not_called()
		mock_remove_peer.assert_not_called()
		bench.reload()
		self.assertEqual(bench.status, "Error")
		self.assertEqual(bench.container_id, "old-container")
		self.assertEqual(bench.container_ip, "172.30.0.50")
		self.assertEqual(bench.wg_ip, "10.8.0.20")

	# --- LogStream batching (deploy-pipeline-performance phase 1) ---

	def _new_deploy_log(self, bench_name):
		"""An empty Deploy Log, cleaned up the way the rest of this file does it."""
		self._cleanup_deploy_logs(bench_name)
		log = frappe.get_doc(
			{
				"doctype": "Deploy Log",
				"bench": bench_name,
				"log_type": "info",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
		return log.name

	def _log_stream(self, log_name, bench_name, flush_every=50):
		"""LogStream with the elapsed-time trigger pinned far out of reach, so
		write-count assertions measure the line-count and terminal triggers only.
		"""
		from benchpress.deploy_manager import LogStream

		stream = LogStream(
			"Deploy Log",
			log_name,
			"bench_deploy_log",
			{"bench": bench_name, "deploy_log": log_name},
			flush_every=flush_every,
		)
		stream.FLUSH_INTERVAL = 3600
		return stream

	@patch("frappe.publish_realtime")
	def test_log_stream_batches_writes(self, mock_publish):
		"""The O(n²) regression guard: assert the write count AND the content.

		Either assertion alone passes for a broken writer — a no-op writer hits
		the count, and the old read-modify-write appender hits the content.
		"""
		bench = self._fresh_bench()
		log_name = self._new_deploy_log(bench.name)
		# A NULL message exercises the Coalesce in flush(): CONCAT(NULL, x) is NULL.
		frappe.db.set_value("Deploy Log", log_name, "message", None, update_modified=False)
		frappe.db.commit()
		stream = self._log_stream(log_name, bench.name)

		with patch.object(stream, "flush", wraps=stream.flush) as flush_spy:
			for index in range(200):
				stream(f"line {index}")

		self.assertEqual(flush_spy.call_count, 4)  # 200 lines at flush_every=50
		message = frappe.db.get_value("Deploy Log", log_name, "message")
		self.assertEqual(message.splitlines(), [f"line {index}" for index in range(200)])
		# The realtime contract is unchanged: still one event per line, batching or not.
		# Count only our event — frappe.db.commit() publishes its own events too.
		line_events = [c for c in mock_publish.call_args_list if c.kwargs.get("event") == "bench_deploy_log"]
		self.assertEqual(len(line_events), 200)

	@patch("frappe.publish_realtime")
	def test_log_stream_flushes_on_terminal_type(self, mock_publish):
		bench = self._fresh_bench()
		log_name = self._new_deploy_log(bench.name)
		stream = self._log_stream(log_name, bench.name)

		for index in range(3):
			stream(f"line {index}")
		self.assertFalse(frappe.db.get_value("Deploy Log", log_name, "message"))

		stream("=== Deploy complete ===", "success")

		message = frappe.db.get_value("Deploy Log", log_name, "message")
		self.assertEqual(message.splitlines(), ["line 0", "line 1", "line 2", "=== Deploy complete ==="])

	@patch("frappe.publish_realtime")
	def test_log_stream_flushes_stale_buffer(self, mock_publish):
		"""A SIGTERM'd or timed-out build keeps everything but the last seconds."""
		bench = self._fresh_bench()
		log_name = self._new_deploy_log(bench.name)
		stream = self._log_stream(log_name, bench.name)
		stream.FLUSH_INTERVAL = 0  # every buffer counts as stale

		stream("line 0")

		self.assertEqual(frappe.db.get_value("Deploy Log", log_name, "message"), "line 0\n")

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
	@patch("frappe.enqueue", return_value=None)
	def test_deduped_enqueue_messages_user(self, mock_enqueue, mock_msgprint):
		bench = self._fresh_bench()

		bench.enqueue_deploy()
		bench.enqueue_redeploy()

		for call in mock_msgprint.call_args_list:
			self.assertIn("already in progress", str(call.args[0]))

	# --- _create_site_on_bench (add-site path) ---

	def _make_bench_site(self, bench):
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"site_name": "arity-test-site",
				"bench": bench.name,
				"status": "Creating",
				"apps_installed": [{"app_name": "benchpress", "app_label": "BenchPress"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
		self.addCleanup(
			lambda n=site.name: (
				frappe.delete_doc("Bench Site", n, force=True, ignore_permissions=True)
				if frappe.db.exists("Bench Site", n)
				else None
			)
		)
		return site

	@patch("benchpress.deploy_manager.create_site_in_container", autospec=True)
	def test_create_site_on_bench_matches_signature_and_activates_site(self, mock_create):
		from benchpress.api import _create_site_on_bench

		bench = self._fresh_bench()
		bench.database_server = self.db_server_name
		bench.container_id = "container-arity-test"
		bench.admin_password = "test-admin-pw"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		site = self._make_bench_site(bench)
		# autospec enforces the real 5-arg signature: a stale 6-arg call raises
		# TypeError inside the except block, which would leave status = Error.
		mock_create.return_value = (0, "site created")

		_create_site_on_bench(site.name)

		site.reload()
		self.assertEqual(site.status, "Active")
		mock_create.assert_called_once()
		args = mock_create.call_args.args
		self.assertEqual(args[0], "container-arity-test")
		self.assertEqual(args[2], "arity-test-site")
		self.assertEqual(args[4], "benchpress")

	# --- build_linkuser_args (Lab.shell wiring) ---

	def test_build_linkuser_args_includes_lab_shell(self):
		from benchpress.deploy_manager import build_linkuser_args

		bench = self._fresh_bench()
		bench.ssh_username = "tester"
		self.lab.shell = "/bin/zsh"
		settings = frappe.get_single("BenchPress Settings")

		args = build_linkuser_args(bench, self.lab, settings, "secret-pw")

		# 8 args: mount_target was removed, so LOGIN_SHELL immediately follows BASE_DOMAIN.
		self.assertEqual(len(args), 8)
		self.assertEqual(args[4], "secret-pw")  # SSH_PASSWORD position
		self.assertEqual(args[6], settings.base_domain or "localhost")  # BASE_DOMAIN position
		self.assertEqual(args[-1], "/bin/zsh")  # LOGIN_SHELL position (right after BASE_DOMAIN)

	def test_build_linkuser_args_defaults_shell_to_bash(self):
		from benchpress.deploy_manager import build_linkuser_args

		bench = self._fresh_bench()
		bench.ssh_username = "tester"
		self.lab.shell = None
		settings = frappe.get_single("BenchPress Settings")

		args = build_linkuser_args(bench, self.lab, settings, "pw")

		self.assertEqual(args[-1], "/bin/bash")


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
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": "benchpress/test:latest"})
		frappe.db.commit()

		with (
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			patch.object(deploy_manager, "start_container", autospec=True),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			patch.object(deploy_manager, "_setup_container_vpn", autospec=True),
			patch.object(deploy_manager, "write_file_to_container", autospec=True),
			patch.object(deploy_manager, "exec_in_container", autospec=True) as mock_exec,
			patch.object(deploy_manager, "create_site_in_container", autospec=True) as mock_site,
		):
			mock_infra.return_value = self.db_server_name
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
