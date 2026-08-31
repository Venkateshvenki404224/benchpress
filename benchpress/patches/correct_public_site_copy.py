# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Correct brand casing and the unbacked credit claim on already-seeded page Singles."""

import re

import frappe

PAGE_SINGLES = (
	"Landing Page Settings",
	"About Page Settings",
	"Contact Page Settings",
	"Signup Page Settings",
)
TEXT_TYPES = {"Data", "Small Text", "Text", "Long Text", "Text Editor"}
BRAND = re.compile(r"Benchpress(?![A-Za-z0-9_])")

OLD_CTA = "Start free — 500 credits"
NEW_CTA = "Start free"
CTA_FIELDS = ("hero_cta_primary_label", "paths_hosted_cta_label", "cta_primary_label")
OLD_HOSTED_BODY = (
	"Sign in, deploy a lab, get the URL and the IDE link. We run the host, the mesh and "
	"the upgrades. 500 credits to start, no card."
)
NEW_HOSTED_BODY = (
	"Sign in, deploy a lab, get the URL and the IDE link. We run the host, the mesh and "
	"the upgrades. No card, no commitment."
)
CREDIT_CLAIM = "500 credits"
OLD_BOOKING_META = "cal / benchpress"
OLD_ISSUES_META = "/benchpress/issues"
NEW_ISSUES_META = "github.com/Venkateshvenki404224/benchpress/issues"


def execute():
	drop_the_credit_claim()
	drop_the_credit_claim_from_signup()
	repoint_the_docs_link()
	hide_placeholder_testimonials()
	retire_the_unrouted_contact_channel()
	for doctype in PAGE_SINGLES:
		if frappe.db.exists("DocType", doctype):
			recase_single(doctype)


def drop_the_credit_claim():
	"""The seeded labels named 500 credits; the shipped grant default is 40."""
	if not frappe.db.exists("DocType", "Landing Page Settings"):
		return
	for fieldname in CTA_FIELDS:
		if frappe.db.get_single_value("Landing Page Settings", fieldname) == OLD_CTA:
			frappe.db.set_single_value("Landing Page Settings", fieldname, NEW_CTA)
	if frappe.db.get_single_value("Landing Page Settings", "paths_hosted_body") == OLD_HOSTED_BODY:
		frappe.db.set_single_value("Landing Page Settings", "paths_hosted_body", NEW_HOSTED_BODY)


def hide_placeholder_testimonials():
	if not frappe.db.exists("DocType", "Landing Testimonial"):
		return
	rows = frappe.get_all(
		"Landing Testimonial",
		filters={"parenttype": "Landing Page Settings"},
		fields=["name", "is_placeholder"],
	)
	if rows and all(row.is_placeholder for row in rows):
		frappe.db.set_single_value("Landing Page Settings", "show_testimonials", 0)


def drop_the_credit_claim_from_signup():
	if not frappe.db.exists("DocType", "Signup Page Settings"):
		return
	from benchpress.www.signup import SIGNUP_SEED

	for fieldname in ("intro_body", "pending_body", "meta_description"):
		value = frappe.db.get_single_value("Signup Page Settings", fieldname)
		if isinstance(value, str) and CREDIT_CLAIM in value:
			frappe.db.set_single_value("Signup Page Settings", fieldname, SIGNUP_SEED[fieldname])

	titles = {step["step_number"]: step["title"] for step in SIGNUP_SEED["signup_steps"]}
	for row in frappe.get_all(
		"Signup Step",
		filters={"parenttype": "Signup Page Settings"},
		fields=["name", "step_number", "title"],
	):
		if CREDIT_CLAIM in (row.title or "") and row.step_number in titles:
			frappe.db.set_value(
				"Signup Step", row.name, "title", titles[row.step_number], update_modified=False
			)


def repoint_the_docs_link():
	"""`/docs` is not a route this app serves; the guide lives on the marketing domain."""
	if not frappe.db.exists("DocType", "Signup Pending Link"):
		return
	from benchpress.www.signup import DOCS_URL

	for row in frappe.get_all(
		"Signup Pending Link",
		filters={"parenttype": "Signup Page Settings", "url": "/docs"},
		fields=["name"],
	):
		frappe.db.set_value("Signup Pending Link", row.name, "url", DOCS_URL, update_modified=False)


def retire_the_unrouted_contact_channel():
	"""The seeded booking card carried no url, so the template rendered a dead link."""
	if not frappe.db.exists("DocType", "Contact Channel"):
		return
	for row in frappe.get_all(
		"Contact Channel",
		filters={"parenttype": "Contact Page Settings", "url": ("in", ["", None])},
		fields=["name", "meta_label"],
	):
		if row.meta_label == OLD_BOOKING_META:
			frappe.delete_doc("Contact Channel", row.name, force=True, ignore_permissions=True)
	if frappe.db.exists("Contact Channel", {"meta_label": OLD_ISSUES_META}):
		frappe.db.set_value(
			"Contact Channel",
			{"meta_label": OLD_ISSUES_META},
			"meta_label",
			NEW_ISSUES_META,
			update_modified=False,
		)


def recase_single(doctype: str):
	for field in frappe.get_meta(doctype).fields:
		if field.fieldtype in TEXT_TYPES:
			recase_field(doctype, field.fieldname)
		elif field.fieldtype == "Table" and frappe.db.exists("DocType", field.options):
			recase_rows(field.options, doctype)


def recase_field(doctype: str, fieldname: str):
	value = frappe.db.get_single_value(doctype, fieldname)
	if isinstance(value, str) and BRAND.search(value):
		frappe.db.set_single_value(doctype, fieldname, BRAND.sub("BenchPress", value))


def recase_rows(child_doctype: str, parenttype: str):
	fields = [f.fieldname for f in frappe.get_meta(child_doctype).fields if f.fieldtype in TEXT_TYPES]
	if not fields:
		return
	for row in frappe.get_all(child_doctype, filters={"parenttype": parenttype}, fields=["name", *fields]):
		for fieldname in fields:
			value = row.get(fieldname)
			if isinstance(value, str) and BRAND.search(value):
				frappe.db.set_value(
					child_doctype,
					row.name,
					fieldname,
					BRAND.sub("BenchPress", value),
					update_modified=False,
				)
