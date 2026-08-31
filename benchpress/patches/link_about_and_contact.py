# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Give an already-seeded landing page the About and Contact links its seed now carries."""

# `seed_single` only fills a child table that is still empty, so a site seeded before these rows
# existed would never see them.

import frappe

from benchpress.benchpress.site_content import (
	LANDING_DOCTYPE,
	LANDING_SEED,
	clear_content_cache,
)

NEW_ANCHORS = ("/about", "/contact")
FOOTER_COLUMN = "Company"
ABOUT_SWITCH = "show_about"


def execute():
	settings = frappe.get_doc(LANDING_DOCTYPE)
	if not settings.nav_items and not settings.footer_links:
		return
	changed = adopt_about_switch(settings) | add_nav_links(settings) | add_footer_column(settings)
	if changed:
		settings.save(ignore_permissions=True)
		clear_content_cache()


def adopt_about_switch(settings) -> bool:
	# A Check the Single has never stored saves as 0, not as the field's default.
	if settings.get(ABOUT_SWITCH) not in (None, 0, "0"):
		return False
	settings.set(ABOUT_SWITCH, LANDING_SEED[ABOUT_SWITCH])
	return True


def add_nav_links(settings) -> bool:
	present = {row.anchor for row in settings.nav_items}
	rows = [
		row
		for row in LANDING_SEED["nav_items"]
		if row["anchor"] in NEW_ANCHORS and row["anchor"] not in present
	]
	for row in rows:
		settings.append("nav_items", row)
	return bool(rows)


def add_footer_column(settings) -> bool:
	if any(row.column_heading == FOOTER_COLUMN for row in settings.footer_links):
		return False
	for row in LANDING_SEED["footer_links"]:
		if row["column_heading"] == FOOTER_COLUMN:
			settings.append("footer_links", row)
	return True
