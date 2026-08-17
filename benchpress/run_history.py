# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Build history and deploy history — two tables of the same shape.

Both answer the same four questions about a past run: did it work, how far did
it get, how long did it take, and when did it start. The screens differ only in
what a run is *of*, so the row shape is shared and the two loaders below differ
only in their source.

**Why these are endpoints rather than a `frappe.client.get_list`.** The SPA used
to read `Build Log` through the generic list API, and `Build Log` carries no
permission query condition — a `BenchPress User` was served every other user's
image builds. Scoping cannot be added to a generic read, so it is added here:
deploy runs go through ``frappe.get_list`` and pick up the registered
``deploy_log_query_conditions``, and build runs are filtered by owner for
anyone who is not an admin.

**Retention.** Log clearing drops both doctypes after seven days, so neither
table is a complete record. The window is applied in the query rather than left
to the cron — clearing only runs when the scheduler does, so older rows can
still be in the table, and a run whose neighbours have been cleared cannot be
compared against anything. The horizon is returned with the rows so the screen
states it instead of implying completeness.
"""

import re

import frappe

from benchpress.deploy_pipeline import scan_log
from benchpress.overview import LOG_RETENTION_DAYS, format_duration, log_duration, window_start
from benchpress.permissions import is_admin, require_app_user

# One page of history, with no "load more" in the design behind it. The cap is
# reported rather than applied silently: a table that quietly stops at fifty
# reads as "this is everything".
HISTORY_LIMIT = 50

LOG_FIELDS = ["name", "log_type", "timestamp", "modified", "message"]

# What a run's `log_type` is called in the Result column. The two sources word
# their in-progress state differently — an image is building, a bench is
# deploying — and every label here resolves to a colour in `statusThemes.js`.
BUILD_RESULTS = {"success": "Success", "error": "Failed", "warning": "Skipped"}
DEPLOY_RESULTS = {"success": "Success", "error": "Failed", "warning": "Skipped"}
BUILD_RUNNING = "Building"
DEPLOY_RUNNING = "Deploying"

# `docker_manager.build_lab_image` opens with "Building image <tag> (base: …)"
# and `deploy_manager.build_lab` closes with "=== Build complete: <tag> ===".
IMAGE_TAG_LINE = re.compile(r"(?:Build complete:|Building image)\s+(\S+)")


def get_build_history() -> dict:
	"""Image builds — every lab's for an admin, the caller's own otherwise."""
	require_app_user()
	logs = frappe.get_list(
		"Build Log",
		filters=_build_filters(),
		fields=["lab", *LOG_FIELDS],
		order_by="timestamp desc",
		limit=HISTORY_LIMIT + 1,
	)
	labs = _labs(sorted({log.lab for log in logs if log.lab}))
	rows = [_build_row(log, labs.get(log.lab, {})) for log in logs[:HISTORY_LIMIT]]
	return _history(rows, truncated=len(logs) > HISTORY_LIMIT)


def get_deploy_history() -> dict:
	"""Deploys of the benches the caller may see."""
	require_app_user()
	logs = frappe.get_list(
		"Deploy Log",
		filters={"timestamp": (">=", window_start())},
		fields=["bench", *LOG_FIELDS],
		order_by="timestamp desc",
		limit=HISTORY_LIMIT + 1,
	)
	benches = _benches(sorted({log.bench for log in logs if log.bench}))
	rows = [_deploy_row(log, benches.get(log.bench, {})) for log in logs[:HISTORY_LIMIT]]
	return _history(rows, truncated=len(logs) > HISTORY_LIMIT)


def _history(rows: list[dict], truncated: bool) -> dict:
	return {
		"rows": rows,
		"window_days": LOG_RETENTION_DAYS,
		"limit": HISTORY_LIMIT,
		"truncated": truncated,
	}


def _build_filters() -> dict:
	"""Build Log has no query condition of its own, so ownership is applied here."""
	filters = {"timestamp": (">=", window_start())}
	if not is_admin():
		filters["owner"] = frappe.session.user
	return filters


def _build_row(log: dict, lab: dict) -> dict:
	return {
		**_run_facts(log),
		"lab": log.lab,
		"lab_title": lab.get("title") or log.lab or "",
		"image_tag": _image_tag(log.message or "") or lab.get("image_tag") or "",
		"result": BUILD_RESULTS.get(log.log_type) or BUILD_RUNNING,
	}


def _image_tag(message: str) -> str:
	"""The tag this run built, as the run itself named it.

	The build logs the tag on its first line and again on its last, so even a
	failed run carries it. The lab's own `image_tag` is the fallback, and it is
	only ever empty when no build of that lab has succeeded.
	"""
	match = IMAGE_TAG_LINE.search(message)
	return match.group(1) if match else ""


def _deploy_row(log: dict, bench: dict) -> dict:
	"""The lab is what a deploy row is named after — `bench_name` is an md5."""
	return {
		**_run_facts(log),
		"bench": log.bench,
		"lab": bench.get("lab") or "",
		"result": DEPLOY_RESULTS.get(log.log_type) or DEPLOY_RUNNING,
	}


def _run_facts(log: dict) -> dict:
	"""The three columns both tables share, read from the log the run wrote.

	Duration prefers the run's own clock: a pipeline that reached its terminal
	step wrote the total elapsed time into that marker, measured rather than
	inferred. Runs without one — image builds, and deploys recorded before the
	pipeline emitted step metadata — fall back to the span between the first
	line and the write that settled the outcome, and a run still in flight has
	no duration at all rather than a growing guess.
	"""
	scan = scan_log(log.message or "")
	seconds = scan.elapsed if scan.completed and scan.elapsed is not None else _finished_duration(log)
	return {
		"name": log.name,
		"last_step": scan.step,
		"duration_seconds": seconds,
		"duration_label": format_duration(seconds),
		"started": log.timestamp,
		"log_type": log.log_type,
	}


def _finished_duration(log: dict) -> float | None:
	if log.log_type not in ("success", "error", "warning"):
		return None
	return log_duration(log)


def _labs(lab_names: list[str]) -> dict:
	if not lab_names:
		return {}
	labs = frappe.get_all("Lab", filters={"name": ("in", lab_names)}, fields=["name", "title", "image_tag"])
	return {lab.name: lab for lab in labs}


def _benches(bench_names: list[str]) -> dict:
	"""Which lab each run deployed — the rows themselves are already scoped."""
	if not bench_names:
		return {}
	benches = frappe.get_all("Bench Instance", filters={"name": ("in", bench_names)}, fields=["name", "lab"])
	return {bench.name: bench for bench in benches}
