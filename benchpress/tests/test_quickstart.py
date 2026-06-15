# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.bench_instance import get_instance_id

TEST_LAB_ID = "test-lab-quickstart"
TEST_ADMIN_PASSWORD = "quickstart-secret-123"


def _running_deploy(bench_name):
	"""Stand-in for deploy_bench: mark the bench Running without touching Docker."""
	bench = frappe.get_doc("Bench Instance", bench_name)
	bench.status = "Running"
	bench.container_id = "fake-container"
	bench.container_ip = "172.18.0.9"
	bench.save(ignore_permissions=True)
	frappe.db.commit()


class TestQuickstart(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		# A pre-built Lab so _ensure_image short-circuits (no real image build).
		if not frappe.db.exists("Lab", TEST_LAB_ID):
			frappe.get_doc(
				{
					"doctype": "Lab",
					"lab_id": TEST_LAB_ID,
					"title": "Test Lab (Quickstart)",
					"frappe_version": "version-15",
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Lab", TEST_LAB_ID, "status", "Ready")
		frappe.db.set_value("Lab", TEST_LAB_ID, "image_tag", "benchpress/test-lab-quickstart:latest")
		frappe.db.commit()

		# Stash the live Settings presets so we can restore them after the run.
		# set_single_value bypasses the singleton's mandatory base_domain, which is
		# unset in a fresh test DB.
		cls._orig_default_lab = frappe.db.get_single_value("BenchPress Settings", "default_lab")
		cls._orig_admin_password = frappe.db.get_single_value("BenchPress Settings", "default_admin_password")
		frappe.db.set_single_value("BenchPress Settings", "default_lab", TEST_LAB_ID)
		frappe.db.set_single_value("BenchPress Settings", "default_admin_password", TEST_ADMIN_PASSWORD)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")

		frappe.db.set_single_value("BenchPress Settings", "default_lab", cls._orig_default_lab)
		frappe.db.set_single_value("BenchPress Settings", "default_admin_password", cls._orig_admin_password)

		bench_name = get_instance_id("Administrator", TEST_LAB_ID)
		if frappe.db.exists("Bench Instance", bench_name):
			frappe.delete_doc("Bench Instance", bench_name, force=True, ignore_permissions=True)
		if frappe.db.exists("Lab", TEST_LAB_ID):
			frappe.delete_doc("Lab", TEST_LAB_ID, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _clear_bench(self):
		bench_name = get_instance_id("Administrator", TEST_LAB_ID)
		if frappe.db.exists("Bench Instance", bench_name):
			frappe.delete_doc("Bench Instance", bench_name, force=True, ignore_permissions=True)
			frappe.db.commit()
		return bench_name

	@patch("benchpress.docker_manager.exec_in_container", return_value=(0, ""))
	@patch("benchpress.quickstart.build_lab")
	@patch("benchpress.quickstart.deploy_bench", side_effect=_running_deploy)
	def test_reads_presets_from_settings(self, mock_deploy, mock_build, mock_exec):
		from benchpress.quickstart import run_quickstart

		bench_name = self._clear_bench()
		run_quickstart()

		# The bench was created against the Settings-configured default Lab.
		self.assertTrue(frappe.db.exists("Bench Instance", bench_name))
		bench = frappe.get_doc("Bench Instance", bench_name)
		self.assertEqual(bench.lab, TEST_LAB_ID)
		# A cached Ready image means no build was triggered.
		mock_build.assert_not_called()
		mock_deploy.assert_called_once_with(bench_name)

	@patch("benchpress.docker_manager.exec_in_container", return_value=(0, ""))
	@patch("benchpress.quickstart.build_lab")
	@patch("benchpress.quickstart.deploy_bench", side_effect=_running_deploy)
	def test_admin_password_is_preset_not_random(self, mock_deploy, mock_build, mock_exec):
		from benchpress.quickstart import run_quickstart

		bench_name = self._clear_bench()
		run_quickstart()

		bench = frappe.get_doc("Bench Instance", bench_name)
		self.assertEqual(bench.get_password("admin_password"), TEST_ADMIN_PASSWORD)

	@patch("benchpress.docker_manager.exec_in_container", return_value=(0, ""))
	@patch("benchpress.quickstart.build_lab")
	@patch("benchpress.quickstart.deploy_bench", side_effect=_running_deploy)
	def test_second_run_is_idempotent_reprint(self, mock_deploy, mock_build, mock_exec):
		from benchpress.quickstart import run_quickstart

		self._clear_bench()
		run_quickstart()  # first run deploys
		run_quickstart()  # second run should reprint the banner, not redeploy

		# deploy_bench ran exactly once across both invocations.
		mock_deploy.assert_called_once()
