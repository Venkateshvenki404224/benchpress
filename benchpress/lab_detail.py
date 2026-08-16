# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Everything the Lab detail screen renders, assembled in one call.

The header, the container status card and the connection panels all describe
one lab and the caller's deployment of it, so the lab and its bench are read
together. The bench goes through ``frappe.get_list``, so the registered
``bench_instance_query_conditions`` scopes it: a BenchPress User is told about
their own deployment and never about another owner's health, address or site.

When a run failed, the failing step and its reason are extracted here rather
than parsed out of the raw log in the browser. Nothing structured is emitted by
the pipeline yet, so the `=== … ===` markers are all there is to read; phase 4
adds real step metadata and ``_parse_failure`` is the single place that changes
when it does.
"""

import re

import frappe

BENCH_FIELDS = [
	"name",
	"bench_name",
	"status",
	"container_health",
	"last_health_check",
	"cpu_usage",
	"memory_usage",
	"container_id",
	"container_ip",
	"wg_ip",
	"domain",
	"site_name",
	"ssh_username",
	"code_server_url",
	"started_at",
	"owner",
]

SITE_FIELDS = ["name", "site_name", "full_domain", "status"]

# `=== Deploy failed: <reason> ===` / `=== Build failed: <reason> ===` end a
# failed run; every other `=== … ===` line opens a step.
FAILED_MARKER = re.compile(r"^===\s*(?:Deploy|Build) failed:\s*(.*?)\s*===$")
STEP_MARKER = re.compile(r"^===\s*(.*?)\s*===$")


def get_lab(name: str) -> dict:
	"""One lab, the caller's deployment of it, and why the last run failed."""
	lab = frappe.get_cached_doc("Lab", name)
	bench = _caller_bench(lab.name)
	return {
		"name": lab.name,
		"lab_id": lab.lab_id,
		"title": lab.title,
		"description": lab.description,
		"frappe_version": lab.frappe_version,
		"status": lab.status,
		"image_tag": lab.image_tag,
		"memory_limit": lab.memory_limit,
		"cpu_cores": lab.cpu_cores,
		"enable_ssh": lab.enable_ssh,
		"enable_code_server": lab.enable_code_server,
		"apps": [_app_row(app) for app in lab.apps],
		"bench": bench,
		"sites": _sites(bench),
		"failure": _failure(lab, bench),
	}


def _app_row(app) -> dict:
	return {
		"app_name": app.app_name,
		"app_label": app.app_label,
		"git_url": app.git_url,
		"branch": app.branch,
	}


def _caller_bench(lab_name: str) -> dict | None:
	"""The caller's most recently touched bench for this lab, or ``None``."""
	benches = frappe.get_list(
		"Bench Instance",
		filters={"lab": lab_name},
		fields=BENCH_FIELDS,
		order_by="modified desc",
		limit_page_length=1,
	)
	return benches[0] if benches else None


def _sites(bench: dict | None) -> list[dict]:
	"""The bench's sites, each with the apps it was actually created with.

	A site's app list can differ from the lab's — the create dialog picks a
	subset — so the child rows are read rather than inferred, once for the whole
	card instead of once per site.
	"""
	if not bench:
		return []
	sites = frappe.get_list(
		"Bench Site",
		filters={"bench": bench["name"]},
		fields=SITE_FIELDS,
		order_by="creation asc",
		limit_page_length=0,
	)
	if not sites:
		return []

	apps = _site_apps([site.name for site in sites])
	for site in sites:
		site.apps = apps.get(site.name, [])
	return sites


def _site_apps(site_names: list[str]) -> dict:
	rows = frappe.get_all(
		"Site App",
		filters={"parent": ("in", site_names)},
		fields=["parent", "app_name"],
		order_by="idx asc",
		parent_doctype="Bench Site",
		limit_page_length=0,
	)
	grouped: dict[str, list[str]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row.app_name)
	return grouped


def _failure(lab, bench: dict | None) -> dict | None:
	"""The step that broke and the reason it gave, or ``None`` when nothing did.

	A broken image build is the root cause of everything downstream, so it wins
	over a failed deploy of the same lab.
	"""
	if lab.status == "Error":
		return _read_failure("Build Log", {"lab": lab.name}, "build")
	if bench and bench.status == "Error":
		return _read_failure("Deploy Log", {"bench": bench.name}, "deploy")
	return None


def _read_failure(doctype: str, filters: dict, source: str) -> dict | None:
	logs = frappe.get_list(
		doctype,
		filters=filters,
		fields=["name", "message"],
		order_by="timestamp desc",
		limit_page_length=1,
	)
	if not logs:
		return None
	step, reason = _parse_failure(logs[0].message or "")
	return {"source": source, "log": logs[0].name, "step": step, "reason": reason}


def _parse_failure(message: str) -> tuple[str, str]:
	"""The last step to open, and the reason the run ended with.

	Cleanup lines carry no `=== … ===` marker, so the last marker that is not
	itself the failure line is the step that was running when the run died.
	"""
	step = ""
	reason = ""
	for line in message.splitlines():
		stripped = line.strip()
		failed = FAILED_MARKER.match(stripped)
		if failed:
			reason = failed.group(1)
			continue
		marker = STEP_MARKER.match(stripped)
		if marker:
			step = marker.group(1)
	return step, reason or _last_line(message)


def _last_line(message: str) -> str:
	"""What a run that died without a failure marker left behind."""
	lines = [line.strip() for line in message.splitlines() if line.strip()]
	return lines[-1] if lines else ""
