# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Everything the Lab detail screen renders, assembled in one call.

The header, the container status card and the connection panels all describe
one lab and the caller's deployment of it, so the lab and its bench are read
together. The bench goes through ``frappe.get_list``, so the registered
``bench_instance_query_conditions`` scopes it: a BenchPress User is told about
their own deployment and never about another owner's health, address or site.

When a run failed, the failing step and its reason are extracted here rather
than parsed out of the raw log in the browser. A run from the current pipeline
names its steps (``deploy_pipeline``), so the failing one is read from that
metadata; runs recorded before it, and image builds — which stream Docker's own
output — still only have `=== … ===` markers, so both are read.
"""

import frappe

from benchpress.credits import config, passes
from benchpress.deploy_pipeline import scan_log

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
		"instance_size": lab.instance_size,
		"memory_limit": lab.memory_limit,
		"cpu_cores": lab.cpu_cores,
		"enable_ssh": lab.enable_ssh,
		"enable_code_server": lab.enable_code_server,
		"credits_per_hour": _rate(lab),
		"apps": [_app_row(app) for app in lab.apps],
		"bench": bench,
		"sites": _sites(bench),
		"failure": _failure(lab, bench),
	}


def _rate(lab) -> float | None:
	"""What deploying this lab costs per hour, or ``None`` when credits are switched off.

	`None` rather than `0` so the screen can tell "credits do not exist here" apart from "this
	size is free", and hide the chip in the first case only.
	"""
	if not config.credits_enabled():
		return None
	size = config.size_for_lab(lab)
	return size.credits_per_hour if size else 0.0


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
	if not benches:
		return None
	bench = benches[0]
	# Whether this instance is prepaid, and until when. One indexed read, and only when credits
	# exist at all — the card that offers the pass is the same card that must not offer a second.
	bench["always_on_until"] = passes.active_pass_until(bench["name"]) if config.credits_enabled() else None
	return bench


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
		return _deploy_failure(bench["name"])
	return None


def _deploy_failure(bench_name: str) -> dict | None:
	"""The last deploy's failure.

	Never redirected to a build's log any more — deploy never builds (Phase 3: it looks up an
	already-built image or fails immediately), so a deploy's own failure is never actually a
	build's.
	"""
	log = _latest_log("Deploy Log", {"bench": bench_name})
	return _failure_payload(log, "deploy") if log else None


def _read_failure(doctype: str, filters: dict, source: str) -> dict | None:
	"""The failing step and reason of the newest matching log, or ``None``."""
	log = _latest_log(doctype, filters)
	return _failure_payload(log, source) if log else None


def _latest_log(doctype: str, filters: dict) -> dict | None:
	"""The newest matching run log, read past the caller's own row scoping.

	Deliberately `get_all`: labs are global recipes, so the build that failed is usually an
	admin's, and `build_log_query_conditions` would empty this banner for everyone else. The
	`Deploy Log` arm needs no scoping either, since `_failure` only ever passes a bench
	`_caller_bench` returned.
	"""
	logs = frappe.get_all(
		doctype,
		filters=filters,
		fields=["name", "message", "timestamp"],
		order_by="timestamp desc",
		limit_page_length=1,
	)
	return logs[0] if logs else None


def _failure_payload(log: dict, source: str) -> dict:
	"""What the banner renders. Only the derived step and reason leave the server — never `message`."""
	step, reason = _parse_failure(log.message or "")
	return {"source": source, "log": log.name, "step": step, "reason": reason}


def _parse_failure(message: str) -> tuple[str, str]:
	"""The last step to open, and the reason the run ended with.

	`scan_log` reads the markers; a run that died without writing a failure
	marker is described by whatever it left behind on its last line.
	"""
	scan = scan_log(message)
	return scan.step, scan.failure or scan.last_line
