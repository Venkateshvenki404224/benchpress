# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Re-seed the approval mail while it still promises a welcome mail that never arrives.

Over an operator edit that kept that sentence, deliberately: the sentence is untrue.
"""

import frappe

from benchpress import emails

DEAD_PROMISE = "separate welcome email"


def execute():
	stored = frappe.db.get_value("Email Template", emails.ACCESS_APPROVED, "response_html")
	if not stored or DEAD_PROMISE not in stored:
		return
	frappe.db.set_value(
		"Email Template",
		emails.ACCESS_APPROVED,
		"response_html",
		emails.default_body(emails.ACCESS_APPROVED),
	)
	frappe.clear_cache(doctype="Email Template")
