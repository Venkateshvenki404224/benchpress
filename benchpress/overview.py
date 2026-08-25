# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Everything the Overview screen renders, assembled in one request.

Status counts, the average deploy time, the caller's environments, the recent
activity feed and — for admins only — shared infrastructure. Reads are
batched: one query per collection, never a `get_doc` inside a loop. Scoping is
never reimplemented here; bench rows reuse `get_bench_owner_filter()` and the
activity feed goes through `frappe.get_list`, so the registered
`deploy_log_query_conditions` applies.
"""

import frappe
from frappe import _
from frappe.utils.data import add_days, cint, now_datetime, time_diff_in_seconds

from benchpress.hooks import default_log_clearing_doctypes
from benchpress.labs import bench_label
from benchpress.permissions import get_bench_owner_filter, is_admin

ENVIRONMENT_LIMIT = 6
ACTIVITY_LIMIT = 6
DEPLOY_SAMPLE_LIMIT = 50
FINISHED_LOG_TYPES = ("success", "error")
# Deploy and build history are cleared on this horizon, so no statistic drawn
# from them may claim a longer window.
LOG_RETENTION_DAYS = default_log_clearing_doctypes["Deploy Log"]

INFRASTRUCTURE_LABELS = {
	"docker_socket": "Docker socket",
	"docker_network": "Docker network",
	"bridge_capacity": "Bridge capacity",
	"mariadb": "MariaDB",
	"clock_skew": "Clock skew",
	"redis": "Redis",
	"container_runtimes": "Container runtimes",
	"vpn_server": "WireGuard",
}


def get_overview() -> dict:
	"""The whole Overview screen for the session user."""
	admin = is_admin()
	environments = _load_environments()
	return {
		"is_admin": admin,
		"first_name": _first_name(),
		"counts": _counts(environments),
		"deploy_time": _average_deploy_time(),
		"environments": environments[:ENVIRONMENT_LIMIT],
		"environment_count": len(environments),
		"activity": _activity(admin),
		"infrastructure": _infrastructure(admin),
	}


def _first_name() -> str:
	return frappe.db.get_value("User", frappe.session.user, "first_name") or ""


def _counts(environments: list[dict]) -> dict:
	return {
		"total": len(environments),
		"running": sum(1 for row in environments if row.status == "Running"),
		"stopped": sum(1 for row in environments if row.status == "Stopped"),
		"needs_attention": sum(1 for row in environments if _needs_attention(row)),
	}


def _needs_attention(environment: dict) -> bool:
	return environment.status == "Error" or environment.container_health == "Unhealthy"


def _load_environments() -> list[dict]:
	"""The caller's benches — every bench for an admin — with lab, site and app."""
	benches = frappe.get_all(
		"Bench Instance",
		filters=get_bench_owner_filter(),
		fields=[
			"name",
			"bench_name",
			"lab",
			"status",
			"container_health",
			"domain",
			"site_name",
			"wg_ip",
			"owner",
		],
		order_by="modified desc",
	)
	if not benches:
		return []

	lab_titles = _lab_titles([bench.lab for bench in benches])
	sites = _primary_sites([bench.name for bench in benches])
	apps = _primary_apps([bench.name for bench in benches])
	for bench in benches:
		bench.lab_title = lab_titles.get(bench.lab) or bench.lab
		bench.app = apps.get(bench.name) or "frappe"
		bench.site = _site_label(bench, sites.get(bench.name))
		bench.site_status = sites.get(bench.name, {}).get("status") or ""
	return benches


def _site_label(bench: dict, site: dict | None) -> str:
	if site:
		return site.get("full_domain") or site.get("site_name") or ""
	return bench.domain or bench.site_name or ""


def _lab_titles(lab_names: list[str]) -> dict:
	labs = frappe.get_all("Lab", filters={"name": ("in", lab_names)}, fields=["name", "title"])
	return {lab.name: lab.title for lab in labs}


def _primary_sites(bench_names: list[str]) -> dict:
	"""The first site of each bench, keyed by bench."""
	sites = frappe.get_all(
		"Bench Site",
		filters={"bench": ("in", bench_names)},
		fields=["bench", "site_name", "full_domain", "status"],
		order_by="creation asc",
	)
	primary = {}
	for site in sites:
		primary.setdefault(site.bench, site)
	return primary


def _primary_apps(bench_names: list[str]) -> dict:
	"""The app whose icon represents each bench — the first one that is not frappe."""
	rows = frappe.get_all(
		"Bench App",
		filters={"parent": ("in", bench_names)},
		fields=["parent", "app_name"],
		order_by="idx asc",
		parent_doctype="Bench Instance",
	)
	primary = {}
	for row in rows:
		if row.app_name and row.app_name.lower() != "frappe":
			primary.setdefault(row.parent, row.app_name)
	return primary


