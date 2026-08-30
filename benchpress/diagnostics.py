# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Read-only environment diagnostics (issue #97).

Every check wraps an existing primitive and only inspects — never creates,
starts, or repairs anything. `run_diagnostics` structurally cannot throw:
each check catches its own exceptions and reports them as a fail row.
"""

from pathlib import Path

import docker
import frappe
from frappe.query_builder.functions import Now

from benchpress import ingress, placement
from benchpress.docker_events import HEARTBEAT_STALE_SECONDS, heartbeat_value
from benchpress.docker_manager import (
	CONTAINER_RUNTIMES,
	DEFAULT_PIDS_LIMIT,
	get_client,
	host_runtimes,
)
from benchpress.mariadb_manager import (
	REDIS_CONTAINER_NAME,
	check_mariadb_health,
	mariadb_drift,
	redis_drift,
)
from benchpress.vpn_adapter import DEFAULT_INTERFACE

DRIFT_FIX = "Recreate the shared pair: docker compose up -d in benchpress/config"
# What refreshes the route-directory report. Named in every row that has none to read, because a
# row that says only "no report" leaves the reader with nothing to start it.
ROUTE_STATE_FIX = "the scheduler and queue-long refresh it every reconcile pass, so check both"
ROUTE_STATE_UNREPORTED = (
	"No worker has reported on the Traefik route directory yet. The first deploy records it, and "
	f"so does every reconcile pass — until one does, no public URL is verified: {ROUTE_STATE_FIX}"
)
# A row that says a listener is dead without naming what restarts it costs the reader a search.
LISTENER_FIX = "start it with docker compose up -d docker-events"

# Not an operator preference: past this, arithmetic on a stored deadline is wrong.
# Two seconds absorbs MariaDB truncating NOW() to whole seconds; what it catches
# is a timezone difference, which is hours, not drift.
SKEW_TOLERANCE_SECONDS = 2

PROC_SYS = Path("/proc/sys")

# The kernel ceilings a container can read. The neighbour table is not among them:
# /proc/sys/net/ipv4/neigh/default/ does not exist in this network namespace, and a row
# that silently left it out would read as checked and fine.
CONTAINER_VISIBLE_CEILINGS = ("kernel.pty.max", "kernel.pid_max", "net.netfilter.nf_conntrack_max")
TERMINALS_PER_BENCH = 8
PTY_ROOT_RESERVE = 1024
CONNTRACK_PER_BENCH = 256


def check_row(check: str, ok: bool, hint: str, severity: str = "Error") -> dict:
	"""One check result. Shared by every caller so the shape cannot drift.

	`severity` is what a failed row reads as on screen. It exists for the checks whose failure is
	a degraded state rather than a broken one, and only `display_row` looks at it.
	"""
	return {"check": check, "status": "pass" if ok else "fail", "hint": hint, "severity": severity}


def display_row(check: dict, label: str) -> dict:
	"""A check row as a screen renders it: a StatusBadge value plus its hint."""
	return {
		"check": check["check"],
		"label": label,
		"status": "Active" if check["status"] == "pass" else check.get("severity", "Error"),
		"hint": check["hint"],
	}


def run_diagnostics() -> list[dict]:
	"""Read-only environment checks. Each row: {check, status: pass|fail, hint, severity}.

	Never raises and never mutates infrastructure.
	"""
	return [
		_check_docker_socket(),
		_check_docker_network(),
		_check_bridge_capacity(),
		_check_kernel_ceilings(),
		_check_mariadb(),
		_check_clock_skew(),
		_check_redis(),
		_check_container_runtimes(),
		_check_golden_images(),
		_check_docker_events(),
		_check_route_directory(),
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


def _read_sysctl(name: str) -> int | None:
	"""A knob's running value from /proc/sys, or None when it is not in this namespace."""
	try:
		return int(PROC_SYS.joinpath(*name.split(".")).read_text().split()[0])
	except (OSError, ValueError, IndexError):
		return None


