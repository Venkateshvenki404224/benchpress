# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Deploy history: what each past run did and how long it took."""

import frappe

from benchpress.deploy_pipeline import scan_log
from benchpress.overview import LOG_RETENTION_DAYS, format_duration, log_duration, window_start
from benchpress.permissions import require_app_user

# One page of history, with no "load more" in the design behind it. The cap is
# reported rather than applied silently: a table that quietly stops at fifty
# reads as "this is everything".
HISTORY_LIMIT = 50

LOG_FIELDS = ["name", "log_type", "timestamp", "modified", "message"]

# What a run's `log_type` is called in the Result column. Every label here
# resolves to a colour in `statusThemes.js`.
DEPLOY_RESULTS = {"success": "Success", "error": "Failed", "warning": "Skipped"}
DEPLOY_RUNNING = "Deploying"


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


def _deploy_row(log: dict, bench: dict) -> dict:
	"""The lab is what a deploy row is named after — `bench_name` is an md5."""
	return {
		**_run_facts(log),
		"bench": log.bench,
		"lab": bench.get("lab") or "",
		"result": DEPLOY_RESULTS.get(log.log_type) or DEPLOY_RUNNING,
	}


def _run_facts(log: dict) -> dict:
	"""The columns a history row reads from the log the run wrote."""
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


def _benches(bench_names: list[str]) -> dict:
	"""Which lab each run deployed — the rows themselves are already scoped."""
	if not bench_names:
		return {}
	benches = frappe.get_all("Bench Instance", filters={"name": ("in", bench_names)}, fields=["name", "lab"])
	return {bench.name: bench for bench in benches}
