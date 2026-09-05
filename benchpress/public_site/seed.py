# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _

from benchpress import emails
from benchpress.public_site import public_site_enabled
from benchpress.public_site.home import LANDING_PAGE, WEBSITE_SETTINGS

EMAIL_TEMPLATE = "Email Template"

# The landing page's former route; a site still pointing at it is re-pointed, not left.
FORMER_HOME_PAGE = "home"

# The brand bar the first seeded rows carried: a blue square beside the word BENCHPRESS.
FAUX_LOGO = re.compile(
	r'<table role="presentation" cellpadding="0" cellspacing="0" border="0">\s*<tr>\s*'
	r'<td width="10" bgcolor="#4E8BFB".*?</td>\s*<td [^>]*>BENCHPRESS</td>\s*</tr>\s*</table>',
	re.DOTALL,
)
LOGO_BLOCK = re.compile(r'<a href="\{\{ site_url \| e \}\}"[^>]*><img [^>]*alt="BenchPress"[^>]*></a>')


def seed_public_site() -> None:
	# Called from `after_install` as well as from the patch: a fresh install marks every patch as
	# already-run, so the patch alone would never fire.
	if not public_site_enabled():
		return
	seed_email_templates()
	claim_home_page()


def seed_email_templates() -> None:
	for row in emails.seed_rows():
		if not frappe.db.exists(EMAIL_TEMPLATE, row["name"]):
			frappe.get_doc(row).insert(ignore_permissions=True)


def claim_home_page() -> None:
	# `get_home_page` falls back to `login` for a guest when nothing names a home page, so an empty
	# value serves the login form at `/`.
	chosen = frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page")
	if chosen and chosen.strip("/") != FORMER_HOME_PAGE:
		return
	frappe.db.set_single_value(WEBSITE_SETTINGS, "home_page", LANDING_PAGE)
	# Written straight to the row, so the controller that would have dropped this key never ran.
	frappe.cache.delete_value("home_page")


def relogo_email_templates() -> None:
	block = _shipped_logo_block()
	for name in emails.DEFAULTS:
		body = frappe.db.get_value(EMAIL_TEMPLATE, name, "response_html")
		if not body:
			continue
		swapped, count = FAUX_LOGO.subn(lambda _match: block, body, count=1)
		if count:
			frappe.db.set_value(EMAIL_TEMPLATE, name, "response_html", swapped)
	frappe.clear_cache(doctype=EMAIL_TEMPLATE)


def _shipped_logo_block() -> str:
	# Taken from the shipped body so the markup lives in the templates and nowhere else.
	found = LOGO_BLOCK.search(emails.default_body(emails.ACCESS_APPROVED))
	if not found:
		frappe.throw(_("The shipped email header no longer carries the logo block"))
	return found.group(0)
