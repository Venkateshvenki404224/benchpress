# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id

# Generous ceilings (ms) meant to catch N+1 / accidental-blocking regressions,
# not micro-benchmarks. Every endpoint below runs with its side effects mocked.
BUDGETS_MS = {
	"get_labs": 500,
	"get_lab": 300,
	"get_lab_templates": 200,
	"get_user_context": 250,
	"get_benches": 600,
	"list_devices": 500,
	"create_lab_from_template": 300,
	"build_lab_image": 300,
	"create_bench": 1500,
	"create_site": 1500,
	"bench_action": 800,
	"get_deploy_logs": 400,
	"add_device": 400,
	"remove_device": 400,
	"get_device_wg_config": 400,
	"get_code_server_credentials": 400,
	"restart_code_server": 500,
	"enqueue_deploy": 400,
	"enqueue_redeploy": 400,
	"enqueue_stop": 500,
	"enqueue_start": 500,
	"get_overview": 1200,
	"get_vpn_status": 400,
}

# The five rows benchpress.diagnostics always returns; the real checks talk to
# Docker and MariaDB, so the Overview timing test never runs them.
DIAGNOSTICS_ROWS = [
	{"check": "docker_socket", "status": "pass", "hint": "Docker daemon reachable"},
	{"check": "docker_network", "status": "pass", "hint": "benchpress network exists"},
	{"check": "mariadb", "status": "pass", "hint": "MariaDB responding"},
	{"check": "redis", "status": "fail", "hint": "benchpress-redis container not found"},
	{"check": "vpn_server", "status": "pass", "hint": "WireGuard server 'wg0' configured"},
]


def _timed(function):
	start = time.perf_counter()
	result = function()
	elapsed_ms = (time.perf_counter() - start) * 1000
	return result, elapsed_ms


def _lab_app():
	return {
		"app_name": "frappe",
		"app_label": "Frappe",
		"git_url": "https://github.com/frappe/frappe",
		"branch": "version-15",
	}


def _ensure_lab(lab_id, **extra):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"API Timing {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
			**extra,
		}
	).insert(ignore_permissions=True)


def _ensure_bench(lab, **extra):
	name = get_instance_id("Administrator", lab.name)
	if frappe.db.exists("Bench Instance", name):
		frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "Bench Instance",
			"lab": lab.name,
			"frappe_version": lab.frappe_version,
			**extra,
		}
	).insert(ignore_permissions=True)


class TestApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _ensure_lab("api-timing-lab", apps=[_lab_app()])
		cls.bench = _ensure_bench(
			cls.lab,
			status="Running",
			container_id="ci-container",
			code_server_url="http://localhost:8443",
			code_server_password="cs-secret",
		)
		cls.action_lab = _ensure_lab("api-timing-action-lab")
		cls.action_bench = _ensure_bench(cls.action_lab, status="Stopped", container_id="ci-action")
		cls.create_lab = _ensure_lab("api-timing-create-lab", apps=[_lab_app()])
		cls.deploy_log = frappe.get_doc(
			{
				"doctype": "Deploy Log",
				"bench": cls.bench.name,
				"log_type": "info",
				"message": "fixture log line",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Deploy Log", cls.deploy_log.name, force=True, ignore_permissions=True)
		for lab in (cls.lab, cls.action_lab, cls.create_lab):
			bench_name = get_instance_id("Administrator", lab.name)
			if frappe.db.exists("Bench Instance", bench_name):
				frappe.delete_doc("Bench Instance", bench_name, force=True, ignore_permissions=True)
			frappe.delete_doc("Lab", lab.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")

	def assert_within_budget(self, endpoint, elapsed_ms):
		self.assertLess(
			elapsed_ms,
			BUDGETS_MS[endpoint],
			f"{endpoint} took {elapsed_ms:.0f}ms, budget is {BUDGETS_MS[endpoint]}ms",
		)

	# --- Read / contract endpoints (no mocks needed) -------------------------

	def test_get_labs_shape_and_timing(self):
		labs, elapsed_ms = _timed(api.get_labs)
		self.assertIsInstance(labs, list)
		for lab in labs:
			self.assertIn("app_names", lab)
			self.assertIn("app_count", lab)
			self.assertIn("bench_count", lab)
		self.assert_within_budget("get_labs", elapsed_ms)

	def test_get_lab_shape_and_timing(self):
		lab, elapsed_ms = _timed(lambda: api.get_lab(self.lab.name))
		self.assertEqual(lab["name"], self.lab.name)
		self.assertIsInstance(lab["apps"], list)
		self.assert_within_budget("get_lab", elapsed_ms)

	def test_get_lab_templates_shape_and_timing(self):
		templates, elapsed_ms = _timed(api.get_lab_templates)
		self.assertIsInstance(templates, list)
		for template in templates:
			self.assertIn("key", template)
			self.assertIn("title", template)
		self.assert_within_budget("get_lab_templates", elapsed_ms)

	def test_get_user_context_shape_and_timing(self):
		context, elapsed_ms = _timed(api.get_user_context)
		for key in ("is_admin", "user", "roles"):
			self.assertIn(key, context)
		self.assert_within_budget("get_user_context", elapsed_ms)

	def test_get_benches_shape_and_timing(self):
		benches, elapsed_ms = _timed(api.get_benches)
		self.assertIsInstance(benches, list)
		for bench in benches:
			for key in ("app_count", "site_count", "ssh_username"):
				self.assertIn(key, bench)
			# Secrets moved to get_bench_credentials (issue #91).
			for key in ("ssh_password", "admin_password", "code_server_password"):
				self.assertNotIn(key, bench)
		self.assert_within_budget("get_benches", elapsed_ms)

	def test_list_devices_shape_and_timing(self):
		devices, elapsed_ms = _timed(api.list_devices)
		self.assertIsInstance(devices, list)
		self.assert_within_budget("list_devices", elapsed_ms)

	def test_get_deploy_logs_shape_and_timing(self):
		logs, elapsed_ms = _timed(lambda: api.get_deploy_logs(self.bench.name))
		self.assertIsInstance(logs, list)
		self.assertGreaterEqual(len(logs), 1)
		for key in ("name", "message", "log_type", "timestamp"):
			self.assertIn(key, logs[0])
		self.assert_within_budget("get_deploy_logs", elapsed_ms)

	def test_get_overview_shape_and_timing(self):
		with patch("benchpress.diagnostics.run_diagnostics", return_value=DIAGNOSTICS_ROWS):
			overview, elapsed_ms = _timed(api.get_overview)

		for key in ("is_admin", "first_name", "counts", "deploy_time", "environments", "activity"):
			self.assertIn(key, overview)
		for key in ("total", "running", "stopped", "needs_attention"):
			self.assertIn(key, overview["counts"])
		self.assertEqual(overview["counts"]["total"], overview["environment_count"])
		self.assertIn(self.bench.name, [row["name"] for row in overview["environments"]])
		self.assert_within_budget("get_overview", elapsed_ms)

	def test_get_overview_deploy_time_states_its_window(self):
		with patch("benchpress.diagnostics.run_diagnostics", return_value=DIAGNOSTICS_ROWS):
			deploy_time = api.get_overview()["deploy_time"]

		# The caption may never outrun log retention (hooks.py: 7 days).
		self.assertEqual(deploy_time["window_days"], 7)
		self.assertIn("sample_size", deploy_time)
		self.assertIn("average_label", deploy_time)

	def test_get_overview_ignores_logs_older_than_retention(self):
		# Log clearing only runs when the scheduler does, so rows past the
		# horizon can still be in the table — the window is enforced in the query.
		window_start = frappe.utils.add_days(frappe.utils.now_datetime(), -7)
		stale = frappe.get_doc(
			{
				"doctype": "Deploy Log",
				"bench": self.bench.name,
				"log_type": "success",
				"message": "run from a month ago",
				"timestamp": frappe.utils.add_days(frappe.utils.now_datetime(), -30),
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Deploy Log", stale.name, force=True, ignore_permissions=True)

		with patch("benchpress.diagnostics.run_diagnostics", return_value=DIAGNOSTICS_ROWS):
			overview = api.get_overview()

		for event in overview["activity"]:
			self.assertGreaterEqual(frappe.utils.get_datetime(event["timestamp"]), window_start)
		average = overview["deploy_time"]["average_seconds"]
		self.assertTrue(average is None or average < 86400, f"stale run leaked into the average: {average}")

	def test_get_overview_infrastructure_is_the_real_diagnostics(self):
		with patch("benchpress.diagnostics.run_diagnostics", return_value=DIAGNOSTICS_ROWS):
			infrastructure = api.get_overview()["infrastructure"]

		self.assertEqual([row["check"] for row in infrastructure], [r["check"] for r in DIAGNOSTICS_ROWS])
		self.assertEqual(infrastructure[0]["status"], "Active")
		self.assertEqual(infrastructure[3]["status"], "Error")
		self.assertEqual(infrastructure[2]["label"], "MariaDB")

	def test_get_vpn_status_shape_and_timing(self):
		status, elapsed_ms = _timed(api.get_vpn_status)
		for key in ("connected", "last_handshake", "peer_count", "stale_after_seconds"):
			self.assertIn(key, status)
		self.assertIsInstance(status["connected"], bool)
		# One status poll interval, never a second threshold of our own.
		self.assertEqual(status["stale_after_seconds"] % 60, 0)
		self.assert_within_budget("get_vpn_status", elapsed_ms)

	def test_get_code_server_credentials_shape_and_timing(self):
		creds, elapsed_ms = _timed(lambda: api.get_code_server_credentials(self.bench.name))
		self.assertEqual(creds["url"], "http://localhost:8443")
		self.assertEqual(creds["password"], "cs-secret")
		self.assert_within_budget("get_code_server_credentials", elapsed_ms)

	# --- Enqueue endpoints (patch frappe.enqueue, assert contract) -----------

	def test_create_lab_from_template_contract_and_timing(self):
		with patch("benchpress.lab_templates.create_lab_from_template", return_value="LAB-fixture") as create:
			result, elapsed_ms = _timed(lambda: api.create_lab_from_template("frappe", "cli-1"))
		create.assert_called_once()
		self.assertEqual(result, {"name": "LAB-fixture", "status": "Draft"})
		self.assert_within_budget("create_lab_from_template", elapsed_ms)

	def test_build_lab_image_contract_and_timing(self):
		with patch("frappe.enqueue") as enqueue:
			result, elapsed_ms = _timed(lambda: api.build_lab_image(self.lab.name))
		enqueue.assert_called_once()
		self.assertEqual(result, {"name": self.lab.name, "status": "Building"})
		self.assert_within_budget("build_lab_image", elapsed_ms)

	def test_create_bench_contract_and_timing(self):
		data = frappe.as_json({"lab": self.create_lab.name, "bench_name": "cli-bench"})
		with patch("frappe.enqueue") as enqueue:
			result, elapsed_ms = _timed(lambda: api.create_bench(data))
		self.addCleanup(
			frappe.delete_doc, "Bench Instance", result["name"], force=True, ignore_permissions=True
		)
		enqueue.assert_called_once()
		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
		self.assertEqual(result["status"], "Deploying")
		self.assertTrue(frappe.db.exists("Bench Instance", result["name"]))
		self.assert_within_budget("create_bench", elapsed_ms)

	def test_create_site_contract_and_timing(self):
		data = frappe.as_json({"bench": self.bench.name, "site_name": "cli-site", "apps": []})
		with patch("frappe.enqueue") as enqueue:
			result, elapsed_ms = _timed(lambda: api.create_site(data))
		self.addCleanup(frappe.delete_doc, "Bench Site", result["name"], force=True, ignore_permissions=True)
		enqueue.assert_called_once()
		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
		self.assertEqual(result["status"], "Creating")
		self.assert_within_budget("create_site", elapsed_ms)

	# --- Docker / manager side effects (patch module functions) --------------

	def test_bench_action_start_stop_restart_and_timing(self):
		with (
			patch("benchpress.docker_manager.start_container"),
			patch("benchpress.docker_manager.stop_container"),
			patch("benchpress.docker_manager.restart_container"),
			patch("benchpress.docker_manager.remove_container"),
		):
			for action, expected in (("start", "Running"), ("stop", "Stopped"), ("restart", "Running")):
				result, elapsed_ms = _timed(lambda: api.bench_action(self.action_bench.name, action))
				self.assertEqual(result["name"], self.action_bench.name)
				self.assertEqual(result["status"], expected)
				self.assert_within_budget("bench_action", elapsed_ms)

	def test_restart_code_server_contract_and_timing(self):
		with patch("benchpress.docker_manager.exec_in_container", return_value=(0, "ok")):
			result, elapsed_ms = _timed(lambda: api.restart_code_server(self.bench.name))
		self.assertEqual(result, {"ok": True})
		self.assert_within_budget("restart_code_server", elapsed_ms)

	# --- Device endpoints (patch benchpress.vpn_adapter.*) -------------------

	def test_add_device_contract_and_timing(self):
		fake = {"name": "dev-1", "wg_ip": "172.27.0.9", "wg_config": "[Interface]"}
		with patch("benchpress.vpn_adapter.register_device", return_value=fake) as register:
			result, elapsed_ms = _timed(lambda: api.add_device("Laptop", "Laptop"))
		register.assert_called_once()
		self.assertEqual(result, fake)
		self.assert_within_budget("add_device", elapsed_ms)

	def test_remove_device_contract_and_timing(self):
		with patch("benchpress.vpn_adapter.unregister_device", return_value=True) as unregister:
			result, elapsed_ms = _timed(lambda: api.remove_device("dev-1"))
		unregister.assert_called_once()
		self.assertEqual(result, {"status": "removed"})
		self.assert_within_budget("remove_device", elapsed_ms)

	def test_get_device_wg_config_contract_and_timing(self):
		with patch("benchpress.vpn_adapter.get_device_config", return_value="[Interface]\n") as config:
			result, elapsed_ms = _timed(lambda: api.get_device_wg_config("dev-1"))
		config.assert_called_once()
		self.assertIsInstance(result, str)
		self.assert_within_budget("get_device_wg_config", elapsed_ms)

	# --- Bench Instance controller methods -----------------------------------

	def test_enqueue_deploy_calls_job_and_timing(self):
		bench = frappe.get_doc("Bench Instance", self.bench.name)
		with patch("frappe.enqueue") as enqueue:
			_, elapsed_ms = _timed(bench.enqueue_deploy)
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.args[0], "benchpress.deploy_manager.deploy_bench")
		self.assert_within_budget("enqueue_deploy", elapsed_ms)

	def test_enqueue_redeploy_calls_job_and_timing(self):
		bench = frappe.get_doc("Bench Instance", self.bench.name)
		with patch("frappe.enqueue") as enqueue:
			_, elapsed_ms = _timed(bench.enqueue_redeploy)
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.args[0], "benchpress.deploy_manager.redeploy_bench")
		self.assert_within_budget("enqueue_redeploy", elapsed_ms)

	def test_enqueue_stop_calls_stop_bench_and_timing(self):
		bench = frappe.get_doc("Bench Instance", self.bench.name)
		with patch("benchpress.deploy_manager.stop_bench") as stop_bench:
			_, elapsed_ms = _timed(bench.enqueue_stop)
		stop_bench.assert_called_once_with(bench.name)
		self.assert_within_budget("enqueue_stop", elapsed_ms)

	def test_enqueue_start_starts_container_and_timing(self):
		bench = frappe.get_doc("Bench Instance", self.bench.name)
		with patch("benchpress.docker_manager.start_container") as start_container:
			_, elapsed_ms = _timed(bench.enqueue_start)
		start_container.assert_called_once_with(bench.container_id)
		self.assertEqual(bench.status, "Running")
		self.assert_within_budget("enqueue_start", elapsed_ms)
