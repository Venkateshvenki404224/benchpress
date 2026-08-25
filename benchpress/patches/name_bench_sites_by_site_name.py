# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Move `Bench Site` onto its site name as a primary key, which is the constraint that was missing.

`site_name` keys a MariaDB database through `"_" + sha1(site_name)[:16]`, and
`mariadb_manager` creates it with `CREATE OR REPLACE DATABASE`. Nothing stopped two rows from
carrying one name, so two benches could share one database and the second could drop the
first tenant's data. `autoname: field:site_name` closes that, and existing rows have to be
moved onto their names before the constraint can hold.

A duplicate loser is suffixed and deactivated, never deleted. An `Inactive` row can still own a
live database - `stop_bench` deactivates without dropping - and `api._drop_bench_site_databases`
reads `site_name` to find what to drop, so a row deleted here is a database nothing will ever
clean up. The suffixed loser is the record that the collision happened.
"""

import frappe
from frappe.model.rename_doc import rename_doc

SITE = "Bench Site"

# Furthest from gone first: a row describing a live site outranks one describing a stopped or
# broken site, and among equals the newest describes the deployment that actually happened.
STATUS_RANK = {"Active": 3, "Creating": 2, "Inactive": 1, "Error": 0}


def execute():
	rows = frappe.get_all(
		SITE, fields=["name", "site_name", "status", "bench", "creation"], order_by="creation asc"
	)
	suffixed = _suffix_duplicates(rows)
	renamed = _rename_onto_site_names(rows)
	if suffixed or renamed:
		frappe.logger("benchpress").info(
			f"bench site keys: renamed {renamed or 'nothing'}; deduped {suffixed or 'nothing'}"
		)


def _suffix_duplicates(rows: list) -> list[str]:
	"""Leave one row per site name, and move every other one aside under a name of its own."""
	by_site_name = {}
	for row in rows:
		by_site_name.setdefault(row.site_name, []).append(row)
	suffixed = []
	for site_name, contenders in by_site_name.items():
		if len(contenders) < 2:
			continue
		for loser in sorted(contenders, key=_survival_rank, reverse=True)[1:]:
			loser.site_name = f"{site_name}#dup-{loser.name}"
			loser.status = "Inactive"
			frappe.db.set_value(
				SITE,
				loser.name,
				{"site_name": loser.site_name, "status": "Inactive"},
				update_modified=False,
			)
			suffixed.append(f"{site_name} -> {loser.site_name}")
	return suffixed


def _survival_rank(row) -> tuple:
	return (
		bool(row.bench and frappe.db.exists("Bench Instance", row.bench)),
		STATUS_RANK.get(row.status, 0),
		row.creation,
	)


def _rename_onto_site_names(rows: list) -> list[str]:
	"""Rename every row onto its site name, stepping a blocker aside when one already holds it."""
	pending = [row for row in rows if row.name != row.site_name]
	renamed = []
	while pending:
		movable = [row for row in pending if not frappe.db.exists(SITE, row.site_name)]
		if not movable:
			# Two rows already carry each other's site name; one steps aside so the other can move.
			_rename(pending[0], f"{pending[0].name}-{frappe.generate_hash(length=6)}")
			continue
		for row in movable:
			was = row.name
			_rename(row, row.site_name)
			renamed.append(f"{was} -> {row.name}")
			pending.remove(row)
	return renamed


def _rename(row, new_name: str) -> None:
	# The model function rather than `frappe.rename_doc`, which does not forward `validate`.
	# Nothing here needs the checks it skips: this runs as Administrator, and the caller has
	# already found the target name free.
	rename_doc(SITE, row.name, new_name, force=True, validate=False, show_alert=False, rebuild_search=False)
	row.name = new_name
