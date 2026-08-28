# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Write the Traefik probe defaults, so Desk shows the numbers actually in force.

Over a stored zero as well as over nothing: `_service_health` reads both as "use the default".
"""

import frappe
from frappe.utils import cint

SETTINGS = "BenchPress Settings"
FIELDS = ("traefik_health_interval_seconds", "traefik_health_timeout_seconds")


def execute():
	stored = frappe.db.get_singles_dict(SETTINGS)
	meta = frappe.get_meta(SETTINGS)
	for field in FIELDS:
		if not cint(stored.get(field)):
			frappe.db.set_single_value(SETTINGS, field, meta.get_field(field).default)
