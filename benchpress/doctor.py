# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import shutil
import subprocess
import sys

import docker
import frappe

from benchpress import docker_manager, traefik_manager, wg_manager
from benchpress.wg_manager import WG_INTERFACE

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


def _in_docker() -> bool:
	return os.path.exists("/.dockerenv")


def _skipped(name: str) -> dict:
	return _result(WARN, name, "skipped (run on the host)")


def _run(cmd: list[str]):
	try:
		return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
	except (subprocess.SubprocessError, OSError) as e:
		frappe.log_error(title=f"doctor subprocess failed: {cmd[0]}", message=str(e))
		return None


def _settings():
	try:
		return frappe.get_cached_doc("BenchPress Settings")
	except frappe.DoesNotExistError:
		return None


def _compose_path() -> str:
	return os.path.join(frappe.get_app_path("benchpress"), "config", "docker-compose.yml")


def _network_subnet(attrs: dict) -> str:
	for cfg in (attrs.get("IPAM") or {}).get("Config") or []:
		if cfg.get("Subnet"):
			return cfg["Subnet"]
	return ""


def _port_from_addr(addr: str) -> int | None:
	port = addr.rpartition(":")[2]
	try:
		return int(port)
	except ValueError:
		return None


def _parse_listening_ports(ss_output: str) -> dict:
	tcp, udp = set(), set()
	for line in ss_output.splitlines():
		parts = line.split()
		if len(parts) < 5:
			continue
		port = _port_from_addr(parts[4])
		if port is None:
			continue
		proto = parts[0].lower()
		if proto.startswith("tcp"):
			tcp.add(port)
		elif proto.startswith("udp"):
			udp.add(port)
	return {"tcp": tcp, "udp": udp}


def _container_is_running(name: str) -> bool:
	try:
		return (docker_manager.get_client().containers.get(name).status or "").lower() == "running"
	except (docker.errors.DockerException, OSError):  # best-effort
		return False


def _wireguard_kernel_available() -> bool:
	if os.path.exists("/sys/module/wireguard"):
		return True
	proc = _run(["modprobe", "-n", "wireguard"])
	return proc is not None and proc.returncode == 0


def _check_os() -> list[dict]:
	return [_evaluate_os(_read_os_release(), _read_text("/proc/version"), _in_docker())]


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


def _evaluate_compose(ok: bool, version: str) -> dict:
	if ok:
		return _result(PASS, "Docker Compose", version or "v2 available")
	return _result(
		FAIL,
		"Docker Compose",
		"docker compose v2 not available",
		"sudo apt-get install docker-compose-plugin",
	)


def _evaluate_docker_network(found: bool, subnet: str) -> dict:
	fix = "bash apps/benchpress/setup.sh <site>  (step 2 creates the benchpress network)"
	if not found:
		return _result(FAIL, "Docker network", "'benchpress' network not found", fix)
	if subnet == "172.30.0.0/24":
		return _result(PASS, "Docker network", f"'benchpress' present ({subnet})")
	return _result(
		WARN,
		"Docker network",
		f"'benchpress' present but subnet is {subnet or 'unknown'} (expected 172.30.0.0/24)",
		fix,
	)


def _evaluate_container(name: str, status: str | None, down_severity: str, fix: str) -> dict:
	label = f"Container {name}"
	if (status or "").lower() == "running":
		return _result(PASS, label, "running")
	return _result(down_severity, label, f"status: {status or 'not found'}", fix)


def _evaluate_ip_forward(value: str) -> dict:
	if value.strip() == "1":
		return _result(PASS, "IP forwarding", "net.ipv4.ip_forward = 1")
	return _result(
		FAIL,
		"IP forwarding",
		f"net.ipv4.ip_forward = {value.strip() or 'unknown'}",
		"sudo sysctl -w net.ipv4.ip_forward=1",
	)


def _evaluate_sudoers(file_exists: bool, sudo_ok: bool) -> dict:
	fix = "bash apps/benchpress/setup.sh <site>  (step 5)"
	if not file_exists:
		return _result(FAIL, "Sudoers", "/etc/sudoers.d/benchpress missing", fix)
	if not sudo_ok:
		return _result(FAIL, "Sudoers", "sudoers present but 'sudo -n wg show' failed", fix)
	return _result(PASS, "Sudoers", "passwordless sudo for wg works")


def _evaluate_wireguard_tools(have_wg: bool, have_wg_quick: bool, kernel: bool) -> dict:
	fix = "bash apps/benchpress/setup.sh <site>  (step 6)"
	missing = [t for t, ok in (("wg", have_wg), ("wg-quick", have_wg_quick)) if not ok]
	if missing:
		return _result(WARN, "WireGuard tools", f"missing: {', '.join(missing)} (VPN features disabled)", fix)
	if not kernel:
		return _result(WARN, "WireGuard tools", "wg + wg-quick installed but kernel module not loadable", fix)
	return _result(PASS, "WireGuard tools", "wg + wg-quick installed, kernel module available")


def _evaluate_wg_interface(up: bool, listen_port: str, expected: str) -> dict:
	if not up:
		return _result(
			WARN, "WireGuard interface", f"{WG_INTERFACE} is not up", f"sudo wg-quick up {WG_INTERFACE}"
		)
	if listen_port and listen_port != expected:
		return _result(
			WARN,
			"WireGuard interface",
			f"{WG_INTERFACE} up but listening on {listen_port} (settings expect {expected})",
			"align wg_server_port in BenchPress Settings, then restart the interface",
		)
	return _result(PASS, "WireGuard interface", f"{WG_INTERFACE} up, listening on {listen_port or expected}")


