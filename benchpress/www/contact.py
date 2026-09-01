# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cstr, strip_html

from benchpress import contact
from benchpress.benchpress.site_content import canonical_url, chrome_content, preview_tags, shipped
from benchpress.public_site import require_public_site

ROUTE = "/contact"

REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
DEFAULT_TITLE = "Contact BenchPress"

# Also `contact.submit`'s keyword names: `posted_values()` hands the whole dict straight to it.
FORM_FIELDS = ("name", "email", "message", "topic")

no_cache = 1
sitemap = 1


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.bp_canonical = canonical_url("/contact")
	context.body_class = "bp-body"
	context.mode_default = "dark"

	settings = shipped(CONTACT_SEED)
	context.update(chrome_content())
	context.update(submission())
	context.settings = settings
	context.channels = channel_rows(settings.channels)
	context.topics = settings.topics
	context.response_times = settings.response_times
	context.default_topic = contact.default_topic()
	context.selfhost_links = link_lines(settings.selfhost_links)

	context.contact_route = ROUTE
	context.repo_url = REPO_URL

	context.meta_title = settings.meta_title
	context.meta_description = settings.meta_description
	context.og_image = settings.og_image
	context.title = context.meta_title
	context.metatags = preview_tags(context.title, context.meta_description, context.og_image)
	return context


def submission() -> dict:
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

	state.update(sent=True, success_message=reply["message"])
	return state


def posted_values() -> frappe._dict:
	form = frappe.form_dict
	return frappe._dict({field: cstr(form.get(field)).strip() for field in FORM_FIELDS})


def channel_rows(channels: list) -> list:
	# `meta` is in Frappe's `RESERVED_KEYWORDS`, so the row ships the value as `meta_label`.
	for row in channels:
		row.meta = row.meta_label
	return channels


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


# Seed content: what the page renders, and what the seeder writes into Desk.

INTRO_BODY = (
	"No chatbot, no ticket robot. Pick whichever door fits — a bug goes to GitHub, a quote goes "
	"to the form, an urgent production question goes to email."
)

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
			"meta_label": contact.CONTACT_EMAIL,
			"url": f"mailto:{contact.CONTACT_EMAIL}",
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
	"topics": [dict(row) for row in contact.TOPICS],
	"form_submit_label": "Send message",
	"form_success_title": "Message sent",
	"form_success_body": contact.SUCCESS_BODY,
	"sla_title": "Response times",
	"response_times": [dict(row) for row in contact.RESPONSE_TIMES],
	"selfhost_title": "Self-hosting a question",
	"selfhost_body": SELFHOST_BODY,
	"selfhost_links": f"github.com/Venkateshvenki404224/benchpress\n{contact.CONTACT_EMAIL}",
	"meta_title": DEFAULT_TITLE,
	"meta_description": (
		"Talk to the people who wrote BenchPress — email or GitHub issues, "
		"answered by a person within one business day."
	),
	"og_image": "",
}
