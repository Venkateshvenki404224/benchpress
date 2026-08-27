# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The site name as an allocation: qualified, claimed, asserted free and released.

This module imports neither `api` nor `deploy_manager`, so all three can call it.
"""

import re

import frappe
from frappe import _

SITE_LABEL_MAX_LENGTH = 63
SITE_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def qualify(raw_site_name: str | None) -> str | None:
	"""Normalize a caller-chosen site name and refuse anything unsafe, or None if empty.

	A bare label is required, so the result is always exactly `<label>.<base_domain>`.
	"""
	if not raw_site_name or not raw_site_name.strip():
		return None
	candidate = raw_site_name.strip().lower()
	if "." in candidate:
		# Rejected rather than treated as already-qualified, so a caller cannot supply
		# an arbitrary suffix.
		frappe.throw(
			_(
				"Site name '{0}' must be a single label without dots — the domain is added automatically."
			).format(raw_site_name)
		)
	if not SITE_LABEL_RE.match(candidate) or len(candidate) > SITE_LABEL_MAX_LENGTH:
		frappe.throw(
			_(
				"Site name '{0}' is not valid: use lowercase letters, numbers and single '-' "
				"separators, starting and ending with a letter or number (max {1} characters), "
				"e.g. 'acme' or 'acme-labs'."
			).format(raw_site_name, SITE_LABEL_MAX_LENGTH)
		)
	base_domain = frappe.db.get_single_value("BenchPress Settings", "base_domain") or "localhost"
	return f"{candidate}.{base_domain}"


def claim(bench) -> None:
	"""Claim the site name by insert. The primary key is the check, and nothing else is."""
	try:
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"site_name": bench.site_name,
				"bench": bench.name,
				"status": "Creating",
			}
		).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		_refuse_taken(bench)
		return
	# After the insert, which stamps the session user over any owner handed to it. `Bench Site`
	# is read `if_owner`, so an admin deploying somebody else's instance would otherwise take the
	# row over and empty that tenant's Sites tab.
	frappe.db.set_value("Bench Site", site.name, "owner", bench.owner, update_modified=False)


def _refuse_taken(bench) -> None:
	# First, and on both paths: the framework msgprints "Bench Site X already exists" before it
	# raises, so a redeploy would carry that internal sentence on an otherwise successful reply.
	frappe.clear_last_message()
	# A locking read, because this session is REPEATABLE READ: a plain one answers from a
	# snapshot taken before the winner committed, and would refuse this caller their own name.
	if frappe.db.get_value("Bench Site", bench.site_name, "bench", for_update=True) == bench.name:
		return
	frappe.throw(_("Site name '{0}' is already in use. Choose a different name.").format(bench.site_name))


def claimed(bench):
	"""The row claimed for this name, claiming it here if nothing did.

	Raises when the name belongs to another bench.
	"""
	if not frappe.db.exists("Bench Site", bench.site_name):
		# A Desk deploy never went through `api.create_bench`, so nothing claimed the name for it.
		claim(bench)
	site = frappe.get_doc("Bench Site", bench.site_name)
	if site.bench != bench.name:
		# The last line of defence rather than the constraint, but a deploy that would write
		# over somebody else's site must fail loudly.
		raise Exception(f"Site {bench.site_name} belongs to {site.bench}")
	return site


# The name is held for exactly as long as the row. `teardown_bench` keeps it so a redeploy still
# owns its own name; only a deleted instance frees it, which is once `api._delete_bench` has
# dropped the database the name keyed.
def release(bench_name: str) -> None:
	"""Free every name this bench holds, by deleting the rows that are the claim."""
	for site in frappe.get_all("Bench Site", filters={"bench": bench_name}, pluck="name"):
		frappe.delete_doc("Bench Site", site, force=True, ignore_permissions=True)
