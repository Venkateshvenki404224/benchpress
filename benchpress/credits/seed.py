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
		"price_multiplier": 1.0,
		"memory_limit": "1g",
		"cpu_cores": 1,
		"credits_per_hour": 1.0,
		"max_sites": 3,
		"is_default": 1,
		"sort_order": 1,
	},
	{
		"size_label": "Medium",
		"price_multiplier": 2.0,
		"memory_limit": "2g",
		"cpu_cores": 2,
		"credits_per_hour": 2.0,
		"max_sites": 5,
		"is_default": 0,
		"sort_order": 2,
	},
	{
		"size_label": "Large",
		"price_multiplier": 4.0,
		"memory_limit": "4g",
		"cpu_cores": 4,
		"credits_per_hour": 4.0,
		"max_sites": 10,
		"is_default": 0,
		"sort_order": 3,
	},
]

# Credits per row rather than a rate, so a longer window can cost less per hour. That is the
# point of selling durations: a week is a commitment and is priced like one.
LEASE_PLANS = [
	{"plan_label": "30 minutes", "minutes": 30, "credits": 5, "is_active": 1, "sort_order": 1},
	{"plan_label": "2 hours", "minutes": 120, "credits": 18, "is_active": 1, "sort_order": 2},
	{"plan_label": "8 hours", "minutes": 480, "credits": 60, "is_active": 1, "sort_order": 3},
	{"plan_label": "1 day", "minutes": 1440, "credits": 150, "is_active": 1, "sort_order": 4},
	{"plan_label": "2 days", "minutes": 2880, "credits": 260, "is_active": 1, "sort_order": 5},
	{"plan_label": "4 days", "minutes": 5760, "credits": 460, "is_active": 1, "sort_order": 6},
	{"plan_label": "1 week", "minutes": 10080, "credits": 700, "is_active": 1, "sort_order": 7},
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
	seed_rows("Lease Plan", "plan_label", LEASE_PLANS)
	seed_rows("Credit Pack", "pack_label", CREDIT_PACKS)
	seed_credit_settings()
	seed_default_lease_plan()
	ensure_ledger_index()


def seed_rows(doctype: str, key: str, rows: list[dict]) -> None:
	existing = set(frappe.get_all(doctype, pluck="name"))
	for row in rows:
		if row[key] in existing:
			continue
		frappe.get_doc({"doctype": doctype, **row}).insert(ignore_permissions=True)


def ensure_ledger_index() -> None:
	"""The two query shapes the ledger is read by, neither of which DocType JSON can declare.

	`(account, creation)` is the statement page: one account's rows, newest first, so pagination
	stays an index range scan however long the ledger grows.

	`(reference_doctype, reference_name)` is the replay guard. Every webhook delivery asks whether
	this order has already been credited, and that question is asked against the one table that
	grows forever — without the index it is a full scan, and it is on the path money takes.

	DocType JSON declares only single-column `search_index` entries, so both are added by hand.
	`request_id` is one column and declares its own. `add_index` is idempotent.
	"""
	frappe.db.add_index("Credit Ledger Entry", ["account", "creation"])
	frappe.db.add_index("Credit Ledger Entry", ["reference_doctype", "reference_name"])


def seed_credit_settings() -> None:
	"""Materialise the Single, because a Single with no row reads every field as None.

	`bench migrate` does not run `init_singles`, so an upgraded site would otherwise see None
	where the doctype declares a default.
	"""
	if frappe.db.get_singles_dict("Credit Settings"):
		return

	settings = frappe.new_doc("Credit Settings")
	settings.save(ignore_permissions=True)


def seed_default_lease_plan() -> None:
	"""Point `Credit Settings` at the shortest plan, so a lab that names none still has one.

	Only when the field is empty: an operator who chose a different fallback keeps it.
	"""
	if frappe.db.get_single_value("Credit Settings", "default_lease_plan"):
		return
	shortest = frappe.db.get_value("Lease Plan", {"is_active": 1}, "name", order_by="minutes asc")
	if shortest:
		frappe.db.set_single_value("Credit Settings", "default_lease_plan", shortest)