def _check_kernel_ceilings() -> dict:
	"""Host-wide limits a dense fleet runs into, read from /proc/sys rather than assumed.

	The targets are `benchpress_devops/host_tuning.py`'s arithmetic sized against one
	bridge's worth of benches, which is what `sudo scripts/tune-host.sh` writes by default.
	Only that script can raise them, and only from the host.
	"""
	try:
		benches = placement.slots_per_bridge()
		targets = {
			"kernel.pty.max": benches * TERMINALS_PER_BENCH + PTY_ROOT_RESERVE,
			"kernel.pid_max": benches * DEFAULT_PIDS_LIMIT,
			"net.netfilter.nf_conntrack_max": benches * CONNTRACK_PER_BENCH,
		}
		running = {name: _read_sysctl(name) for name in CONTAINER_VISIBLE_CEILINGS}
		blind_spot = (
			"The neighbour table is not visible from inside a container — read it on the host "
			"with ./entry.py --check-host"
		)
		low = [
			f"{name} is {running[name] if running[name] is not None else 'unreadable'}, below {targets[name]}"
			for name in CONTAINER_VISIBLE_CEILINGS
			if running[name] is None or running[name] < targets[name]
		]
		if low:
			return check_row(
				"kernel_ceilings",
				False,
				f"{'; '.join(low)} for {benches} benches — raise it on the host with "
				f"sudo scripts/tune-host.sh --benches {benches}. {blind_spot}",
			)
		measured = ", ".join(f"{name} {running[name]}" for name in CONTAINER_VISIBLE_CEILINGS)
		return check_row("kernel_ceilings", True, f"{measured} — enough for {benches} benches. {blind_spot}")
	except Exception as e:
		return check_row("kernel_ceilings", False, f"Could not read kernel ceilings: {e}")


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
		if not check_mariadb_health(server.name):
			return check_row(
				"mariadb",
				False,
				f"MariaDB at {server.container_name} is not answering SELECT 1 (doc status: {server.status})",
			)
		drift, hit_rate = mariadb_drift(server.name)
		summary = f"MariaDB responding at {server.container_name}, buffer pool hit rate {hit_rate}"
		if drift:
			return check_row(
				"mariadb", False, f"{summary}, but {'; '.join(drift)}. {DRIFT_FIX}", severity="Warning"
			)
		return check_row("mariadb", True, f"{summary}, on the declared settings")
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
	"""Running is not enough — a stock Redis is unbounded and never evicts.

	Drift is a Warning, never an Error: the cache still serves every bench, and it stays
	drifted until a human recreates the pair.
	"""
	try:
		container = get_client().containers.get(REDIS_CONTAINER_NAME)
		if container.status != "running":
			return check_row("redis", False, f"{REDIS_CONTAINER_NAME} status is {container.status}")
		drift = redis_drift()
		if drift:
			return check_row(
				"redis",
				False,
				f"{REDIS_CONTAINER_NAME} is running, but {'; '.join(drift)}. {DRIFT_FIX}",
				severity="Warning",
			)
		return check_row("redis", True, f"{REDIS_CONTAINER_NAME} is running on the declared settings")
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


def _check_golden_images() -> dict:
	"""How much of the catalog restores its site instead of creating it.

	Warning, never Error: a lab with no golden deploys exactly as it always has, just slowly.
	The labels come off the image list `cached_tags` already asks Docker for.
	"""
	try:
		from benchpress.golden import golden_tags
		from benchpress.image_cache import cached_tags

		tags = cached_tags()
		if not tags:
			return check_row("golden_images", True, "No lab image is built yet")
		missing = sorted(tags - golden_tags())
		coverage = f"{len(tags) - len(missing)} of {len(tags)} built labs carry a golden dump"
		if missing:
			return check_row(
				"golden_images",
				False,
				f"{coverage} — {', '.join(missing)} build their site from scratch on every deploy. "
				"Rebuild those labs, or run Build golden on each.",
				severity="Warning",
			)
		return check_row("golden_images", True, coverage)
	except Exception as e:
		return check_row("golden_images", False, f"Could not read golden image labels: {e}")


