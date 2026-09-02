# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Removing fixtures a test committed. A plain `delete_doc` cleanup is rolled back with the test."""

import frappe


def drop(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
	frappe.db.commit()  # nosemgrep


def drop_all(doctype: str, filters: dict) -> None:
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		drop(doctype, name)
