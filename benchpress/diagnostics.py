# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Read-only environment diagnostics (issue #97).

Every check wraps an existing primitive and only inspects — never creates,
starts, or repairs anything. `run_diagnostics` structurally cannot throw:
each check catches its own exceptions and reports them as a fail row.
"""

import docker
import frappe
from frappe.query_builder.functions import Now

from benchpress import placement
from benchpress.docker_manager import CONTAINER_RUNTIMES, get_client, host_runtimes
from benchpress.mariadb_manager import check_mariadb_health
from benchpress.vpn_adapter import DEFAULT_INTERFACE

REDIS_CONTAINER_NAME = "benchpress-redis"

# Not an operator preference: past this, arithmetic on a stored deadline is wrong.
# Two seconds absorbs MariaDB truncating NOW() to whole seconds; what it catches
# is a timezone difference, which is hours, not drift.
SKEW_TOLERANCE_SECONDS = 2


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
		_check_bridge_capacity(),
		_check_mariadb(),
		_check_clock_skew(),
		_check_redis(),
		_check_container_runtimes(),
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


def _check_bridge_capacity() -> dict:
	"""How much room the bench bridge family has left, counted rather than assumed.

	Inspects and nothing else: a bridge that does not exist yet is absent from the report
	rather than created, which is what this module promises and what keeps the family lazy.
	"""
	try:
		usage = placement.bridge_usage()
		if not usage:
			return check_row("bridge_capacity", True, "No bench bridge exists yet")
		per_bridge = ", ".join(f"{row['network']} {row['used']} used / {row['free']} free" for row in usage)
		headroom = placement.headroom(usage)
		return check_row("bridge_capacity", headroom > 0, f"{per_bridge} — {headroom} benches of headroom")
	except Exception as e:
		return check_row("bridge_capacity", False, f"Could not measure bridge capacity: {e}")


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


def _check_clock_skew() -> dict:
	"""Frappe writes Datetimes naive in the site timezone; SQL NOW() answers in the database's.

	A gap between the two silently lengthens every deadline comparison SQL evaluates.
	"""
	try:
		app_clock = frappe.utils.now_datetime()
		db_clock = frappe.qb.select(Now()).run()[0][0]
		skew = abs((app_clock - db_clock).total_seconds())
		if skew <= SKEW_TOLERANCE_SECONDS:
			return check_row("clock_skew", True, f"App and database clocks agree to within {skew:.0f}s")
		return check_row(
			"clock_skew",
			False,
			f"App clock says {app_clock:%Y-%m-%d %H:%M:%S} and the database says "
			f"{db_clock:%Y-%m-%d %H:%M:%S} — a gap of {skew:.0f}s. Compare stored deadlines "
			"against an epoch integer bound in Python, never against SQL NOW()",
		)
	except Exception as e:
		return check_row("clock_skew", False, f"Could not compare the app and database clocks: {e}")


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


def _check_container_runtimes() -> dict:
	"""Registered, not working — proving one runs takes `preflight_runtime`."""
	required = sorted(name for name in CONTAINER_RUNTIMES.values() if name)
	try:
		missing = [name for name in required if name not in host_runtimes()["names"]]
		if missing:
			return check_row(
				"container_runtimes",
				False,
				f"Docker has no {', '.join(missing)} — benches on that runtime cannot deploy",
			)
		return check_row("container_runtimes", True, f"Docker has {', '.join(required)} registered")
	except Exception as e:
		return check_row("container_runtimes", False, f"Could not read Docker runtimes: {e}")


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
