# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

from benchpress.benchpress.doctype.benchpress_settings.benchpress_settings import claim_host_name


def execute():
	claim_host_name(frappe.db.get_single_value("BenchPress Settings", "base_domain"))
