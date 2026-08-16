# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.deploy_pipeline import (
	DEPLOY_STEPS,
	STEP_INDEX,
	STEP_TOTAL,
	DeployLogWriter,
	DeployPipeline,
	format_step_line,
	parse_step_line,
)


class TestStepLines(IntegrationTestCase):
	"""The line format is a contract with `frontend/src/utils/deploySteps.js`."""

	def test_every_step_round_trips(self):
		for step in DEPLOY_STEPS:
			parsed = parse_step_line(format_step_line(step.key, 12.34))
			self.assertIsNotNone(parsed, f"{step.key} did not parse")
			self.assertEqual(parsed["step_key"], step.key)
			self.assertEqual(parsed["step_label"], step.label)
			self.assertEqual(parsed["step_index"], STEP_INDEX[step.key])
			self.assertEqual(parsed["step_total"], STEP_TOTAL)
			self.assertEqual(parsed["step_elapsed"], 12.3)

	def test_marker_keeps_the_legacy_prefix(self):
		# `LogViewer.vue` and `lab_detail` both parse `=== … ===`; metadata goes
		# inside the wrapper, never in place of it.
		line = format_step_line("site", 61.4)
		self.assertTrue(line.startswith("=== "))
		self.assertTrue(line.endswith(" ==="))
		self.assertIn("Step 7/11", line)

	def test_a_legacy_marker_is_not_read_as_a_step(self):
		self.assertIsNone(parse_step_line("=== Creating container ==="))
		self.assertIsNone(parse_step_line("Building assets..."))

	def test_the_order_is_the_code_s_not_the_brief_s(self):
		# DESIGN_BRIEF §4 puts the WireGuard peer at 10; `_setup_container_vpn`
		# runs it right after the container IP, so the stepper says 5.
		self.assertEqual(STEP_INDEX["container_ip"], 4)
		self.assertEqual(STEP_INDEX["vpn_peer"], 5)
		self.assertEqual(STEP_INDEX["site_config"], 6)
		self.assertEqual(STEP_TOTAL, 11)

	def test_the_terminal_step_still_reads_as_deploy_complete(self):
		self.assertIn("Deploy complete", format_step_line("complete", 180.0))


class TestDeployLogWriter(IntegrationTestCase):
	"""Every line is published to one user's room, and to nobody else's."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": "test-lab-log-writer",
				"title": "Test Lab (Log Writer)",
				"frappe_version": "version-15",
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("Build Log", {"lab": cls.lab.name})
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _writer(self, user="owner@example.com"):
		log = frappe.get_doc(
			{
				"doctype": "Build Log",
				"lab": self.lab.name,
				"message": "",
				"log_type": "info",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
		self.addCleanup(
			lambda name=log.name: frappe.delete_doc(
				"Build Log", name, force=True, ignore_permissions=True
			)
		)
		return log, DeployLogWriter(
			"Build Log", log.name, "lab_build_log", {"lab": self.lab.name, "build_log": log.name}, user
		)

	def test_the_payload_keeps_the_keys_the_spa_appends_on(self):
		_, writer = self._writer()

		with patch("frappe.publish_realtime") as publish:
			writer("cloning frappe…")

		message = publish.call_args.kwargs["message"]
		self.assertEqual(
			set(message), {"lab", "build_log", "log", "type"}
		)  # additive only: no key may disappear
		self.assertEqual(message["log"], "cloning frappe…")
		self.assertEqual(message["type"], "info")

	def test_a_step_adds_its_metadata_beside_those_keys(self):
		_, writer = self._writer()
		pipeline = DeployPipeline(writer)

		with patch("frappe.publish_realtime") as publish:
			pipeline.step("site")

		message = publish.call_args.kwargs["message"]
		self.assertEqual(message["type"], "step")
		self.assertEqual(message["step_key"], "site")
		self.assertEqual(message["step_index"], 7)
		self.assertEqual(message["step_total"], STEP_TOTAL)
		self.assertEqual(message["step_label"], "Creating the site")
		self.assertIn("log", message)

	def test_the_publish_is_scoped_to_the_run_s_owner(self):
		_, writer = self._writer(user="owner@example.com")

		with patch("frappe.publish_realtime") as publish:
			writer("=== Build started ===")

		# No room, no doctype: a user room, so a second user's socket is never
		# in the set of recipients.
		self.assertEqual(publish.call_args.kwargs["user"], "owner@example.com")
		self.assertFalse(publish.call_args.kwargs.get("room"))
		self.assertIs(publish.call_args.kwargs["after_commit"], False)

	def test_the_line_is_appended_to_the_document(self):
		log, writer = self._writer()

		writer("first")
		writer("second")

		self.assertEqual(frappe.db.get_value("Build Log", log.name, "message"), "first\nsecond\n")
