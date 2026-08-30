# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""One click is one job: build the image the deploy needs, then deploy, then say so."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import deploy_pipeline, image_cache, launch, lifecycle
from benchpress.credits import admission
from benchpress.tests.test_deploy_manager import _fresh_bench, _make_lab

ADMISSION = "Bench Admission"
DEPLOY_LOG = "Deploy Log"
# The lab is shared catalog content, so its author is somebody other than the person launching it.
LAB_AUTHOR = "launch-lab-author@example.com"


def _ensure_user(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Lab Author", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	return email


class TestRunLaunch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-launch")
		frappe.db.set_value("Lab", cls.lab.name, "owner", _ensure_user(LAB_AUTHOR))
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.db.delete(DEPLOY_LOG, {"bench": name})
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		frappe.db.delete("Build Log", {"lab": cls.lab.name})
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		image_cache.clear_cached_tags()
		self.addCleanup(image_cache.clear_cached_tags)

	def _bench(self):
		bench = _fresh_bench(self, self.lab.name)
		# The run commits, so the class rollback cannot take these back.
		self.addCleanup(frappe.db.commit)
		self.addCleanup(lambda name=bench.name: frappe.db.delete(DEPLOY_LOG, {"bench": name}))
		return bench

	def _make_ready(self):
		"""The lab as a second launcher finds it: built, and its row pointing at the image."""
		tag = image_cache.cache_tag(self.lab)
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": tag})
		frappe.db.commit()
		return tag

	def _make_unbuilt(self):
		frappe.db.set_value("Lab", self.lab.name, {"status": "Draft", "image_tag": None})
		frappe.db.commit()

	def _run(self, bench, cached=(), build_error=None):
		"""One launch with the build and the deploy stubbed, but the log and the lock real."""
		with (
			patch.object(image_cache, "list_cached_tags", autospec=True, return_value=set(cached)),
			patch.object(launch.deploy_manager, "_run_build", autospec=True) as run_build,
			patch.object(lifecycle, "deploy_bench", autospec=True) as deploy,
			patch.object(launch, "_announce", autospec=True),
		):
			if build_error:
				run_build.side_effect = build_error
			launch.run_launch(bench.name)
		return run_build, deploy

	def _logs(self, bench_name):
		return frappe.get_all(
			DEPLOY_LOG, filters={"bench": bench_name}, fields=["name", "message", "log_type"]
		)

	def test_a_built_lab_goes_straight_to_the_deploy_it_already_has_an_image_for(self):
		bench = self._bench()
		tag = self._make_ready()

		run_build, deploy = self._run(bench, cached=[tag])

		run_build.assert_not_called()
		logs = self._logs(bench.name)
		# One `Deploy Log` for the whole launch: the deploy is handed the row, not asked to open one.
		self.assertEqual(len(logs), 1)
		deploy.assert_called_once_with(bench.name, None, logs[0].name)

	def test_an_unbuilt_lab_is_built_before_the_deploy_and_then_deployed(self):
		bench = self._bench()
		self._make_unbuilt()

		run_build, deploy = self._run(bench, cached=[])

		run_build.assert_called_once()
		deploy.assert_called_once()

	def test_the_build_belongs_to_the_launcher_not_to_the_lab_s_author(self):
		"""The Build Log and its stream go to whoever is watching, and that is not the author."""
		bench = self._bench()
		self._make_unbuilt()

		run_build, _deploy = self._run(bench, cached=[])

		self.assertNotEqual(frappe.db.get_value("Lab", self.lab.name, "owner"), bench.owner)
		self.assertEqual(run_build.call_args.args[1], bench.owner)

	def test_the_image_step_is_opened_before_docker_so_the_stepper_reads_it(self):
		bench = self._bench()
		self._make_unbuilt()

		self._run(bench, cached=[])

		scan = deploy_pipeline.scan_log(self._logs(bench.name)[0].message)
		self.assertEqual(scan.step, deploy_pipeline.step_label("image"))

	def test_a_failed_build_stops_the_launch_before_the_deploy(self):
		bench = self._bench()
		self._make_unbuilt()
		admission.claim("Administrator", bench.name, 0, 0.0)
		frappe.db.commit()
		self.assertTrue(frappe.db.exists(ADMISSION, bench.name))

		_run_build, deploy = self._run(bench, cached=[], build_error=Exception("docker build blew up"))

		deploy.assert_not_called()
		self.assertEqual(frappe.db.get_value("Lab", self.lab.name, "status"), "Error")
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")
		# The hold and the slot go back, or the launcher is one instance poorer for a run that
		# never created one.
		self.assertFalse(frappe.db.exists(ADMISSION, bench.name))
		log = self._logs(bench.name)[0]
		self.assertIn("=== Deploy failed: the lab image could not be built:", log.message)
		self.assertEqual(log.log_type, "error")
