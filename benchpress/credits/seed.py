# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Seed the commercial config so a fresh install has prices to show.

Deliberately not a `fixtures` entry. App fixtures import with `force=True`, which deletes and
re-inserts each row on *every* `bench migrate` — that would silently reset any price an operator
retuned in Desk, and would drop rows other doctypes link to. `seed_defaults` only fills in what
is missing, so operator edits and deletions both survive every later migrate.

It runs from two places because Frappe drives fresh installs and upgrades differently:
`after_install` (a fresh install marks every patch as already-run, so the patch alone would never
fire) and `benchpress.patches.seed_credit_config` (an existing site only runs patches).

Every number here is a placeholder to be re-derived against the real server; see
specs/in-progress/hosted-credits-and-landing/README.md.
"""

import frappe

INSTANCE_SIZES = [
	{
		"size_label": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"credits_per_hour": 1.0,
		"max_sites": 3,
		"is_default": 1,
		"sort_order": 1,
	},
	{
		"size_label": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"credits_per_hour": 2.0,
		"max_sites": 5,
		"is_default": 0,
		"sort_order": 2,
	},
	{
		"size_label": "Large",
		"memory_limit": "4g",
		"cpu_cores": 4,
		"credits_per_hour": 4.0,
		"max_sites": 10,
		"is_default": 0,
		"sort_order": 3,
	},
]

CREDIT_PACKS = [
	{
		"pack_label": "Starter",
		"inr_price": 499,
		"credits": 200,
		"is_active": 1,
		"highlight": 0,
		"sort_order": 1,
	},
	{
		"pack_label": "Regular",
		"inr_price": 1999,
		"credits": 1000,
		"is_active": 1,
		"highlight": 1,
		"sort_order": 2,
	},
	{
		"pack_label": "Heavy",
		"inr_price": 6999,
		"credits": 4000,
		"is_active": 1,
		"highlight": 0,
		"sort_order": 3,
	},
]


def seed_defaults() -> None:
	"""Idempotent. Safe to call on every install and from the patch."""
	seed_rows("Instance Size", "size_label", INSTANCE_SIZES)
	seed_rows("Credit Pack", "pack_label", CREDIT_PACKS)
	seed_credit_settings()
	ensure_ledger_index()


def seed_rows(doctype: str, key: str, rows: list[dict]) -> None:
	existing = set(frappe.get_all(doctype, pluck="name"))
	for row in rows:
		if row[key] in existing:
			continue
		frappe.get_doc({"doctype": doctype, **row}).insert(ignore_permissions=True)


def ensure_ledger_index() -> None:
	"""The statement page's only query shape: one account's rows, newest first.

	A composite `(account, creation)` index serves both the filter and the sort, so pagination
	stays an index range scan however long the ledger grows. DocType JSON can only declare
	single-column `search_index` entries, so this one is added by hand; `add_index` is idempotent.
	"""
	frappe.db.add_index("Credit Ledger Entry", ["account", "creation"])


def seed_credit_settings() -> None:
	"""Materialise the Single, because a Single with no row reads every field as None.

	`bench migrate` does not run `init_singles`, so an upgraded site would otherwise see None
	where the doctype declares a default.
	"""
	if frappe.db.get_singles_dict("Credit Settings"):
		return

	settings = frappe.new_doc("Credit Settings")
	settings.save(ignore_permissions=True)
