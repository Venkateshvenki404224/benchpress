# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The hosted waitlist — the app's only guest-reachable endpoint.

`join` is the single door left open to unauthenticated traffic, so it is written as a security
boundary rather than as a form handler: the address is validated before it reaches the database,
the free-text fields are truncated to their column widths, everything else in the request is
dropped, and the answer is identical whether the address was new or already on the list. Telling
a stranger which addresses are registered is a membership oracle, and a waitlist for a paid
product is exactly the list an attacker would enumerate.

Rate limiting is per (IP, email) so one address cannot be sprayed from one host, and the cap is
deliberately low: a human joins a waitlist once.
"""

import frappe
from frappe import _
from frappe.database import savepoint
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr

from benchpress.permissions import require_admin

DOCTYPE = "Waitlist Entry"
JOINS_PER_HOUR = 3
DATA_LIMIT = 140
TEXT_LIMIT = 1000


@frappe.whitelist(allow_guest=True)
@rate_limit(key="email", limit=JOINS_PER_HOUR, seconds=60 * 60, ip_based=True)
def join(
	email: str, full_name: str | None = None, company: str | None = None, use_case: str | None = None
) -> dict:
	"""Record an interest in hosted access. Always answers the same way."""
	entry = frappe.new_doc(DOCTYPE)
	entry.update(
		{
			"email": email,
			"full_name": clip(full_name, DATA_LIMIT),
			"company": clip(company, DATA_LIMIT),
			"use_case": clip(use_case, TEXT_LIMIT),
		}
	)
	insert_once(entry)
	return {"joined": True, "message": _("You're on the list. We'll email you when a slot opens.")}


@frappe.whitelist()
def approve(entries) -> dict:
	"""Approve the selected entries and invite each one. Desk bulk action, admins only."""
	require_admin()
	names = frappe.parse_json(entries)
	users = [approve_entry(name) for name in names]
	return {"approved": len(users), "users": users}


def approve_entry(name: str) -> str:
	"""One document per call — approval writes a `User`, so it cannot be a bulk update."""
	return frappe.get_doc(DOCTYPE, name).approve()


def insert_once(entry) -> None:
	"""Insert, and treat a repeat address as success.

	The doctype autonames on the email, so a duplicate is a primary-key conflict the database
	rejects without a lookup. Swallowing it inside a savepoint keeps the surrounding transaction
	usable and keeps the response indistinguishable from a first-time join.
	"""
	with savepoint(catch=frappe.DuplicateEntryError):
		entry.insert(ignore_permissions=True)


def clip(value, limit: int) -> str:
	"""Trim optional free text to its column width before it reaches the database."""
	return cstr(value).strip()[:limit]
