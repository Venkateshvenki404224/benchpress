# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Plant the six transactional emails and point `/` at the landing page."""

# Called from both `after_install` and `patches.seed_public_site`: a fresh install marks every
# patch as already-run, so the patch alone would never fire.

import frappe

from benchpress import emails
from benchpress.public_site import public_site_enabled
from benchpress.public_site.home import LANDING_PAGE, WEBSITE_SETTINGS

EMAIL_TEMPLATE = "Email Template"

# The landing page's former route; a site still pointing at it is re-pointed, not left.
FORMER_HOME_PAGE = "home"


def seed_public_site() -> None:
	"""Seed the mail templates and the site's home page. Idempotent."""
	if not public_site_enabled():
		return
	seed_email_templates()
	claim_home_page()


def seed_email_templates() -> None:
	"""Plant the six mail templates, never over an operator's edit."""
	for row in emails.seed_rows():
		if not frappe.db.exists(EMAIL_TEMPLATE, row["name"]):
			frappe.get_doc(row).insert(ignore_permissions=True)


def claim_home_page() -> None:
	"""Point `/` at the landing page, unless the operator has chosen a page of their own."""
	# `get_home_page` falls back to `login` for a guest when nothing names a home page, so an empty
	# value serves the login form at `/`.
	chosen = frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page")
	if chosen and chosen.strip("/") != FORMER_HOME_PAGE:
		return
	frappe.db.set_single_value(WEBSITE_SETTINGS, "home_page", LANDING_PAGE)
	# Written straight to the row, so the controller that would have dropped this key never ran.
	frappe.cache.delete_value("home_page")
