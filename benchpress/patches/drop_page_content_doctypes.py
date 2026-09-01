# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Remove the thirty doctypes that modelled page copy. Every public page renders from a constant."""

import frappe

PAGE_CONTENT_DOCTYPES = (
	"Landing Page Settings",
	"About Page Settings",
	"Contact Page Settings",
	"Signup Page Settings",
	"About Contrast Row",
	"About Day Entry",
	"About Principle",
	"About Stat",
	"About Timeline Entry",
	"Contact Channel",
	"Contact Response Time",
	"Contact Topic",
	"Landing Agent Api Example",
	"Landing Agent Point",
	"Landing Comparison Row",
	"Landing Console Callout",
	"Landing Faq Item",
	"Landing Feature Card",
	"Landing Footer Link",
	"Landing Hero Assurance",
	"Landing Logo",
	"Landing Nav Item",
	"Landing Path Point",
	"Landing Pipeline Phase",
	"Landing Pipeline Step",
	"Landing Service Card",
	"Landing Template Card",
	"Landing Testimonial",
	"Signup Pending Link",
	"Signup Step",
)


def execute():
	for doctype in PAGE_CONTENT_DOCTYPES:
		drop(doctype)
	frappe.clear_cache()


def drop(doctype: str) -> None:
	frappe.delete_doc_if_exists("DocType", doctype, force=1)
	frappe.db.delete("Singles", {"doctype": doctype})
	# `delete_doc` leaves the physical table behind; the framework's own uninstall drops it here.
	frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{doctype}`")
