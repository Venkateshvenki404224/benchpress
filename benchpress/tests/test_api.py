# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.data import get_datetime

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id

# Generous ceilings (ms) meant to catch N+1 / accidental-blocking regressions,
# not micro-benchmarks. Every endpoint below runs with its side effects mocked.
BUDGETS_MS = {
	"get_labs": 500,
	"get_lab": 300,
	"get_lab_templates": 200,
	"get_user_context": 250,
	"get_credit_summary": 250,
	"get_credit_statement": 400,
	"get_benches": 600,
	"list_devices": 500,
	"create_lab_from_template": 300,
	"build_lab_image": 300,
	"prewarm_catalog": 300,
	"create_bench": 1500,
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
	"get_device_types": 200,
	"run_connection_test": 800,
	"get_lab_form_options": 200,
	"get_build_history": 600,
	"get_deploy_history": 600,
}

# The seven rows benchpress.diagnostics always returns; the real checks talk to
# Docker and MariaDB, so the Overview timing test never runs them.
DIAGNOSTICS_ROWS = [
	{"check": "docker_socket", "status": "pass", "hint": "Docker daemon reachable"},
	{"check": "docker_network", "status": "pass", "hint": "benchpress network exists"},
	{"check": "mariadb", "status": "pass", "hint": "MariaDB responding"},
	{"check": "clock_skew", "status": "pass", "hint": "App and database clocks agree"},
	{"check": "redis", "status": "fail", "hint": "benchpress-redis container not found"},
	{"check": "container_runtimes", "status": "pass", "hint": "Docker has sysbox-runc registered"},
	{"check": "vpn_server", "status": "pass", "hint": "WireGuard server 'wg0' configured"},
]


# A real failed build tail: the pipeline brackets each step with `=== … ===`
# and ends the run with its own failure marker.
FAILED_BUILD_LOG = "\n".join(
	[
		"=== Build started ===",
		"Step 1/3 : FROM frappe/base:version-15",
		"=== Installing apps ===",
		"fatal: repository 'https://github.com/frappe/nope' not found",
		"=== Build failed: app install exited 128 ===",
		"Cleanup: removed the half-built image",
	]
)


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


def _count_queries(action) -> int:
	"""How many statements `action` sends to MariaDB.

	`assertQueryCount` asserts a ceiling, which cannot express "flat regardless
	of row count" — an absolute number would also be dominated by frappe's
	one-off DocType and permission meta loads and would pass or fail on test
	ordering. Counting twice and comparing does express it.
	"""
	count = 0
	original_sql = frappe.db.__class__.sql

	def counting_sql(*args, **kwargs):
		nonlocal count
		count += 1
		return original_sql(*args, **kwargs)

	frappe.db.__class__.sql = counting_sql
	try:
		action()
	finally:
		frappe.db.__class__.sql = original_sql
	return count


