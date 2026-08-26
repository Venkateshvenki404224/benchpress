# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Write the golden switches' defaults, which a `Check` field's default alone does not.

A Single stores only the values something has set, so a field added to the DocType reads back as
`None` until the settings form is saved once. Both of these default to on, and unset would mean
off: builds that quietly skip the golden step, and deploys that quietly build every site from
scratch. Neither says anything in a log.
"""

import frappe

SETTINGS = "BenchPress Settings"
FIELDS = ("enable_golden_images", "restore_from_golden")


def execute():
	stored = frappe.db.get_singles_dict(SETTINGS)
	for field in FIELDS:
		if field not in stored:
			frappe.db.set_single_value(SETTINGS, field, 1)