def window_start():
	"""The oldest timestamp the screen may speak for.

	Log clearing only runs when the scheduler does, so rows older than the
	retention horizon can still be in the table. Filtering explicitly keeps
	every window claim true whether or not the cron ran.
	"""
	return add_days(now_datetime(), -LOG_RETENTION_DAYS)


def _average_deploy_time() -> dict:
	"""Mean duration of finished deploys, bounded by log retention."""
	logs = frappe.get_list(
		"Deploy Log",
		filters={
			"log_type": ("in", FINISHED_LOG_TYPES),
			"timestamp": (">=", window_start()),
		},
		fields=["timestamp", "modified"],
		order_by="timestamp desc",
		limit=DEPLOY_SAMPLE_LIMIT,
	)
	durations = [duration for log in logs if (duration := log_duration(log))]
	average = sum(durations) / len(durations) if durations else None
	return {
		"average_seconds": average,
		"average_label": format_duration(average) if average else None,
		"sample_size": len(durations),
		"window_days": LOG_RETENTION_DAYS,
	}


def log_duration(log: dict) -> float | None:
	"""A run lasts from its timestamp to the write that settled its log_type."""
	if not (log.timestamp and log.modified):
		return None
	seconds = time_diff_in_seconds(log.modified, log.timestamp)
	return seconds if seconds > 0 else None


def format_duration(seconds: float | None) -> str:
	if not seconds:
		return ""
	total = cint(round(seconds))
	if total < 60:
		return f"{total}s"
	minutes, remaining = divmod(total, 60)
	if minutes < 60:
		return f"{minutes}m {remaining}s"
	hours, minutes = divmod(minutes, 60)
	return f"{hours}h {minutes}m"


def _activity(admin: bool) -> list[dict]:
	"""Deploy activity for everyone; build activity for admins only.

	Build Log carries no permission query condition, so including it for a
	non-admin would leak every other user's builds.
	"""
	events = _deploy_events()
	if admin:
		events += _build_events()
	events.sort(key=lambda event: event["timestamp"], reverse=True)
	return events[:ACTIVITY_LIMIT]


def _deploy_events() -> list[dict]:
	logs = frappe.get_list(
		"Deploy Log",
		filters={"timestamp": (">=", window_start())},
		fields=["name", "bench", "log_type", "timestamp", "modified"],
		order_by="timestamp desc",
		limit=ACTIVITY_LIMIT,
	)
	labels = _bench_labels([log.bench for log in logs])
	return [_deploy_event(log, labels.get(log.bench) or log.bench) for log in logs]


def _deploy_event(log: dict, subject: str) -> dict:
	messages = {
		"success": _("{0} deployed in {1}").format(subject, format_duration(log_duration(log))),
		"error": _("{0} deploy failed").format(subject),
		"warning": _("{0} deploy skipped — another deploy was already running").format(subject),
	}
	return {
		"message": messages.get(log.log_type) or _("{0} is deploying").format(subject),
		"log_type": log.log_type,
		"timestamp": log.timestamp,
		"bench": log.bench,
	}


def _build_events() -> list[dict]:
	logs = frappe.get_list(
		"Build Log",
		filters={"timestamp": (">=", window_start())},
		fields=["name", "lab", "log_type", "timestamp", "modified"],
		order_by="timestamp desc",
		limit=ACTIVITY_LIMIT,
	)
	return [_build_event(log) for log in logs]


def _build_event(log: dict) -> dict:
	messages = {
		"success": _("{0} image built in {1}").format(log.lab, format_duration(log_duration(log))),
		"error": _("{0} image build failed").format(log.lab),
	}
	return {
		"message": messages.get(log.log_type) or _("{0} started building").format(log.lab),
		"log_type": log.log_type,
		"timestamp": log.timestamp,
		"lab": log.lab,
	}


def _bench_labels(bench_names: list[str]) -> dict:
	"""Activity reads as sentences, so a bench is named after its lab, not its md5."""
	benches = frappe.get_all("Bench Instance", filters={"name": ("in", bench_names)}, fields=["name", "lab"])
	return {bench.name: bench_label(bench.lab) for bench in benches}


def _infrastructure(admin: bool) -> list[dict] | None:
	"""The eight real diagnostics checks — admins only, never a placeholder."""
	if not admin:
		return None
	from benchpress.diagnostics import display_row, run_diagnostics

	return [
		display_row(check, INFRASTRUCTURE_LABELS.get(check["check"], check["check"]))
		for check in run_diagnostics()
	]
