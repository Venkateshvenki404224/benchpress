# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

from benchpress.public_site import public_site_enabled

WEBSITE_SETTINGS = "Website Settings"

LANDING_PAGE = "index"

# `get_home_page` turns this into `desk` for a System User and `portal` for a portal user.
SIGNED_IN_DEFAULT = "me"


def home_page_for(user: str) -> str | None:
	# `get_website_user_home_page` runs for every user, not only a Website User, and is consulted
	# ahead of Website Settings; `None` falls through to whatever an operator chose in Desk.
	if user == "Guest" or not public_site_enabled():
		return None
	chosen = frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page") or ""
	return SIGNED_IN_DEFAULT if chosen.strip("/") == LANDING_PAGE else None
