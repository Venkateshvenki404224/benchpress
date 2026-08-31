# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model import delete_fields

BENCH_INSTANCE_FIELDS = ["wg_private_key", "wg_public_key"]
SETTINGS_FIELDS = [
	"wg_server_ip",
	"wg_subnet",
	"wg_server_port",
	"wg_server_public_key",
	"wg_server_private_key",
	"wg_server_endpoint",
	"next_wg_ip",
]


def execute():
	"""Drop the WireGuard schema BenchPress no longer owns (phase 4).

	delete_fields drops the Bench Instance columns and clears the
	BenchPress Settings values from tabSingles.
	"""
	delete_fields(
		{
			"Bench Instance": BENCH_INSTANCE_FIELDS,
			"BenchPress Settings": SETTINGS_FIELDS,
		},
		delete=1,
	)
	frappe.clear_cache(doctype="Bench Instance")
	frappe.clear_cache(doctype="BenchPress Settings")
