# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.utils import cstr, strip_html

from benchpress import contact
from benchpress.benchpress.site_content import chrome_content, merged, preview_tags
from benchpress.public_site import require_public_site

DOCTYPE = "Contact Page Settings"

ROUTE = "/contact"

REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
CONTACT_EMAIL = "hello@benchpress.dev"
DEFAULT_TITLE = "Contact BenchPress"

# Also `contact.submit`'s keyword names: `posted_values()` hands the whole dict straight to it.
FORM_FIELDS = ("name", "email", "message", "topic")

CACHE_BUST_PATHS = (
	("public", "css", "brand.css"),
	("public", "css", "pages.css"),
	("public", "js", "site.js"),
	("public", "js", "contact.js"),
	("public", "images", "logo"),
	("public", "manifest.json"),
)

no_cache = 1


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.full_width = 1
	context.body_class = "bp-body"
	context.mode_default = "dark"

	settings = page_settings()
	context.update(chrome_content(is_landing=False))
	context.update(submission(settings))
	context.settings = settings
	context.channels = channel_rows(settings.channels)
	context.topics = settings.topics
	context.response_times = settings.response_times
	context.default_topic = default_topic(settings.topics)
	context.selfhost_links = link_lines(settings.selfhost_links)

	context.contact_route = ROUTE
	context.repo_url = REPO_URL
	context.contact_email = settings.notify_email or CONTACT_EMAIL

	context.meta_title = settings.meta_title or DEFAULT_TITLE
	context.meta_description = settings.meta_description or settings.intro_body
	context.og_image = settings.og_image
	context.title = context.meta_title
	context.metatags = preview_tags(context.title, context.meta_description, context.og_image)
	context.asset_version = asset_version()
	return context


def submission(settings) -> dict:
	"""The state the page opens in: empty form, form with an error, or receipt."""
	state = {
		"sent": False,
		"form_error": "",
		"form_values": frappe._dict(),
		"success_message": "",
	}
	if getattr(frappe.request, "method", "GET") != "POST":
		return state

	posted = posted_values()
	state["form_values"] = posted
	try:
		reply = contact.submit(**posted)
	except frappe.ValidationError as error:
		# The exception is swallowed here, so the rollback the framework would do on the way out is ours.
		frappe.db.rollback()
		state["form_error"] = strip_html(cstr(error)).strip()
		return state

	state.update(sent=True, success_message=reply.get("message") or settings.form_success_body)
	return state


def posted_values() -> frappe._dict:
	form = frappe.form_dict
	return frappe._dict({field: cstr(form.get(field)).strip() for field in FORM_FIELDS})


def page_settings() -> frappe._dict:
	return merged(DOCTYPE, CONTACT_SEED)


def channel_rows(channels: list) -> list:
	# `meta` is in Frappe's `RESERVED_KEYWORDS`, so the child table ships the column as `meta_label`.
	# These rows are plain dicts, so the alias the template reads is safe to restore here.
	for row in channels:
		row.meta = row.get("meta_label") or row.get("meta") or ""
	return channels


def default_topic(topics: list) -> str:
	"""The flagged row, else the first, else no topic at all."""
	flagged = next((row.label for row in topics if row.get("is_default") and row.label), "")
	return flagged or next((row.label for row in topics if row.label), "")


def link_lines(value: str) -> list[dict]:
	"""`selfhost_links` is one address per line."""
	lines = [line.strip() for line in cstr(value).splitlines() if line.strip()]
	return [{"text": line, "url": link_href(line)} for line in lines]


def link_href(line: str) -> str:
	if " " in line:
		return ""
	if "@" in line:
		return f"mailto:{line}"
	if line.startswith(("http://", "https://")):
		return line
	return f"https://{line}" if "." in line else ""


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


# Seed content: what an unset field falls back to, and what the seeder writes.

INTRO_BODY = (
	"No chatbot, no ticket robot. Pick whichever door fits — a bug goes to GitHub, a quote goes "
	"to the form, an urgent production question goes to email."
)

SUCCESS_BODY = "Thanks — it is in front of a person, not a queue. You will hear back within one business day."

SELFHOST_BODY = (
	"<p>Self-hosted installs get community support on GitHub — issues and discussions, answered "
	"in public so the next person finds the answer. Paid support with a response window is one "
	"of the four things we sell.</p>"
)

CONTACT_SEED = {
	"eyebrow": "Contact",
	"title": "Talk to the people who wrote it.",
	"intro_body": INTRO_BODY,
	"channels": [
		{
			"icon": "mail",
			"title": "Email us",
			"body": "Sales, hosted access, quotes for setup or app work. A human replies.",
			"meta_label": CONTACT_EMAIL,
			"url": f"mailto:{CONTACT_EMAIL}",
		},
		{
			"icon": "github",
			"title": "GitHub issues",
			"body": "Bugs, feature requests and self-hosting questions, answered in public.",
			"meta_label": "github.com/Venkateshvenki404224/benchpress/issues",
			"url": f"{REPO_URL}/issues",
		},
	],
	"form_title": "Send a message",
	"form_subtitle": "We answer every message within one business day.",
	"form_topic_label": "Topic",
	"topics": [
		{"label": "Hosted access", "route_to_email": "", "is_default": 1},
		{"label": "Setup or migration", "route_to_email": "", "is_default": 0},
		{"label": "Custom app work", "route_to_email": "", "is_default": 0},
		{"label": "Bug or issue", "route_to_email": "", "is_default": 0},
	],
	"form_submit_label": "Send message",
	"form_success_title": "Message sent",
	"form_success_body": SUCCESS_BODY,
	"sla_title": "Response times",
	"response_times": [
		{"subject": "Hosted access requests", "window": "1 business day"},
		{"subject": "Sales and quotes", "window": "1 business day"},
		{"subject": "GitHub issues", "window": "2–3 days"},  # noqa: RUF001 -- verbatim spec copy
	],
	"selfhost_title": "Self-hosting a question",
	"selfhost_body": SELFHOST_BODY,
	"selfhost_links": f"github.com/Venkateshvenki404224/benchpress\n{CONTACT_EMAIL}",
	"notify_email": CONTACT_EMAIL,
	"meta_title": DEFAULT_TITLE,
	"meta_description": (
		"Talk to the people who wrote BenchPress — email or GitHub issues, "
		"answered by a person within one business day."
	),
	"og_image": "",
}
