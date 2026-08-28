# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Write the per-tier request-rate defaults onto every `Instance Size` row.

Rows predating the fields read back zero, and Traefik reads `average: 0` as no limit at all.
"""

import frappe
from frappe.utils import cint

DOCTYPE = "Instance Size"
FIELDS = ("rate_average", "rate_burst")


def execute():
	meta = frappe.get_meta(DOCTYPE)
	defaults = {field: cint(meta.get_field(field).default) for field in FIELDS}
	for row in frappe.get_all(DOCTYPE, fields=["name", *FIELDS]):
		unseeded = {field: defaults[field] for field in FIELDS if not cint(row.get(field))}
		if unseeded:
			frappe.db.set_value(DOCTYPE, row.name, unseeded)
