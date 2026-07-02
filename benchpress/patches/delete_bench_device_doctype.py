# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Remove the legacy Bench Device DocType — devices are VPN Peers now (phase 4)."""
	if frappe.db.table_exists("Bench Device"):
		frappe.db.delete("Bench Device")
	frappe.delete_doc_if_exists("DocType", "Bench Device", force=1)
	frappe.delete_doc_if_exists("Module Def", "Device Management", force=1)
