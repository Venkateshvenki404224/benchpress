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
		frappe.set_user("Administrator")
		existing = get_instance_id("Administrator", self.lab.name)
		if frappe.db.exists("Bench Instance", existing):
			frappe.delete_doc("Bench Instance", existing, force=True, ignore_permissions=True)
			frappe.db.commit()
		bench = _make_bench(self.lab.name)
		self.addCleanup(
			lambda n=bench.name: frappe.delete_doc("Bench Instance", n, force=True, ignore_permissions=True)
			if frappe.db.exists("Bench Instance", n)
			else None
		)
		self.addCleanup(frappe.db.commit)
		return bench

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

	@patch("benchpress.deploy_manager.deploy_bench")
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

	@patch("benchpress.deploy_manager.deploy_bench")
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

	@patch("benchpress.deploy_manager.deploy_bench")
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

	# --- apply_public_visibility ---

	def _deployed_bench(self):
		bench = self._fresh_bench()
		frappe.db.set_value("Bench Instance", bench.name, "database_server", self.db_server_name)
		frappe.db.set_value("Bench Instance", bench.name, "container_id", "old-container")
		frappe.db.commit()
		bench.reload()
		return bench

	@patch("benchpress.deploy_manager.time.sleep")
	@patch("benchpress.deploy_manager._provision_running_container")
	@patch("benchpress.deploy_manager.start_container")
	@patch("benchpress.deploy_manager.create_bench_container")
	@patch("benchpress.deploy_manager._remove_stale_container")
	def test_apply_public_visibility_private_generates_creds(
		self, mock_rm, mock_create, mock_start, mock_prov, mock_sleep
	):
		from benchpress.deploy_manager import apply_public_visibility

		mock_create.return_value = "new-container"
		bench = self._deployed_bench()

		apply_public_visibility(bench.name, is_public=False)

		bench.reload()
		self.assertEqual(bench.is_public, 0)
		self.assertEqual(bench.public_username, "lab")
		self.assertTrue(bench.get_password("public_password"))
		self.assertEqual(bench.status, "Running")
		self.assertEqual(bench.container_id, "new-container")
		mock_rm.assert_called_once()
		mock_prov.assert_called_once()

	@patch("benchpress.deploy_manager.time.sleep")
	@patch("benchpress.deploy_manager._provision_running_container")
	@patch("benchpress.deploy_manager.start_container")
	@patch("benchpress.deploy_manager.create_bench_container")
	@patch("benchpress.deploy_manager._remove_stale_container")
	def test_apply_public_visibility_public_recreates_container(
		self, mock_rm, mock_create, mock_start, mock_prov, mock_sleep
	):
		from benchpress.deploy_manager import apply_public_visibility

		mock_create.return_value = "new-container"
		bench = self._deployed_bench()

		apply_public_visibility(bench.name, is_public=True)

		bench.reload()
		self.assertEqual(bench.is_public, 1)
		self.assertEqual(bench.status, "Running")
		mock_create.assert_called_once()
