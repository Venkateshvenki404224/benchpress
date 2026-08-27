# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Drop `Bench Site.full_domain`, after the code that stopped reading it.

Removing the field from the DocType JSON stops anything resolving it, but `bench migrate`
leaves the column in place, so the drop is explicit here.
"""

import frappe
from frappe.model import delete_fields

RETIRED = {"Bench Site": ["full_domain"]}


def execute() -> list[str]:
	"""Returns the columns this run removed, so a second run says nothing."""
	columns = {row[0] for row in frappe.db.describe("Bench Site")}
	dropped = [f"Bench Site.{field}" for field in RETIRED["Bench Site"] if field in columns]
	delete_fields(RETIRED, delete=1)
	frappe.clear_cache(doctype="Bench Site")
	return dropped
