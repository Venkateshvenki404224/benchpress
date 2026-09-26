# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

SETTINGS = "BenchPress Settings"
FIELD = "max_bench_databases"


def execute():
	if not cint(frappe.db.get_single_value(SETTINGS, FIELD)):
		frappe.db.set_single_value(SETTINGS, FIELD, frappe.get_meta(SETTINGS).get_field(FIELD).default)
