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


def check_row(check: str, ok: bool, hint: str) -> dict:
	"""One check result. Shared by every caller so the shape cannot drift."""
	return {"check": check, "status": "pass" if ok else "fail", "hint": hint}


def display_row(check: dict, label: str) -> dict:
	"""A check row as a screen renders it: a StatusBadge value plus its hint."""
	return {
		"check": check["check"],
		"label": label,
		"status": "Active" if check["status"] == "pass" else "Error",
		"hint": check["hint"],
	}


def run_diagnostics() -> list[dict]:
	"""Read-only environment checks. Each row: {check, status: pass|fail, hint}.

	Never raises and never mutates infrastructure.
	"""
	return [
		_check_docker_socket(),
		_check_docker_network(),
		_check_mariadb(),
		_check_redis(),
		check_vpn_server(),
	]


def _check_docker_socket() -> dict:
	try:
		get_client().ping()
		return check_row("docker_socket", True, "Docker daemon reachable")
	except Exception as e:
		return check_row("docker_socket", False, f"Cannot reach Docker daemon: {e}")


def _check_docker_network() -> dict:
	try:
		get_client().networks.get("benchpress")
		return check_row("docker_network", True, "benchpress network exists")
	except docker.errors.NotFound:
		return check_row(
			"docker_network",
			False,
			"benchpress network missing — it is created automatically on first deploy",
		)
	except Exception as e:
		return check_row("docker_network", False, f"Could not inspect networks: {e}")


def _check_mariadb() -> dict:
	try:
		servers = frappe.get_all(
			"Database Server",
			fields=["name", "status", "container_name"],
			order_by="creation asc",
			limit=1,
		)
		if not servers:
			return check_row(
				"mariadb",
				False,
				"No Database Server record — shared MariaDB is provisioned on first deploy",
			)
		server = servers[0]
		if check_mariadb_health(server.name):
			return check_row("mariadb", True, f"MariaDB responding at {server.container_name}")
		return check_row(
			"mariadb",
			False,
			f"MariaDB at {server.container_name} is not answering SELECT 1 (doc status: {server.status})",
		)
	except Exception as e:
		return check_row("mariadb", False, f"Could not check MariaDB: {e}")


def _check_redis() -> dict:
	try:
		container = get_client().containers.get(REDIS_CONTAINER_NAME)
		if container.status == "running":
			return check_row("redis", True, f"{REDIS_CONTAINER_NAME} is running")
		return check_row("redis", False, f"{REDIS_CONTAINER_NAME} status is {container.status}")
	except docker.errors.NotFound:
		return check_row(
			"redis",
			False,
			f"{REDIS_CONTAINER_NAME} container not found — shared Redis is provisioned on first deploy",
		)
	except Exception as e:
		return check_row("redis", False, f"Could not check Redis: {e}")


def check_vpn_server() -> dict:
	try:
		if "vpn_management" not in frappe.get_installed_apps():
			return check_row("vpn_server", False, "required app vpn_management is not installed")
		if not frappe.db.exists("WireGuard Server", DEFAULT_INTERFACE):
			return check_row(
				"vpn_server",
				False,
				f"WireGuard Server '{DEFAULT_INTERFACE}' is not configured",
			)
		public_key = frappe.db.get_value("WireGuard Server", DEFAULT_INTERFACE, "server_public_key")
		if not public_key:
			return check_row(
				"vpn_server",
				False,
				f"WireGuard Server '{DEFAULT_INTERFACE}' exists but has no server public key — "
				"interface not initialized",
			)
		return check_row("vpn_server", True, f"WireGuard server '{DEFAULT_INTERFACE}' configured")
	except Exception as e:
		return check_row("vpn_server", False, f"Could not check VPN server: {e}")
