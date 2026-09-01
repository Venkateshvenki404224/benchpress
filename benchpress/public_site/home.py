# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Who `/` is for. A guest gets the landing page; a signed-in visitor gets their own app."""

# Wired to the `get_website_user_home_page` hook, which despite the name runs for every user.
# `get_home_page_via_hooks` is consulted ahead of Website Settings, so answering unconditionally
# would take `/` away from Desk; returning `None` falls through to the stored value.

import frappe

from benchpress.public_site import public_site_enabled

WEBSITE_SETTINGS = "Website Settings"

LANDING_PAGE = "index"

# `get_home_page` turns this into `desk` for a System User and `portal` for a portal user.
SIGNED_IN_DEFAULT = "me"


def home_page_for(user: str) -> str | None:
	"""Where a signed-in visitor lands. `None` leaves the answer to Website Settings."""
	if user == "Guest" or not public_site_enabled():
		return None
	chosen = frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page") or ""
	return SIGNED_IN_DEFAULT if chosen.strip("/") == LANDING_PAGE else None
