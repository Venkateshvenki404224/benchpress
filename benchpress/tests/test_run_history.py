# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Build and deploy history: what a row says, and whose runs a caller sees.

The scoping tests are the point of the module. `Build Log` carries no
permission query condition, so before this endpoint existed a `BenchPress User`
reading the doctype through the generic list API was served every other user's
image builds. A regression there is silent — the table still renders — so it is
asserted from both directions: the owner sees their run, and the other user does
not.
"""

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import run_history
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.deploy_pipeline import format_step_line

# A finished run from the current pipeline: every marker carries its offset, and
# the terminal step carries the whole run's elapsed time.
STRUCTURED_LOG = "\n".join(
	[
		"=== Deploy started ===",
		format_step_line("infrastructure", 0.0),
		"MariaDB reachable at benchpress-mariadb:3306",
		format_step_line("image", 4.2),
		format_step_line("complete", 97.2),
	]
)

# A run that died at step seven.
FAILED_LOG = "\n".join(
	[
		format_step_line("site_config", 40.1),
		format_step_line("site", 61.4),
		"ERROR: new-site exited 1",
		"=== Deploy failed: site creation failed ===",
		"Cleanup: removed the container",
	]
)

# A build streams Docker's own output and never emitted structured markers.
BUILD_LOG = "\n".join(
	[
		"=== Build started ===",
		"Building image benchpress/history-lab:latest (base: frappe/build:version-15, apps: 1)",
		"=== Build complete: benchpress/history-lab:latest ===",
	]
)


def _ensure_user(email, first_name, role):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id, **extra):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"History {lab_id}",
			"frappe_version": "version-15",
			**extra,
		}
	).insert(ignore_permissions=True)


def _log(doctype, owner, **fields):
	"""Insert a log owned by `owner` — ownership comes from the session user."""
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{"doctype": doctype, "timestamp": frappe.utils.now_datetime(), **fields}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestRunHistory(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.owner = _ensure_user("history-owner@example.com", "History Owner", "BenchPress User")
		cls.other = _ensure_user("history-other@example.com", "History Other", "BenchPress User")

		cls.lab = _ensure_lab("history-lab", image_tag="benchpress/history-lab:latest")
		cls.bench = cls._ensure_bench(cls.owner, cls.lab)

		cls.owner_build = _log(
			"Build Log", cls.owner, lab=cls.lab.name, log_type="success", message=BUILD_LOG
		)
		cls.other_build = _log(
			"Build Log", cls.other, lab=cls.lab.name, log_type="error", message="=== Build failed: boom ==="
		)
		cls.done_deploy = _log(
			"Deploy Log", cls.owner, bench=cls.bench.name, log_type="success", message=STRUCTURED_LOG
		)
		cls.failed_deploy = _log(
			"Deploy Log", cls.owner, bench=cls.bench.name, log_type="error", message=FAILED_LOG
		)
		cls.running_deploy = _log(
			"Deploy Log", cls.owner, bench=cls.bench.name, log_type="info", message="=== Deploy started ==="
		)
		frappe.db.commit()

	@classmethod
	def _ensure_bench(cls, owner, lab):
		name = get_instance_id(owner, lab.name)
		if frappe.db.exists("Bench Instance", name):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		frappe.set_user(owner)
		try:
			return frappe.get_doc(
				{"doctype": "Bench Instance", "lab": lab.name, "frappe_version": lab.frappe_version}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for log in (cls.owner_build, cls.other_build):
			frappe.delete_doc("Build Log", log.name, force=True, ignore_permissions=True)
		for log in (cls.done_deploy, cls.failed_deploy, cls.running_deploy):
			frappe.delete_doc("Deploy Log", log.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		for email in (cls.owner, cls.other):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _row(self, rows, name):
		return next((row for row in rows if row["name"] == name), None)

	# --- Shape ---------------------------------------------------------------

	def test_build_history_row_shape(self):
		history = run_history.get_build_history()
		self.assertEqual(history["window_days"], 7)
		self.assertEqual(history["limit"], run_history.HISTORY_LIMIT)
		row = self._row(history["rows"], self.owner_build.name)
		for key in ("lab", "lab_title", "image_tag", "result", "last_step", "duration_label", "started"):
			self.assertIn(key, row)
		self.assertEqual(row["lab"], self.lab.name)
		self.assertEqual(row["image_tag"], "benchpress/history-lab:latest")

	def test_a_build_reports_the_tag_it_named_itself(self):
		"""A run that recorded its tag is read from the log, not from the lab."""
		log = _log(
			"Build Log",
			self.owner,
			lab=self.lab.name,
			log_type="error",
			message="Building image benchpress/run-specific:v9 (base: frappe/build:version-15, apps: 0)",
		)
		self.addCleanup(frappe.delete_doc, "Build Log", log.name, force=True, ignore_permissions=True)
		row = self._row(run_history.get_build_history()["rows"], log.name)
		self.assertEqual(row["image_tag"], "benchpress/run-specific:v9")

	def test_deploy_history_row_shape(self):
		rows = run_history.get_deploy_history()["rows"]
		row = self._row(rows, self.done_deploy.name)
		self.assertEqual(row["bench"], self.bench.name)
		self.assertEqual(row["lab"], self.lab.name)

	def test_result_reads_as_an_outcome_not_a_log_type(self):
		builds = run_history.get_build_history()["rows"]
		deploys = run_history.get_deploy_history()["rows"]
		self.assertEqual(self._row(builds, self.owner_build.name)["result"], "Success")
		self.assertEqual(self._row(builds, self.other_build.name)["result"], "Failed")
		self.assertEqual(self._row(deploys, self.failed_deploy.name)["result"], "Failed")
		self.assertEqual(self._row(deploys, self.running_deploy.name)["result"], "Deploying")

	# --- What the run recorded about itself ----------------------------------

	def test_a_finished_pipeline_reports_its_own_measured_duration(self):
		row = self._row(run_history.get_deploy_history()["rows"], self.done_deploy.name)
		self.assertEqual(row["last_step"], "Deploy complete")
		self.assertEqual(row["duration_seconds"], 97.2)
		self.assertEqual(row["duration_label"], "1m 37s")

	def test_a_failed_run_names_the_step_it_died_in(self):
		row = self._row(run_history.get_deploy_history()["rows"], self.failed_deploy.name)
		self.assertEqual(row["last_step"], "Creating the site")

	def test_a_run_still_in_flight_has_no_duration_rather_than_a_growing_guess(self):
		row = self._row(run_history.get_deploy_history()["rows"], self.running_deploy.name)
		self.assertIsNone(row["duration_seconds"])
		self.assertEqual(row["duration_label"], "")

	def test_a_build_reports_the_marker_it_last_opened(self):
		row = self._row(run_history.get_build_history()["rows"], self.owner_build.name)
		self.assertEqual(row["last_step"], "Build complete: benchpress/history-lab:latest")

	# --- Scoping -------------------------------------------------------------

	def test_admin_sees_every_build(self):
		names = [row["name"] for row in run_history.get_build_history()["rows"]]
		self.assertIn(self.owner_build.name, names)
		self.assertIn(self.other_build.name, names)

	def test_a_user_sees_only_their_own_builds(self):
		frappe.set_user(self.owner)
		names = [row["name"] for row in run_history.get_build_history()["rows"]]
		self.assertIn(self.owner_build.name, names, "the owner lost sight of their own build")
		self.assertNotIn(self.other_build.name, names, "Build Log is leaking across users")

	def test_a_user_sees_only_deploys_of_their_own_benches(self):
		frappe.set_user(self.other)
		names = [row["name"] for row in run_history.get_deploy_history()["rows"]]
		self.assertNotIn(self.done_deploy.name, names)

		frappe.set_user(self.owner)
		names = [row["name"] for row in run_history.get_deploy_history()["rows"]]
		self.assertIn(self.done_deploy.name, names)