def _delete_labs(labs):
	frappe.set_user("Administrator")
	for lab in labs:
		frappe.delete_doc("Lab", lab.name, force=True, ignore_permissions=True)
	frappe.db.commit()


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
			container_health="Unhealthy",
			last_health_check=frappe.utils.now_datetime(),
			code_server_url="http://localhost:8443",
			code_server_password="cs-secret",
		)
		cls.failed_lab = _ensure_lab("api-timing-failed-lab", status="Error")
		cls.failed_build_log = frappe.get_doc(
			{
				"doctype": "Build Log",
				"lab": cls.failed_lab.name,
				"log_type": "error",
				"message": FAILED_BUILD_LOG,
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
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
		frappe.delete_doc("Build Log", cls.failed_build_log.name, force=True, ignore_permissions=True)
		for lab in (cls.lab, cls.action_lab, cls.create_lab, cls.failed_lab):
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
			for key in ("app_names", "app_count", "bench_count", "deployed_as", "last_run"):
				self.assertIn(key, lab)
		self.assert_within_budget("get_labs", elapsed_ms)

	def test_get_labs_reports_where_a_lab_is_deployed(self):
		row = self._lab_row(api.get_labs(), self.lab.name)
		self.assertEqual(row["deployed_as"]["bench"], self.bench.name)
		self.assertEqual(row["deployed_as"]["status"], "Running")
		self.assertEqual(row["bench_count"], 1)

	def test_get_labs_says_never_deployed_rather_than_leaving_a_blank(self):
		row = self._lab_row(api.get_labs(), self.create_lab.name)
		self.assertIsNone(row["deployed_as"])
		self.assertIsNone(row["last_run"])
		self.assertEqual(row["bench_count"], 0)

	def test_get_labs_last_run_is_the_newest_container_start(self):
		started = frappe.utils.now_datetime()
		frappe.db.set_value("Bench Instance", self.bench.name, "started_at", started)
		row = self._lab_row(api.get_labs(), self.lab.name)
		self.assertEqual(get_datetime(row["last_run"]), get_datetime(started))

	def test_get_labs_query_count_does_not_scale_with_lab_count(self):
		"""An N+1 regression fails here: four more labs must cost no more queries."""
		api.get_labs()  # warm the DocType meta and permission caches
		baseline = _count_queries(api.get_labs)

		extra = [_ensure_lab(f"api-timing-n1-{index}", apps=[_lab_app()]) for index in range(4)]
		self.addCleanup(_delete_labs, extra)
		frappe.db.commit()
		api.get_labs()

		grown = _count_queries(api.get_labs)
		self.assertEqual(
			grown,
			baseline,
			f"{len(extra)} more labs cost {grown - baseline} more queries — the N+1 is back",
		)
		self.assertGreaterEqual(len(api.get_labs()), len(extra) + 3)

	def _lab_row(self, labs, name):
		row = next((lab for lab in labs if lab["name"] == name), None)
		self.assertIsNotNone(row, f"{name} missing from get_labs")
		return row

	def test_get_lab_shape_and_timing(self):
		lab, elapsed_ms = _timed(lambda: api.get_lab(self.lab.name))
		self.assertEqual(lab["name"], self.lab.name)
		self.assertIsInstance(lab["apps"], list)
		for key in ("bench", "sites", "failure", "enable_ssh", "enable_code_server"):
			self.assertIn(key, lab)
		self.assert_within_budget("get_lab", elapsed_ms)

	def test_get_lab_carries_both_status_axes_of_the_bench(self):
		"""A Running bench can be Unhealthy — the card cannot draw one from the other."""
		bench = api.get_lab(self.lab.name)["bench"]

		self.assertEqual(bench["name"], self.bench.name)
		self.assertEqual(bench["status"], "Running")
		self.assertEqual(bench["container_health"], "Unhealthy")
		self.assertIsNotNone(bench["last_health_check"])

	def test_get_lab_reports_no_bench_for_an_undeployed_lab(self):
		lab = api.get_lab(self.create_lab.name)

		self.assertIsNone(lab["bench"])
		self.assertEqual(lab["sites"], [])

	def test_get_lab_names_the_failing_step_and_its_reason(self):
		failure = api.get_lab(self.failed_lab.name)["failure"]

		self.assertEqual(failure["source"], "build")
		self.assertEqual(failure["step"], "Installing apps")
		self.assertEqual(failure["reason"], "app install exited 128")
		self.assertEqual(failure["log"], self.failed_build_log.name)

	def test_get_lab_reports_no_failure_when_nothing_failed(self):
		self.assertIsNone(api.get_lab(self.lab.name)["failure"])

	def test_get_lab_templates_shape_and_timing(self):
		templates, elapsed_ms = _timed(api.get_lab_templates)
		self.assertIsInstance(templates, list)
		for template in templates:
			self.assertIn("key", template)
			self.assertIn("title", template)
		self.assert_within_budget("get_lab_templates", elapsed_ms)

	def test_get_user_context_shape_and_timing(self):
		context, elapsed_ms = _timed(api.get_user_context)
		for key in ("is_admin", "user", "roles", "credits"):
			self.assertIn(key, context)
		self.assert_within_budget("get_user_context", elapsed_ms)

	def test_get_user_context_carries_the_credit_gate(self):
		"""Every credit surface hides behind this flag, so it is part of the contract."""
		self.assertIn("enabled", api.get_user_context()["credits"])

	def test_get_credit_summary_shape_and_timing(self):
		summary, elapsed_ms = _timed(api.get_credit_summary)
		self.assertIn("enabled", summary)
		self.assert_within_budget("get_credit_summary", elapsed_ms)

	def test_get_credit_statement_shape_and_timing(self):
		statement, elapsed_ms = _timed(api.get_credit_statement)
		for key in ("enabled", "rows", "total", "summary"):
			self.assertIn(key, statement)
		self.assert_within_budget("get_credit_statement", elapsed_ms)

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

		by_check = {row["check"]: row for row in infrastructure}
		self.assertEqual([row["check"] for row in infrastructure], [r["check"] for r in DIAGNOSTICS_ROWS])
		self.assertEqual(by_check["docker_socket"]["status"], "Active")
		self.assertEqual(by_check["redis"]["status"], "Error")
		self.assertEqual(by_check["mariadb"]["label"], "MariaDB")
		self.assertEqual(by_check["clock_skew"]["label"], "Clock skew")

	def test_get_vpn_status_shape_and_timing(self):
		status, elapsed_ms = _timed(api.get_vpn_status)
		for key in ("connected", "last_handshake", "peer_count", "stale_after_seconds"):
			self.assertIn(key, status)
		self.assertIsInstance(status["connected"], bool)
		# One status poll interval, never a second threshold of our own.
		self.assertEqual(status["stale_after_seconds"] % 60, 0)
		self.assert_within_budget("get_vpn_status", elapsed_ms)

	def test_get_overview_activity_names_a_bench_readably(self):
		"""`bench_name` is an md5; activity is prose, so it uses the lab-derived label."""
		with patch("benchpress.diagnostics.run_diagnostics", return_value=DIAGNOSTICS_ROWS):
			activity = api.get_overview()["activity"]

		event = next(row for row in activity if row.get("bench") == self.bench.name)
		self.assertIn(f"bench-{self.lab.name}", event["message"])
		self.assertNotIn(self.bench.name, event["message"])

	def test_get_lab_form_options_comes_from_the_doctype(self):
		options, elapsed_ms = _timed(api.get_lab_form_options)
		versions = frappe.get_meta("Lab").get_field("frappe_version").options.split("\n")
		self.assertEqual(options["frappe_versions"], [v for v in versions if v])
		self.assertEqual(options["defaults"]["cpu_cores"], "1")
		self.assert_within_budget("get_lab_form_options", elapsed_ms)

	def test_get_build_history_shape_and_timing(self):
		history, elapsed_ms = _timed(api.get_build_history)
		self.assertEqual(history["window_days"], 7)
		row = next(row for row in history["rows"] if row["name"] == self.failed_build_log.name)
		for key in ("lab", "lab_title", "image_tag", "result", "last_step", "duration_label", "started"):
			self.assertIn(key, row)
		self.assertEqual(row["result"], "Failed")
		# The fixture log's last marker before its failure line.
		self.assertEqual(row["last_step"], "Installing apps")
		self.assert_within_budget("get_build_history", elapsed_ms)

	def test_get_deploy_history_shape_and_timing(self):
		history, elapsed_ms = _timed(api.get_deploy_history)
		row = next(row for row in history["rows"] if row["name"] == self.deploy_log.name)
		self.assertEqual(row["bench"], self.bench.name)
		self.assertEqual(row["lab"], self.lab.name)
		self.assertEqual(row["result"], "Deploying")
		self.assert_within_budget("get_deploy_history", elapsed_ms)

	def test_history_never_returns_the_log_bodies_it_parsed(self):
		"""A list of runs is not a list of logs — the messages stay on the server."""
		for history in (api.get_build_history(), api.get_deploy_history()):
			for row in history["rows"]:
				self.assertNotIn("message", row)

	def test_get_device_types_is_the_backend_list(self):
		from benchpress.vpn_adapter import DEVICE_TYPES

		types, elapsed_ms = _timed(api.get_device_types)
		self.assertEqual(types, DEVICE_TYPES)
		self.assert_within_budget("get_device_types", elapsed_ms)

	def test_run_connection_test_shape_and_timing(self):
		checks, elapsed_ms = _timed(api.run_connection_test)

		self.assertEqual(
			[check["check"] for check in checks],
			["vpn_server", "device_registered", "peer_active", "handshake"],
		)
		for check in checks:
			for key in ("check", "label", "status", "hint"):
				self.assertIn(key, check)
			self.assertIn(check["status"], ("Active", "Error"))
			# A boolean is not an answer — every row says what to do about it.
			self.assertTrue(check["hint"])
		self.assert_within_budget("run_connection_test", elapsed_ms)

	def test_run_connection_test_names_the_failing_step_without_a_device(self):
		with patch("benchpress.connection_test.list_devices", return_value=[]):
			checks = api.run_connection_test()

		by_check = {check["check"]: check for check in checks}
		self.assertEqual(by_check["device_registered"]["status"], "Error")
		self.assertIn("no device", by_check["device_registered"]["hint"])
		self.assertEqual(by_check["handshake"]["status"], "Error")

	def test_run_connection_test_passes_on_a_fresh_handshake(self):
		device = {
			"name": "PEER-CONN-1",
			"device_name": "Contract Laptop",
			"last_handshake": frappe.utils.now_datetime(),
		}
		peer_status = {
			"name": "PEER-CONN-1",
			"status": "Active",
			"assigned_ip": "172.27.0.9",
			"endpoint": "203.0.113.7:51820",
		}
		with (
			patch("benchpress.connection_test.list_devices", return_value=[device]),
			patch("benchpress.connection_test.get_device_peer_status", return_value=peer_status),
		):
			checks = api.run_connection_test()

		by_check = {check["check"]: check for check in checks}
		self.assertEqual(by_check["peer_active"]["status"], "Active")
		self.assertIn("172.27.0.9", by_check["peer_active"]["hint"])
		self.assertEqual(by_check["handshake"]["status"], "Active")

	def test_run_connection_test_explains_a_peer_that_never_connected(self):
		device = {"name": "PEER-CONN-2", "device_name": "New Phone", "last_handshake": None}
		with (
			patch("benchpress.connection_test.list_devices", return_value=[device]),
			patch(
				"benchpress.connection_test.get_device_peer_status",
				return_value={"status": "Pending", "assigned_ip": "172.27.0.10", "endpoint": None},
			),
		):
			checks = api.run_connection_test()

		by_check = {check["check"]: check for check in checks}
		self.assertEqual(by_check["peer_active"]["status"], "Error")
		self.assertIn("New Phone has never connected", by_check["peer_active"]["hint"])
		self.assertIn("never heard from New Phone", by_check["handshake"]["hint"])

	def test_get_code_server_credentials_shape_and_timing(self):
		creds, elapsed_ms = _timed(lambda: api.get_code_server_credentials(self.bench.name))
		self.assertEqual(creds["url"], "http://localhost:8443")
		self.assertEqual(creds["password"], "cs-secret")
		self.assert_within_budget("get_code_server_credentials", elapsed_ms)

	# The IDE button now calls this endpoint at the moment it is clicked, so its two
	# guards are what a user reads when the IDE cannot answer — not an assumption.
	def test_get_code_server_credentials_refuses_a_bench_that_is_not_running(self):
		with self.assertRaises(frappe.ValidationError):
			api.get_code_server_credentials(self.action_bench.name)

	def test_get_code_server_credentials_refuses_a_bench_with_no_address(self):
		# A failed code-server step clears the address, and this class rolls back
		# only once, so the fixture is put back for its siblings.
		self.addCleanup(self._restore_code_server_url, self.bench.code_server_url)
		self._set_code_server_url("")
		with self.assertRaises(frappe.ValidationError):
			api.get_code_server_credentials(self.bench.name)

	def _restore_code_server_url(self, url):
		self._set_code_server_url(url)

	def _set_code_server_url(self, url):
		frappe.db.set_value("Bench Instance", self.bench.name, "code_server_url", url)
		frappe.clear_document_cache("Bench Instance", self.bench.name)

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

	def test_prewarm_catalog_contract_and_timing(self):
		with patch("frappe.enqueue") as enqueue:
			result, elapsed_ms = _timed(api.prewarm_catalog)
		enqueue.assert_called_once()
		# `queue-short` has no Docker socket, so the pre-warm must be handed to `queue-long`.
		self.assertEqual(enqueue.call_args.kwargs["queue"], "long")
		self.assertEqual(result["status"], "Queued")
		self.assert_within_budget("prewarm_catalog", elapsed_ms)

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

	def _set_base_domain(self, value):
		before = frappe.db.get_single_value("BenchPress Settings", "base_domain")
		frappe.db.set_single_value("BenchPress Settings", "base_domain", value)
		self.addCleanup(frappe.db.set_single_value, "BenchPress Settings", "base_domain", before)

	def test_create_bench_honors_an_explicit_site_name(self):
		self._set_base_domain("benchpress.cloud")
		data = frappe.as_json({"lab": self.create_lab.name, "site_name": "acme"})
		with patch("frappe.enqueue"):
			result = api.create_bench(data)
		self.addCleanup(
			frappe.delete_doc, "Bench Instance", result["name"], force=True, ignore_permissions=True
		)
		self.assertEqual(
			frappe.db.get_value("Bench Instance", result["name"], "site_name"), "acme.benchpress.cloud"
		)

	def test_create_bench_rejects_a_duplicate_site_name(self):
		self._set_base_domain("benchpress.cloud")
		other_lab = _ensure_lab("api-timing-dup-site-lab")
		other_bench = _ensure_bench(other_lab)
		self.addCleanup(
			frappe.delete_doc, "Bench Instance", other_bench.name, force=True, ignore_permissions=True
		)
		self.addCleanup(frappe.delete_doc, "Lab", other_lab.name, force=True, ignore_permissions=True)
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"bench": other_bench.name,
				"site_name": "acme.benchpress.cloud",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Site", site.name, force=True, ignore_permissions=True)
		frappe.db.commit()

		data = frappe.as_json({"lab": self.create_lab.name, "site_name": "acme"})
		with self.assertRaises(frappe.ValidationError):
			api.create_bench(data)
		instance_id = get_instance_id(frappe.session.user, self.create_lab.name)
		self.assertFalse(frappe.db.exists("Bench Instance", instance_id))

	def test_create_bench_refuses_to_rename_a_deployed_instance(self):
		self._set_base_domain("benchpress.cloud")
		lab = _ensure_lab("api-timing-rename-running-lab", apps=[_lab_app()])
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)
		bench = _ensure_bench(lab, status="Running", site_name="original.benchpress.cloud")
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)

		data = frappe.as_json({"lab": lab.name, "site_name": "renamed"})
		with self.assertRaises(frappe.ValidationError):
			api.create_bench(data)
		self.assertEqual(
			frappe.db.get_value("Bench Instance", bench.name, "site_name"), "original.benchpress.cloud"
		)

	def test_create_bench_refuses_to_rename_a_stopped_instance(self):
		"""`stop_bench` never drops the database, so a `Stopped` instance's site is still live."""
		self._set_base_domain("benchpress.cloud")
		lab = _ensure_lab("api-timing-rename-stopped-lab", apps=[_lab_app()])
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)
		bench = _ensure_bench(lab, status="Stopped", site_name="original.benchpress.cloud")
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)

		data = frappe.as_json({"lab": lab.name, "site_name": "renamed"})
		with self.assertRaises(frappe.ValidationError):
			api.create_bench(data)
		self.assertEqual(
			frappe.db.get_value("Bench Instance", bench.name, "site_name"), "original.benchpress.cloud"
		)

	def test_create_bench_allows_a_new_site_name_after_teardown(self):
		self._set_base_domain("benchpress.cloud")
		lab = _ensure_lab("api-timing-rename-draft-lab", apps=[_lab_app()])
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)
		bench = _ensure_bench(lab, status="Draft", site_name="old.benchpress.cloud")
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)

		data = frappe.as_json({"lab": lab.name, "site_name": "fresh"})
		with patch("frappe.enqueue"):
			result = api.create_bench(data)
		self.assertEqual(result["status"], "Deploying")
		self.assertEqual(
			frappe.db.get_value("Bench Instance", bench.name, "site_name"), "fresh.benchpress.cloud"
		)

	def test_create_bench_redeploy_with_the_same_site_name_is_a_no_op(self):
		self._set_base_domain("benchpress.cloud")
		lab = _ensure_lab("api-timing-rename-noop-lab", apps=[_lab_app()])
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)
		bench = _ensure_bench(lab, status="Running", site_name="stable.benchpress.cloud")
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)

		data = frappe.as_json({"lab": lab.name, "site_name": "stable"})
		with patch("frappe.enqueue"):
			result = api.create_bench(data)
		self.assertEqual(result["status"], "Deploying")
		self.assertEqual(
			frappe.db.get_value("Bench Instance", bench.name, "site_name"), "stable.benchpress.cloud"
		)

		data_without_site_name = frappe.as_json({"lab": lab.name})
		with patch("frappe.enqueue"):
			api.create_bench(data_without_site_name)
		self.assertEqual(
			frappe.db.get_value("Bench Instance", bench.name, "site_name"), "stable.benchpress.cloud"
		)

	def test_create_bench_without_site_name_defaults_to_the_public_hostname(self):
		data = frappe.as_json({"lab": self.create_lab.name})
		with patch("frappe.enqueue"):
			result = api.create_bench(data)
		self.addCleanup(
			frappe.delete_doc, "Bench Instance", result["name"], force=True, ignore_permissions=True
		)
		site_name = frappe.db.get_value("Bench Instance", result["name"], "site_name")
		base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
		suffix = base_domain if base_domain and base_domain != "localhost" else "localhost"
		self.assertEqual(site_name, f"{result['name']}.{suffix}")

	# --- Docker / manager side effects (patch module functions) --------------

	def test_bench_action_start_stop_restart_and_timing(self):
		with (
			patch("benchpress.docker_manager.start_container"),
			# Stop routes through `deploy_manager.stop_bench`, which bound its Docker call at
			# import — so the patch has to land on that module, not on `docker_manager`.
			patch("benchpress.deploy_manager.stop_container"),
			patch("benchpress.docker_manager.restart_container"),
			patch("benchpress.docker_manager.remove_container"),
		):
			for action, expected in (("start", "Running"), ("stop", "Stopped"), ("restart", "Running")):
				result, elapsed_ms = _timed(lambda: api.bench_action(self.action_bench.name, action))
				self.assertEqual(result["name"], self.action_bench.name)
				self.assertEqual(result["status"], expected)
				self.assert_within_budget("bench_action", elapsed_ms)

	def test_bench_action_stop_deactivates_the_sites(self):
		"""The SPA's Stop and the worker's stop are one path, so neither can skip the rows."""
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"bench": self.action_bench.name,
				"site_name": "stop-path.localhost",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Site", site.name, force=True, ignore_permissions=True)
		self.addCleanup(frappe.db.commit)

		with patch("benchpress.deploy_manager.stop_container"):
			api.bench_action(self.action_bench.name, "stop")

		self.assertEqual(frappe.db.get_value("Bench Site", site.name, "status"), "Inactive")

	def test_bench_action_on_an_instance_with_no_container_never_reaches_docker(self):
		"""A Draft or reaped instance has no container id; Docker's own error names nothing
		the user can act on, so the guard has to fire before the call."""
		lab = _ensure_lab("api-timing-no-container-lab")
		bench = _ensure_bench(lab, status="Draft")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Instance", bench.name, force=True, ignore_permissions=True)

		for action in ("start", "stop", "restart"):
			with (
				self.subTest(action=action),
				patch("benchpress.docker_manager.start_container") as start,
				patch("benchpress.deploy_manager.stop_container") as stop,
				patch("benchpress.docker_manager.restart_container") as restart,
			):
				with self.assertRaises(frappe.ValidationError) as caught:
					api.bench_action(bench.name, action)
				self.assertIn("deploy it first", str(caught.exception))
				start.assert_not_called()
				stop.assert_not_called()
				restart.assert_not_called()

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