def _evaluate_http_port(port: int, in_use: bool, traefik_up: bool) -> dict:
	name = f"Port {port}/tcp"
	if not in_use:
		return _result(PASS, name, "free")
	if traefik_up:
		return _result(PASS, name, "in use by Traefik")
	return _result(
		WARN,
		name,
		"in use by another process",
		f"free port {port} or stop the conflicting service before enabling public routing",
	)


def _evaluate_wg_port(port: int, bound: bool) -> dict:
	name = f"Port {port}/udp (WireGuard)"
	if bound:
		return _result(PASS, name, "bound")
	return _result(WARN, name, "not bound (WireGuard VPN unreachable)", f"sudo ufw allow {port}/udp")


def _check_compose() -> list[dict]:
	proc = _run(["docker", "compose", "version"])
	ok = proc is not None and proc.returncode == 0
	version = proc.stdout.strip().splitlines()[0] if ok and proc.stdout.strip() else ""
	return [_evaluate_compose(ok, version)]


def _check_docker_network() -> list[dict]:
	try:
		net = docker_manager.get_client().networks.get("benchpress")
	except docker.errors.NotFound:
		return [_evaluate_docker_network(False, "")]
	except (docker.errors.DockerException, OSError) as e:
		return [
			_result(
				FAIL,
				"Docker network",
				f"could not query Docker networks: {e}",
				"ensure the Docker daemon is reachable, then re-run",
			)
		]
	return [_evaluate_docker_network(True, _network_subnet(net.attrs))]


def _check_infra_containers() -> list[dict]:
	settings = _settings()
	fix = f"docker compose -f {_compose_path()} up -d"
	required = [("benchpress-mariadb", FAIL), ("benchpress-redis", FAIL)]
	if settings is not None and traefik_manager.routing_enabled(settings):
		required.append(("benchpress-traefik", WARN))

	try:
		client = docker_manager.get_client()
	except (docker.errors.DockerException, OSError) as e:
		return [_result(sev, f"Container {name}", f"Docker unreachable: {e}", fix) for name, sev in required]

	results = []
	for name, sev in required:
		try:
			status = client.containers.get(name).status
		except docker.errors.NotFound:
			status = None
		except (docker.errors.DockerException, OSError) as e:
			results.append(_result(sev, f"Container {name}", f"could not query: {e}", fix))
			continue
		results.append(_evaluate_container(name, status, sev, fix))
	return results


def _check_ip_forward() -> list[dict]:
	if _in_docker():
		return [_skipped("IP forwarding")]
	return [_evaluate_ip_forward(_read_text("/proc/sys/net/ipv4/ip_forward"))]


def _check_sudoers() -> list[dict]:
	if _in_docker():
		return [_skipped("Sudoers")]
	file_exists = os.path.exists("/etc/sudoers.d/benchpress")
	sudo_ok = False
	if file_exists:
		proc = _run(["sudo", "-n", "wg", "show"])
		sudo_ok = proc is not None and proc.returncode == 0
	return [_evaluate_sudoers(file_exists, sudo_ok)]


def _check_wireguard_tools() -> list[dict]:
	have_wg = wg_manager._wg_available()
	have_wg_quick = shutil.which("wg-quick") is not None
	kernel = have_wg and have_wg_quick and _wireguard_kernel_available()
	return [_evaluate_wireguard_tools(have_wg, have_wg_quick, kernel)]


def _check_wg_interface() -> list[dict]:
	if _in_docker():
		return [_skipped("WireGuard interface")]
	proc = _run(["sudo", "-n", "wg", "show", WG_INTERFACE, "listen-port"])
	up = proc is not None and proc.returncode == 0
	listen_port = proc.stdout.strip() if up else ""
	settings = _settings()
	expected = str(settings.wg_server_port or 51820) if settings is not None else "51820"
	return [_evaluate_wg_interface(up, listen_port, expected)]


def _check_ports() -> list[dict]:
	if _in_docker():
		return [_skipped("Ports / firewall")]
	proc = _run(["ss", "-ltnu"])
	if proc is None or proc.returncode != 0:
		return [
			_result(
				WARN,
				"Ports / firewall",
				"could not enumerate listening sockets",
				"install iproute2 so 'ss' is available, then re-run",
			)
		]
	listening = _parse_listening_ports(proc.stdout)
	traefik_up = _container_is_running("benchpress-traefik")
	results = [_evaluate_http_port(p, p in listening["tcp"], traefik_up) for p in (80, 443)]
	settings = _settings()
	wg_port = int(settings.wg_server_port or 51820) if settings is not None else 51820
	results.append(_evaluate_wg_port(wg_port, wg_port in listening["udp"]))
	return results


CHECKS = [
	_check_os,
	_check_resources,
	_check_docker,
	_check_frappe,
	_check_compose,
	_check_docker_network,
	_check_infra_containers,
	_check_ip_forward,
	_check_sudoers,
	_check_wireguard_tools,
	_check_wg_interface,
	_check_ports,
]


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
		"in_container": _in_docker(),
	}

	if as_json:
		print(frappe.as_json(results))
	else:
		print(_format_report(results, env, tty=sys.stdout.isatty()))

	if strict and _summary(results)["fail"]:
		raise SystemExit(1)
	return None
