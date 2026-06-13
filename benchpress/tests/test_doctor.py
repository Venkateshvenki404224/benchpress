# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from benchpress.doctor import (
	FAIL,
	MIN_CPU_CORES,
	MIN_FREE_DISK_GB,
	MIN_RAM_GB,
	PASS,
	WARN,
	_evaluate_os,
	_evaluate_resources,
	_format_report,
	_result,
	_summary,
)

UBUNTU = {"ID": "ubuntu", "ID_LIKE": "debian", "PRETTY_NAME": "Ubuntu 22.04.4 LTS"}
GENERIC_PROC = "Linux version 6.8.0-124-generic (buildd@lcy02) gcc"
WSL_PROC = "Linux version 5.15.133.1-microsoft-standard-WSL2 (oe-user@oe-host)"


def _status_for(results, name):
	return next(r["status"] for r in results if r["name"] == name)


class TestEvaluateResources(IntegrationTestCase):
	def test_below_threshold_fails(self):
		results = _evaluate_resources(MIN_CPU_CORES - 1, MIN_RAM_GB - 1, MIN_FREE_DISK_GB - 1)
		self.assertEqual(_status_for(results, "CPU cores"), FAIL)
		self.assertEqual(_status_for(results, "Memory"), FAIL)
		self.assertEqual(_status_for(results, "Free disk"), FAIL)

	def test_at_threshold_warns(self):
		results = _evaluate_resources(MIN_CPU_CORES, MIN_RAM_GB, MIN_FREE_DISK_GB)
		for name in ("CPU cores", "Memory", "Free disk"):
			self.assertEqual(_status_for(results, name), WARN)

	def test_above_threshold_passes(self):
		results = _evaluate_resources(MIN_CPU_CORES + 2, MIN_RAM_GB + 4, MIN_FREE_DISK_GB + 50)
		for name in ("CPU cores", "Memory", "Free disk"):
			self.assertEqual(_status_for(results, name), PASS)


class TestEvaluateOs(IntegrationTestCase):
	def test_ubuntu_passes(self):
		self.assertEqual(_evaluate_os(UBUNTU, GENERIC_PROC, False)["status"], PASS)

	def test_wsl2_warns(self):
		result = _evaluate_os(UBUNTU, WSL_PROC, False)
		self.assertEqual(result["status"], WARN)
		self.assertIn("WSL2", result["detail"])

	def test_unknown_distro_warns(self):
		unknown = {"ID": "arch", "PRETTY_NAME": "Arch Linux"}
		self.assertEqual(_evaluate_os(unknown, GENERIC_PROC, False)["status"], WARN)


class TestFormatReport(IntegrationTestCase):
	def test_tags_and_summary_present(self):
		report = _format_report(
			[_result(PASS, "A", "ok"), _result(FAIL, "B", "bad", "do x")], {"site": "frontend"}
		)
		self.assertIn("[PASS]", report)
		self.assertIn("[FAIL]", report)
		self.assertIn("Summary:", report)

	def test_no_ansi_when_not_tty(self):
		report = _format_report([_result(PASS, "A", "ok")], {"site": "frontend"}, tty=False)
		self.assertNotIn("\x1b", report)

	def test_ansi_when_tty(self):
		report = _format_report([_result(PASS, "A", "ok")], {"site": "frontend"}, tty=True)
		self.assertIn("\x1b", report)


class TestSecretSafety(IntegrationTestCase):
	def test_report_never_leaks_secret_shapes(self):
		results = [
			_result(PASS, "A", "ok"),
			_result(WARN, "B", "borderline", "fix it"),
			_result(FAIL, "C", "bad", "do x"),
		]
		env = {"site": "frontend", "bench": "/home/frappe/frappe-bench", "in_container": True}
		report = _format_report(results, env, tty=False)
		for needle in ("$apr1$", "PrivateKey", "-----BEGIN", "@"):
			self.assertNotIn(needle, report)


class TestSummary(IntegrationTestCase):
	def test_counts_by_status(self):
		results = [
			_result(PASS, "a", ""),
			_result(PASS, "b", ""),
			_result(WARN, "c", ""),
			_result(FAIL, "d", ""),
			_result(FAIL, "e", ""),
			_result(FAIL, "f", ""),
		]
		self.assertEqual(_summary(results), {"pass": 2, "warn": 1, "fail": 3})
