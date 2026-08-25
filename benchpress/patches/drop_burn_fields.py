# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Drop the accrual engine's columns, after the code that stopped reading them.

`Credit Settings.max_run_hours` and `always_on_monthly_inr` are not listed. Removing a field
from a Single's JSON deletes its DocField on the next sync, which is what makes it unreadable;
the stored value in `tabSingles` is left where `bench migrate` leaves it. It is inert once no
field and no code path can reach it, and deleting an operator's number buys nothing.
"""

import frappe
from frappe.model import delete_fields

RETIRED = {
	"Credit Account": ["burn_rate", "burn_since"],
	"Bench Instance": ["credit_burn_rate", "credit_burn_started", "ttl_warned_at"],
}


def execute() -> list[str]:
	"""Returns the columns this run removed, so a second run says nothing."""
	dropped = [
		f"{doctype}.{field}" for doctype, fields in RETIRED.items() for field in _present(doctype, fields)
	]
	delete_fields(RETIRED, delete=1)
	for doctype in RETIRED:
		frappe.clear_cache(doctype=doctype)
	return dropped


def _present(doctype: str, fields: list[str]) -> list[str]:
	columns = {row[0] for row in frappe.db.describe(doctype)}
	return [field for field in fields if field in columns]
