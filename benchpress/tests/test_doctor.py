# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import contextlib
import io
import json
from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from benchpress import doctor
from benchpress.doctor import (
	FAIL,
	MIN_CPU_CORES,
	MIN_FREE_DISK_GB,
	MIN_RAM_GB,
	PASS,
	WARN,
	_evaluate_compose,
	_evaluate_container,
	_evaluate_docker_network,
	_evaluate_http_port,
	_evaluate_ip_forward,
	_evaluate_os,
	_evaluate_resources,
	_evaluate_sudoers,
	_evaluate_wg_interface,
	_evaluate_wg_port,
	_evaluate_wireguard_tools,
	_format_report,
	_network_subnet,
	_parse_listening_ports,
	_result,
	_skipped,
	_summary,
	run,
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


class TestSkipped(IntegrationTestCase):
	def test_skipped_is_warn_on_the_host(self):
		result = _skipped("IP forwarding")
		self.assertEqual(result["status"], WARN)
		self.assertIn("run on the host", result["detail"])


class TestEvaluateCompose(IntegrationTestCase):
	def test_available_passes(self):
		self.assertEqual(_evaluate_compose(True, "Docker Compose version v2.27.0")["status"], PASS)

	def test_missing_fails_with_install_fix(self):
		result = _evaluate_compose(False, "")
		self.assertEqual(result["status"], FAIL)
		self.assertIn("docker-compose-plugin", result["fix"])


class TestEvaluateDockerNetwork(IntegrationTestCase):
	def test_missing_fails(self):
		self.assertEqual(_evaluate_docker_network(False, "")["status"], FAIL)

	def test_expected_subnet_passes(self):
		self.assertEqual(_evaluate_docker_network(True, "172.30.0.0/24")["status"], PASS)

	def test_wrong_subnet_warns(self):
		self.assertEqual(_evaluate_docker_network(True, "10.0.0.0/24")["status"], WARN)


class TestNetworkSubnet(IntegrationTestCase):
	def test_extracts_subnet(self):
		attrs = {"IPAM": {"Config": [{"Subnet": "172.30.0.0/24"}]}}
		self.assertEqual(_network_subnet(attrs), "172.30.0.0/24")

	def test_missing_config_returns_empty(self):
		self.assertEqual(_network_subnet({}), "")


class TestEvaluateContainer(IntegrationTestCase):
	def test_running_passes(self):
		self.assertEqual(_evaluate_container("benchpress-redis", "running", FAIL, "fix")["status"], PASS)

	def test_stopped_uses_severity(self):
		self.assertEqual(_evaluate_container("benchpress-traefik", "exited", WARN, "fix")["status"], WARN)

	def test_not_found_carries_fix(self):
		result = _evaluate_container("benchpress-mariadb", None, FAIL, "do x")
		self.assertEqual(result["status"], FAIL)
		self.assertEqual(result["fix"], "do x")


class TestEvaluateIpForward(IntegrationTestCase):
	def test_enabled_passes(self):
		self.assertEqual(_evaluate_ip_forward("1\n")["status"], PASS)

	def test_disabled_fails_with_sysctl_fix(self):
		result = _evaluate_ip_forward("0\n")
		self.assertEqual(result["status"], FAIL)
		self.assertIn("ip_forward=1", result["fix"])


class TestEvaluateSudoers(IntegrationTestCase):
	def test_missing_file_fails(self):
		self.assertEqual(_evaluate_sudoers(False, False)["status"], FAIL)

	def test_sudo_check_failing_fails(self):
		self.assertEqual(_evaluate_sudoers(True, False)["status"], FAIL)

	def test_configured_passes(self):
		self.assertEqual(_evaluate_sudoers(True, True)["status"], PASS)


class TestEvaluateWireguardTools(IntegrationTestCase):
	def test_missing_tool_warns(self):
		result = _evaluate_wireguard_tools(False, True, False)
		self.assertEqual(result["status"], WARN)
		self.assertIn("wg", result["detail"])

	def test_no_kernel_module_warns(self):
		self.assertEqual(_evaluate_wireguard_tools(True, True, False)["status"], WARN)

	def test_all_present_passes(self):
		self.assertEqual(_evaluate_wireguard_tools(True, True, True)["status"], PASS)


class TestEvaluateWgInterface(IntegrationTestCase):
	def test_down_warns_with_bring_up_fix(self):
		result = _evaluate_wg_interface(False, "", "51820")
		self.assertEqual(result["status"], WARN)
		self.assertIn("wg-quick up", result["fix"])

	def test_port_mismatch_warns(self):
		self.assertEqual(_evaluate_wg_interface(True, "51821", "51820")["status"], WARN)

	def test_matching_port_passes(self):
		self.assertEqual(_evaluate_wg_interface(True, "51820", "51820")["status"], PASS)


class TestEvaluatePorts(IntegrationTestCase):
	def test_free_http_port_passes(self):
		self.assertEqual(_evaluate_http_port(80, False, False)["status"], PASS)

	def test_http_port_owned_by_traefik_passes(self):
		self.assertEqual(_evaluate_http_port(443, True, True)["status"], PASS)

	def test_http_port_taken_by_other_warns(self):
		self.assertEqual(_evaluate_http_port(80, True, False)["status"], WARN)

	def test_wg_port_bound_passes(self):
		self.assertEqual(_evaluate_wg_port(51820, True)["status"], PASS)

	def test_wg_port_unbound_warns_with_port_in_fix(self):
		result = _evaluate_wg_port(51820, False)
		self.assertEqual(result["status"], WARN)
		self.assertIn("51820", result["fix"])


class TestRun(IntegrationTestCase):
	def _run_capturing(self, checks, **kwargs):
		buf = io.StringIO()
		with patch.object(doctor, "CHECKS", checks), contextlib.redirect_stdout(buf):
			run(**kwargs)
		return buf.getvalue()

	def test_json_output_is_valid_results_array(self):
		checks = [lambda: [_result(PASS, "A", "ok"), _result(WARN, "B", "borderline", "fix it")]]
		parsed = json.loads(self._run_capturing(checks, as_json=True))
		self.assertEqual([r["name"] for r in parsed], ["A", "B"])
		self.assertEqual(parsed[1]["fix"], "fix it")

	def test_strict_exits_nonzero_on_fail(self):
		checks = [lambda: [_result(FAIL, "A", "bad", "do x")]]
		with self.assertRaises(SystemExit) as ctx:
			self._run_capturing(checks, strict=True)
		self.assertEqual(ctx.exception.code, 1)

	def test_strict_exits_zero_without_fail(self):
		checks = [lambda: [_result(PASS, "A", "ok"), _result(WARN, "B", "meh")]]
		self._run_capturing(checks, strict=True)


class TestParseListeningPorts(IntegrationTestCase):
	def test_parses_tcp_and_udp(self):
		out = (
			"Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
			"tcp   LISTEN 0      128    0.0.0.0:80         0.0.0.0:*\n"
			"tcp   LISTEN 0      128    [::]:443           [::]:*\n"
			"udp   UNCONN 0      0      0.0.0.0:51820      0.0.0.0:*\n"
		)
		parsed = _parse_listening_ports(out)
		self.assertEqual(parsed["tcp"], {80, 443})
		self.assertEqual(parsed["udp"], {51820})

	def test_ignores_header_only(self):
		header = "Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
		self.assertEqual(_parse_listening_ports(header), {"tcp": set(), "udp": set()})
