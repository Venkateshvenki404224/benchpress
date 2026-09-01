# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""`/login`: branded while the public site is on, Frappe's own page while it is off."""

import frappe
from frappe.utils import cint
from frappe.www.login import get_context as frappe_login_context

from benchpress.benchpress.site_content import asset_version, chrome_content, preview_tags
from benchpress.public_site import public_site_enabled

no_cache = True

# `TemplatePage` reads `context.template` back after `get_context` returns, so this is the off
# switch for a shadow. Colocated assets still resolve by this module's name: never add login.js.
FRAMEWORK_TEMPLATE = "frappe/www/login.html"

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

# The chrome keys `site_header.html` and `site_footer.html` read.
FALLBACK_CHROME = {
	"nav_items": [],
	"footer_columns": [],
	"footer_tagline": None,
	"footer_copyright": None,
	"footer_trademark": None,
	"signup_route": WAITLIST_ROUTE,
}


def get_context(context):
	frappe_login_context(context)
	if not public_site_enabled():
		context.template = FRAMEWORK_TEMPLATE
		return context

	context.update(branded(context))
	return context


def branded(context) -> dict:
	try:
		return with_chrome(context)
	except Exception:
		# Deliberately broad: a traceback here would serve the error page instead of the login form.
		frappe.log_error(title="Branded /login fell back to the shipped chrome")
		return without_chrome()


def with_chrome(context) -> dict:
	content = page_context(LOGIN_SEED)
	content.update(chrome_content())
	content["signup_prompt"] = signup_prompt(
		content["login_signup_prompt"], cint(context.get("disable_signup"))
	)
	return content


def without_chrome() -> dict:
	"""The login card with the chrome keys emptied."""
	content = page_context(LOGIN_SEED)
	content.update(FALLBACK_CHROME)
	content["asset_version"] = asset_version()
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


def signup_prompt(html: str, disable_signup: int) -> str:
	"""Re-point the prompt's link when Frappe will not render the inline signup section."""
	if not disable_signup:
		return html
	return html.replace('href="#signup"', 'href="/signup"')