def _check_docker_events() -> dict:
	"""Whether the event listener's heartbeat is fresh enough to be believed.

	A streaming listener that dies looks exactly like a quiet fleet, which the cron it replaced
	never did.
	"""
	try:
		published = heartbeat_value()
		if not published:
			return check_row(
				"docker_events",
				False,
				f"The Docker event listener has published no heartbeat — {LISTENER_FIX}",
			)
		age = published["age"]
		if age > HEARTBEAT_STALE_SECONDS:
			return check_row(
				"docker_events",
				False,
				f"The Docker event listener last reported {age}s ago, past the "
				f"{HEARTBEAT_STALE_SECONDS}s it is given — {LISTENER_FIX}",
			)
		return check_row(
			"docker_events",
			True,
			f"Docker event listener reported {age}s ago, {published['events_seen']} events seen",
		)
	except Exception as e:
		return check_row("docker_events", False, f"Could not read the listener heartbeat: {e}")


def _check_route_directory() -> dict:
	"""Whether the route directory the advertised public URL depends on is mounted and rendered.

	Read from what a worker recorded: this screen renders in `backend`, which never mounts it.
	"""
	# The one check that fails on a stock install: `base_domain` is required, so step 5 of
	# docs/operator/install.mdx advertises `<bench>.<domain>` on a checkout whose queue-long has
	# no route mount, because only docker-compose.prod.yml declares one. Without this row every
	# other check passes on a host where no public URL can ever answer.
	try:
		base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
		if not base_domain or base_domain == "localhost":
			return check_row("route_directory", True, "No public base domain, so no route is published")

		state = ingress.directory_state()
		if not state:
			return check_row("route_directory", False, ROUTE_STATE_UNREPORTED, severity="Warning")
		if state["age"] > ingress.ROUTE_STATE_STALE_SECONDS:
			return check_row(
				"route_directory",
				False,
				f"The route directory was last reported on {state['age']}s ago, past the "
				f"{ingress.ROUTE_STATE_STALE_SECONDS}s it is given — {ROUTE_STATE_FIX}",
				severity="Warning",
			)

		if not state["mounted"]:
			return check_row("route_directory", False, ingress.route_directory_fix())

		missing = state["missing"]
		if ingress.CONTROL_PLANE_ROUTE_FILE in missing:
			# The failure this row exists to name: docker turns a bind source that does not exist
			# into an empty directory, which passes every "is the path there" test there is.
			return check_row(
				"route_directory",
				False,
				f"The route directory holds no {ingress.CONTROL_PLANE_ROUTE_FILE}, so it is an "
				"empty directory docker created for a bind source that was never rendered, not "
				"the mount. Render it on the host: ./entry.py --domain <fqdn>",
			)

		if ingress.WILDCARD_ANCHOR_FILE not in missing:
			return check_row(
				"route_directory",
				True,
				f"{state['published']} bench routes published beside "
				f"{ingress.CONTROL_PLANE_ROUTE_FILE}, *.{base_domain} anchored",
			)
		if not state["published"]:
			return check_row(
				"route_directory",
				True,
				"Route directory mounted and rendered, no bench route published yet — the first "
				f"deploy writes {ingress.WILDCARD_ANCHOR_FILE}",
			)
		# Warning, not Error: every deploy and every reconcile pass writes the anchor, so this is a
		# state that heals itself. Still worth a row, because until it does each of those published
		# hostnames answers on a certificate the browser refuses.
		return check_row(
			"route_directory",
			False,
			f"{state['published']} bench routes are published but no {ingress.WILDCARD_ANCHOR_FILE} "
			f"holds *.{base_domain} in Traefik's certificate store, so those URLs fail TLS. The "
			"next deploy or reconcile pass writes it",
			severity="Warning",
		)
	except Exception as e:
		return check_row("route_directory", False, f"Could not read the route directory report: {e}")


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
