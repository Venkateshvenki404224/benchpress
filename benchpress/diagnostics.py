# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Read-only environment diagnostics (issue #97).

Every check wraps an existing primitive and only inspects — never creates,
starts, or repairs anything. `run_diagnostics` structurally cannot throw:
each check catches its own exceptions and reports them as a fail row.
"""

import docker
import frappe

from benchpress.docker_manager import get_client
from benchpress.mariadb_manager import check_mariadb_health
from benchpress.vpn_adapter import DEFAULT_INTERFACE

REDIS_CONTAINER_NAME = "benchpress-redis"


def _row(check: str, ok: bool, hint: str) -> dict:
	return {"check": check, "status": "pass" if ok else "fail", "hint": hint}


def run_diagnostics() -> list[dict]:
	"""Read-only environment checks. Each row: {check, status: pass|fail, hint}.

	Never raises and never mutates infrastructure.
	"""
	return [
		_check_docker_socket(),
		_check_docker_network(),
		_check_mariadb(),
		_check_redis(),
		_check_vpn_server(),
	]


def _check_docker_socket() -> dict:
	try:
		get_client().ping()
		return _row("docker_socket", True, "Docker daemon reachable")
	except Exception as e:
		return _row("docker_socket", False, f"Cannot reach Docker daemon: {e}")


def _check_docker_network() -> dict:
	try:
		get_client().networks.get("benchpress")
		return _row("docker_network", True, "benchpress network exists")
	except docker.errors.NotFound:
		return _row(
			"docker_network",
			False,
			"benchpress network missing — it is created automatically on first deploy",
		)
	except Exception as e:
		return _row("docker_network", False, f"Could not inspect networks: {e}")


def _check_mariadb() -> dict:
	try:
		servers = frappe.get_all(
			"Database Server",
			fields=["name", "status", "container_name"],
			order_by="creation asc",
			limit=1,
		)
		if not servers:
			return _row(
				"mariadb",
				False,
				"No Database Server record — shared MariaDB is provisioned on first deploy",
			)
		server = servers[0]
		if check_mariadb_health(server.name):
			return _row("mariadb", True, f"MariaDB responding at {server.container_name}")
		return _row(
			"mariadb",
			False,
			f"MariaDB at {server.container_name} is not answering SELECT 1 (doc status: {server.status})",
		)
	except Exception as e:
		return _row("mariadb", False, f"Could not check MariaDB: {e}")


def _check_redis() -> dict:
	try:
		container = get_client().containers.get(REDIS_CONTAINER_NAME)
		if container.status == "running":
			return _row("redis", True, f"{REDIS_CONTAINER_NAME} is running")
		return _row("redis", False, f"{REDIS_CONTAINER_NAME} status is {container.status}")
	except docker.errors.NotFound:
		return _row(
			"redis",
			False,
			f"{REDIS_CONTAINER_NAME} container not found — shared Redis is provisioned on first deploy",
		)
	except Exception as e:
		return _row("redis", False, f"Could not check Redis: {e}")


def _check_vpn_server() -> dict:
	try:
		if "vpn_management" not in frappe.get_installed_apps():
			return _row("vpn_server", False, "required app vpn_management is not installed")
		if not frappe.db.exists("WireGuard Server", DEFAULT_INTERFACE):
			return _row(
				"vpn_server",
				False,
				f"WireGuard Server '{DEFAULT_INTERFACE}' is not configured",
			)
		public_key = frappe.db.get_value("WireGuard Server", DEFAULT_INTERFACE, "server_public_key")
		if not public_key:
			return _row(
				"vpn_server",
				False,
				f"WireGuard Server '{DEFAULT_INTERFACE}' exists but has no server public key — "
				"interface not initialized",
			)
		return _row("vpn_server", True, f"WireGuard server '{DEFAULT_INTERFACE}' configured")
	except Exception as e:
		return _row("vpn_server", False, f"Could not check VPN server: {e}")
