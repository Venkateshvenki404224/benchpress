# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import shutil
import sys

import docker
import frappe

from benchpress import docker_manager

PASS = "pass"
WARN = "warn"
FAIL = "fail"

MIN_CPU_CORES = 2
MIN_RAM_GB = 4
MIN_FREE_DISK_GB = 20

_TAG = {PASS: "[PASS]", WARN: "[WARN]", FAIL: "[FAIL]"}
_ANSI = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m"}
_ANSI_RESET = "\033[0m"


def _result(status: str, name: str, detail: str, fix: str | None = None) -> dict:
	return {"status": status, "name": name, "detail": detail, "fix": fix}


def _threshold_status(value: float, minimum: float) -> str:
	if value < minimum:
		return FAIL
	if value == minimum:
		return WARN
	return PASS


def _evaluate_resources(cpu_count: int, ram_gb: float, free_gb: float) -> list[dict]:
	cpu_status = _threshold_status(cpu_count, MIN_CPU_CORES)
	ram_status = _threshold_status(ram_gb, MIN_RAM_GB)
	disk_status = _threshold_status(free_gb, MIN_FREE_DISK_GB)
	return [
		_result(
			cpu_status,
			"CPU cores",
			f"{cpu_count} detected (minimum {MIN_CPU_CORES})",
			None if cpu_status == PASS else f"provision a host with at least {MIN_CPU_CORES} CPU cores",
		),
		_result(
			ram_status,
			"Memory",
			f"{ram_gb:.1f} GB total (minimum {MIN_RAM_GB} GB)",
			None if ram_status == PASS else f"provision a host with at least {MIN_RAM_GB} GB RAM",
		),
		_result(
			disk_status,
			"Free disk",
			f"{free_gb:.1f} GB free at bench (minimum {MIN_FREE_DISK_GB} GB)",
			None if disk_status == PASS else f"free up disk so at least {MIN_FREE_DISK_GB} GB is available",
		),
	]


def _evaluate_os(os_release: dict, proc_version: str, in_docker: bool) -> dict:
	name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "unknown OS"
	detail = f"{name} (running inside container)" if in_docker else name

	if "microsoft" in proc_version.lower():
		return _result(
			WARN,
			"Operating system",
			f"{detail} on WSL2",
			"run the BenchPress host setup from a native Linux host; WSL2 networking and WireGuard are unreliable",
		)

	distro_id = (os_release.get("ID") or "").lower()
	id_like = (os_release.get("ID_LIKE") or "").lower()
	supported = ("ubuntu", "debian")
	if distro_id in supported or any(s in id_like for s in supported):
		return _result(PASS, "Operating system", detail)
	return _result(
		WARN,
		"Operating system",
		detail,
		"BenchPress is verified on Ubuntu/Debian; other distros may work but are untested",
	)


def _format_report(results: list[dict], env: dict, tty: bool = False) -> str:
	lines = ["BenchPress readiness check"]
	site = env.get("site") or "?"
	bench = env.get("bench") or "?"
	location = "container" if env.get("in_container") else "host"
	lines.append(f"site: {site}  bench: {bench}  running on: {location}")
	lines.append("")

	for r in results:
		tag = _TAG.get(r["status"], "[????]")
		if tty:
			tag = f"{_ANSI.get(r['status'], '')}{tag}{_ANSI_RESET}"
		lines.append(f"{tag} {r['name']}: {r['detail']}")
		if r.get("fix"):
			lines.append(f"        fix: {r['fix']}")

	counts = _summary(results)
	lines.append("")
	lines.append(f"Summary: {counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail")
	return "\n".join(lines)


def _summary(results: list[dict]) -> dict:
	return {
		"pass": sum(1 for r in results if r["status"] == PASS),
		"warn": sum(1 for r in results if r["status"] == WARN),
		"fail": sum(1 for r in results if r["status"] == FAIL),
	}


def _read_text(path: str) -> str:
	try:
		with open(path) as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
			return f.read()
	except OSError:
		return ""


def _read_os_release() -> dict:
	data = {}
	for line in _read_text("/etc/os-release").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		data[key.strip()] = value.strip().strip('"')
	return data


def _read_mem_total_gb() -> float:
	for line in _read_text("/proc/meminfo").splitlines():
		if line.startswith("MemTotal:"):
			parts = line.split()
			if len(parts) >= 2:
				return int(parts[1]) / (1024**2)
	return 0.0


def _bench_dir() -> str:
	return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _check_os() -> list[dict]:
	return [_evaluate_os(_read_os_release(), _read_text("/proc/version"), os.path.exists("/.dockerenv"))]


def _check_resources() -> list[dict]:
	cpu_count = os.cpu_count() or 0
	ram_gb = _read_mem_total_gb()
	try:
		free_gb = shutil.disk_usage(_bench_dir()).free / (1024**3)
	except OSError:
		free_gb = 0.0
	return _evaluate_resources(cpu_count, ram_gb, free_gb)


def _check_docker() -> list[dict]:
	try:
		client = docker_manager.get_client()
		client.ping()
		server_version = client.version().get("Version", "unknown")
		return [_result(PASS, "Docker daemon", f"reachable, server version {server_version}")]
	except (docker.errors.DockerException, OSError) as e:
		return [
			_result(
				FAIL,
				"Docker daemon",
				f"unreachable: {e}",
				"sudo systemctl start docker — if permission denied: sudo usermod -aG docker $USER, then log out and back in",
			)
		]


def _check_frappe() -> list[dict]:
	installed = "benchpress" in frappe.get_installed_apps()
	results = [
		_result(
			PASS if installed else FAIL,
			"BenchPress app",
			"installed on site" if installed else "not installed on this site",
			None if installed else "bench --site <site> install-app benchpress",
		)
	]

	try:
		frappe.get_cached_doc("BenchPress Settings")
		results.append(_result(PASS, "BenchPress Settings", "singleton loads"))
	except frappe.DoesNotExistError as e:
		results.append(
			_result(FAIL, "BenchPress Settings", f"could not load: {e}", "bench --site <site> migrate")
		)

	site = getattr(frappe.local, "site", None)
	results.append(
		_result(
			PASS if site else FAIL,
			"Site context",
			f"bound to '{site}'" if site else "no site bound",
			None if site else "invoke within a site: bench --site <site> execute benchpress.doctor.run",
		)
	)
	return results


CHECKS = [_check_os, _check_resources, _check_docker, _check_frappe]


def run(as_json: bool = False, strict: bool = False):
	"""Print a host-readiness report (pass/warn/fail) for BenchPress."""
	results = []
	for check in CHECKS:
		try:
			results.extend(check())
		except Exception as e:
			frappe.log_error(title=f"doctor check failed: {check.__name__}", message=frappe.get_traceback())
			results.append(_result(FAIL, check.__name__, f"check raised an unexpected error: {e}"))

	env = {
		"site": getattr(frappe.local, "site", None),
		"bench": _bench_dir(),
		"in_container": os.path.exists("/.dockerenv"),
	}
	print(_format_report(results, env, tty=sys.stdout.isatty()))
	return None
