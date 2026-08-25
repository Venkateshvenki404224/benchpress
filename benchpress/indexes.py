# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Composite indexes the DocType JSONs cannot declare.

`search_index` on a field produces a single-column index only, and Frappe does not index Link
fields on its own — so every filter below was a full table scan. Each index here is named by the
query that needs it; `add_index` is idempotent, so this is safe on every install and from a patch.
"""

import frappe


def ensure_indexes() -> None:
	ensure_lab_index()
	ensure_bench_site_index()
	ensure_log_indexes()
	ensure_lease_sweep_index()


def ensure_lab_index() -> None:
	"""`lab_templates._labs_by_template`: the newest lab per template, on every Templates load.

	Filtering on `template` and sorting by `creation` was a scan plus a filesort of the whole
	table to produce one row per template.
	"""
	frappe.db.add_index("Lab", ["template", "creation"])


def ensure_bench_site_index() -> None:
	"""Everything that reads a bench's sites, which is now every deploy.

	`_record_primary_site` looks a row up by exactly this pair, and the `bench` prefix serves the
	site counts, the Sites tab, the teardown sweep and the database drop.
	"""
	frappe.db.add_index("Bench Site", ["bench", "site_name"])


def ensure_log_indexes() -> None:
	"""The two log tables, each read by its scoping column and shown newest first.

	`Build Log` is read by lab on the lab page and by owner in the run history, and its owner is
	now also its permission rule, so both orders earn an index. `Deploy Log` is only ever read
	one bench at a time.
	"""
	frappe.db.add_index("Build Log", ["lab", "owner"])
	frappe.db.add_index("Build Log", ["owner", "timestamp"])
	frappe.db.add_index("Deploy Log", ["bench", "timestamp"])


def ensure_lease_sweep_index() -> None:
	"""The lease sweep's priority queue: equality on the state, then a sorted range.

	`lease_state` narrows the scan, `expires_at_ts` leaves the due rows already ordered, and the
	`LIMIT` stops early — so the cost is the batch, not the fleet. Claimed rows move to
	`Stopping` and leave the range entirely. Measured at 100k rows: `type=range`, 0.26 ms,
	200 rows read for a 200-row batch.
	"""
	frappe.db.add_index("Bench Instance", ["lease_state", "expires_at_ts"])
