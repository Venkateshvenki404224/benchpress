# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, cstr, strip_html

from benchpress import waitlist
from benchpress.benchpress.site_content import chrome_content, preview_tags, shipped
from benchpress.credits.config import SIGNUP_ROUTE, credits_enabled, waitlist_open
from benchpress.public_site import require_public_site

WAITLIST_DOCTYPE = "Waitlist Entry"

SOURCE = "Signup Page"

ROUTE = "/signup"
LOGIN_ROUTE = "/login"
DOCS_URL = "https://benchpress.cloud/docs"
REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
DEFAULT_TITLE = "Request access — BenchPress"

# Also `waitlist.join`'s keyword names: `posted_values()` hands the whole dict straight to it.
FORM_FIELDS = ("email", "full_name", "company", "team_size", "intent", "expected_apps", "use_case")

no_cache = 1


def get_context(context):
	require_public_site()

	# One front door at a time: with self-serve signup live, the queue this page feeds is gone.
	if credits_enabled() and not waitlist_open():
		frappe.local.flags.redirect_location = SIGNUP_ROUTE
		raise frappe.Redirect

	context.no_cache = 1
	context.body_class = "bp-body"
	context.mode_default = "dark"

	settings = shipped(SIGNUP_SEED)
	context.update(chrome_content())
	context.update(submission())
	context.settings = settings
	context.steps = settings.signup_steps
	context.pending_links = settings.pending_links
	context.team_size = select_field("team_size")
	context.intent = select_field("intent")

	context.waitlist_open = True
	context.signup_route = ROUTE
	context.login_route = LOGIN_ROUTE
	context.docs_url = DOCS_URL
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
		"submitted": False,
		"reference": "",
		"submitted_email": "",
		"form_error": "",
		"form_values": frappe._dict(),
	}
	# `frappe.request` is a proxy that is falsy rather than absent outside a request.
	if not frappe.request or frappe.request.method != "POST":
		return state

	posted = posted_values()
	state["form_values"] = posted
	try:
		reply = waitlist.join(source=SOURCE, **posted)
	except frappe.ValidationError as error:
		# The exception is swallowed here, so the rollback the framework would do on the way out is ours.
		frappe.db.rollback()
		state["form_error"] = strip_html(cstr(error)).strip()
		return state

	state.update(submitted=True, reference=reply["reference"], submitted_email=posted.email)
	return state


def posted_values() -> frappe._dict:
	form = frappe.form_dict
	values = frappe._dict({field: cstr(form.get(field)).strip() for field in FORM_FIELDS})
	# An unticked checkbox posts nothing at all, so the absent case has to become 0 here.
	values.consented = cint(form.get("consented"))
	return values


def select_field(fieldname: str) -> frappe._dict:
	# Read off the meta, because `waitlist.match_option` matches the answer against this same list.
	field = frappe.get_meta(WAITLIST_DOCTYPE).get_field(fieldname)
	options = [line.strip() for line in cstr(field.options).split("\n") if line.strip()]
	fallback = options[0] if options else ""
	return frappe._dict(options=options, default=cstr(field.default) or fallback)


# Seed content: what an unset field falls back to, and what the seeder writes.

INTRO_BODY = (
	"Hosted accounts are approved manually while we keep capacity honest — usually within one "
	"business day. Tell us what you plan to run and we will either open the account or say why not."
)

PENDING_BODY = (
	"We read every request by hand. If it fits the capacity we have, you will get a login link, "
	"usually within one business day. If it doesn't, you will get a plain answer instead of silence."
)

SELFHOST_NOTE = (
	"<p><b>Don't want to wait?</b> Self-hosting needs no account and no approval — clone the repo, "
	"run <code>./setup.sh</code>, and you are running the same code we host.</p>"
)

SIGNUP_SEED = {
	"badge_text": "Reviewed by a human",
	"title": "Request access to hosted BenchPress.",
	"intro_body": INTRO_BODY,
	"signup_steps": [
		{
			"step_number": 1,
			"title": "You tell us what you plan to run",
			"body": "Apps, Frappe version, how many people need environments. Two minutes of typing.",
		},
		{
			"step_number": 2,
			"title": "We read it and decide",
			"body": "A person checks capacity and fit. Usually within one business day, and always with an answer either way.",
		},
		{
			"step_number": 3,
			"title": "Approved accounts start with a credit balance",
			"body": "Enough for a few environments and a week of poking. Deploys are free; failed builds cost nothing.",
		},
	],
	"selfhost_note": SELFHOST_NOTE,
	"form_title": "Access request",
	"form_subtitle": "All fields except the message are required.",
	"form_privacy_note": "We use this to decide on access and nothing else. No newsletter.",
	"form_submit_label": "Send request",
	"form_login_prompt": "Already approved?",
	"pending_title": "Request received — pending review",
	"pending_body": PENDING_BODY,
	"pending_links": [
		{
			"icon": "github",
			"text": "While you wait, the repo is public — clone it and self-host the same code for free.",
			"url": REPO_URL,
		},
		{
			"icon": "book-open",
			"text": "The self-hosting guide covers Docker, WireGuard and the first template end to end.",
			"url": DOCS_URL,
		},
	],
	"pending_back_label": "Back to the form",
	"meta_title": DEFAULT_TITLE,
	"meta_description": INTRO_BODY,
	"og_image": "",
}
