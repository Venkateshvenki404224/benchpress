# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import contextlib
import io
from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from benchpress import doctor, setup
from benchpress.setup import (
	APPLY,
	OK,
	SKIP,
	STEPS,
	_format_plan,
	_passes,
	_plan_summary,
	_record,
	plan,
)


def _doctor_result(status):
	return [doctor._result(status, "x", "detail")]


class TestPasses(IntegrationTestCase):
	def test_all_pass_is_true(self):
		self.assertTrue(_passes(lambda: _doctor_result(doctor.PASS)))

	def test_any_warn_is_false(self):
		results = [doctor._result(doctor.PASS, "a", ""), doctor._result(doctor.WARN, "b", "")]
		self.assertFalse(_passes(lambda: results))

	def test_any_fail_is_false(self):
		self.assertFalse(_passes(lambda: _doctor_result(doctor.FAIL)))


class TestFormatPlan(IntegrationTestCase):
	def test_tags_and_summary_present(self):
		records = [
			_record(OK, "Sudoers", "already applied"),
			_record(APPLY, "IP forwarding", "would apply", change=["sysctl -w net.ipv4.ip_forward=1"]),
		]
		report = _format_plan(records, {"site": "frontend"})
		self.assertIn("[OK]", report)
		self.assertIn("[APPLY]", report)
		self.assertIn("Plan:", report)

	def test_no_ansi_when_not_tty(self):
		report = _format_plan([_record(OK, "A", "ok")], {"site": "frontend"}, tty=False)
		self.assertNotIn("\x1b", report)

	def test_ansi_when_tty(self):
		report = _format_plan([_record(APPLY, "A", "would apply")], {"site": "frontend"}, tty=True)
		self.assertIn("\x1b", report)


class TestSecretSafety(IntegrationTestCase):
	def test_plan_never_leaks_secret_shapes(self):
		records = [_record(APPLY, s.name, "would apply", change=s.describe()) for s in STEPS]
		env = {"site": "frontend", "bench": "/home/frappe/frappe-bench", "in_container": False}
		report = _format_plan(records, env, tty=False)
		for needle in ("$apr1$", "PrivateKey", "-----BEGIN", "@"):
			self.assertNotIn(needle, report)


class TestPlanSummary(IntegrationTestCase):
	def test_counts_by_status(self):
		records = [
			_record(OK, "a", ""),
			_record(APPLY, "b", ""),
			_record(APPLY, "c", ""),
			_record(SKIP, "d", ""),
		]
		self.assertEqual(_plan_summary(records), {"apply": 2, "ok": 1, "skip": 1})


class TestPlan(IntegrationTestCase):
	def test_plan_is_read_only_and_classifies_rows(self):
		with (
			patch.object(STEPS[0], "apply") as sudoers_apply,
			patch.object(STEPS[1], "apply") as ip_forward_apply,
			patch.object(doctor, "_in_docker", return_value=False),
			patch.object(doctor, "_check_sudoers", return_value=_doctor_result(doctor.PASS)),
			patch.object(doctor, "_check_ip_forward", return_value=_doctor_result(doctor.FAIL)),
		):
			records = plan()

		sudoers_apply.assert_not_called()
		ip_forward_apply.assert_not_called()
		by_step = {r["step"]: r["status"] for r in records}
		self.assertEqual(by_step["Sudoers (passwordless wg)"], OK)
		self.assertEqual(by_step["IP forwarding"], APPLY)

	def test_ip_forward_applies_when_persistence_conf_absent(self):
		with (
			patch.object(doctor, "_in_docker", return_value=False),
			patch.object(doctor, "_check_ip_forward", return_value=_doctor_result(doctor.PASS)),
			patch("os.path.exists", return_value=False),
		):
			records = plan(only="ip_forward")
		self.assertEqual(len(records), 1)
		self.assertEqual(records[0]["step"], "IP forwarding")
		self.assertEqual(records[0]["status"], APPLY)

	def test_container_degrade_skips_host_only_steps(self):
		with patch.object(doctor, "_in_docker", return_value=True):
			records = plan()
		self.assertEqual(len(records), 2)
		self.assertTrue(all(r["status"] == SKIP for r in records))


class TestRun(IntegrationTestCase):
	def test_dry_run_mutates_nothing(self):
		buf = io.StringIO()
		with (
			patch("subprocess.run") as subprocess_run,
			patch.object(STEPS[0], "apply") as sudoers_apply,
			patch.object(STEPS[1], "apply") as ip_forward_apply,
			patch.object(doctor, "_in_docker", return_value=False),
			patch.object(doctor, "_check_sudoers", return_value=_doctor_result(doctor.FAIL)),
			patch.object(doctor, "_check_ip_forward", return_value=_doctor_result(doctor.FAIL)),
			contextlib.redirect_stdout(buf),
		):
			result = setup.run(dry_run=True)

		self.assertIsNone(result)
		subprocess_run.assert_not_called()
		sudoers_apply.assert_not_called()
		ip_forward_apply.assert_not_called()
		self.assertIn("Plan:", buf.getvalue())
