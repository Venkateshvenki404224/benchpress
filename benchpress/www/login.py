# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Branded `/login`. It shadows Frappe's page; the login flow underneath is still Frappe's."""

import os

import frappe
from frappe.utils import cint
from frappe.www.login import get_context as frappe_login_context

from benchpress.benchpress.site_content import chrome_content, preview_tags

no_cache = True

# `/login` has no Single of its own; the nine `login_*` fields ride on the signup Single.
SETTINGS_DOCTYPE = "Signup Page Settings"

WAITLIST_ROUTE = "/signup"

LOGIN_SEED = {
	"login_title": "Log in",
	"login_body": ("Access is granted after review, so accounts only exist once we have approved a request."),
	"login_oauth_label": "Continue with GitHub",
	"login_divider_label": "or email",
	"login_remember_label": "Keep me signed in on this device",
	"login_submit_label": "Log in",
	# Text Editor field: the template renders it raw, and `signup_prompt()` rewrites the anchor.
	"login_signup_prompt": (
		'<p>No account yet? <a href="#signup">Request access</a> — approved by hand, usually '
		"inside a business day. Self-hosting needs no account at all.</p>"
	),
	"login_panel_eyebrow": "After you log in",
	"login_panel_title": "A console, a credit balance, and one button that matters.",
}

CACHE_BUST_PATHS = (
	("public", "css", "brand.css"),
	("public", "css", "login.css"),
	("public", "js", "site.js"),
	("public", "js", "login.js"),
	("public", "images", "logo"),
)

# The chrome keys `site_header.html` and `site_footer.html` read.
FALLBACK_CHROME = {
	"nav_items": [],
	"footer_columns": [],
	"footer_tagline": None,
	"footer_copyright": None,
	"footer_trademark": None,
	"footer_trademark_short": None,
	"is_landing": False,
	"signup_route": WAITLIST_ROUTE,
}


def get_context(context):
	frappe_login_context(context)
	context.update(branded(context))
	return context


def branded(context) -> dict:
	try:
		return desk_content(context)
	except Exception:
		# Deliberately broad: a traceback here would serve the error page instead of the login form.
		frappe.log_error(title="Branded /login fell back to seed copy")
		return seed_content()


def desk_content(context) -> dict:
	content = page_context(login_copy())
	content.update(chrome_content(is_landing=False))
	content["asset_version"] = asset_version()
	content["signup_prompt"] = signup_prompt(
		content["login_signup_prompt"], cint(context.get("disable_signup"))
	)
	return content


def seed_content() -> dict:
	"""The shipped copy alone: no Desk read, no disk read."""
	content = page_context(dict(LOGIN_SEED))
	content.update(FALLBACK_CHROME)
	content["asset_version"] = "0"
	content["signup_prompt"] = LOGIN_SEED["login_signup_prompt"]
	return content


def page_context(copy: dict) -> dict:
	content = dict(copy)
	content.update(
		{
			"mode_default": "dark",
			"body_class": "bp-body",
			"full_width": 1,
			"show_sidebar": 0,
			"meta_title": copy["login_title"],
			"meta_description": copy["login_body"],
			"metatags": preview_tags(copy["login_title"], copy["login_body"]),
		}
	)
	return content


def login_copy() -> dict:
	copy = dict(LOGIN_SEED)
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return copy

	settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
	for fieldname in LOGIN_SEED:
		value = settings.get(fieldname)
		if value not in (None, ""):
			copy[fieldname] = value
	return copy


def signup_prompt(html: str, disable_signup: int) -> str:
	"""Re-point the prompt's link when Frappe will not render the inline signup section."""
	if not disable_signup:
		return html
	return html.replace('href="#signup"', 'href="/signup"')


def asset_version() -> str:
	"""Newest mtime among the assets this page links by plain filename."""
	mtimes = []
	for parts in CACHE_BUST_PATHS:
		path = frappe.get_app_path("benchpress", *parts)
		if os.path.isdir(path):
			mtimes += [os.path.getmtime(os.path.join(path, name)) for name in os.listdir(path)]
		elif os.path.exists(path):
			mtimes.append(os.path.getmtime(path))
	return str(int(max(mtimes))) if mtimes else "0"
