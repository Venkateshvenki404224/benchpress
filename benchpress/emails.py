# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Transactional mail — seven operator-editable `Email Template` rows."""

import functools

import frappe
from frappe.utils import cint, format_datetime, get_url, get_url_to_form
from markupsafe import Markup, escape

from benchpress import contact
from benchpress.benchpress.site_content import REPO_URL, asset_version
from benchpress.credits import config

WAITLIST = "Waitlist Entry"
CONTACT = "Contact Message"

ACCESS_RECEIVED = "BenchPress Access Request Received"
ACCESS_FILED = "BenchPress Access Request Filed"
ACCESS_APPROVED = "BenchPress Access Approved"
ACCESS_DECLINED = "BenchPress Access Declined"
CONTACT_RECEIVED = "BenchPress Contact Message Received"
CONTACT_FILED = "BenchPress Contact Message Filed"
PASSWORD_RESET = "BenchPress Password Reset"

TEMPLATE_DIR = "benchpress/templates/emails"

# The header lockup, in the one variant that reads on the dark bar the templates draw it on.
LOGO_PATH = "/assets/benchpress/images/logo/wordmark-on-dark.png"

# Template name -> (subject, body file). The file is both the fallback body and the Desk seed.
DEFAULTS = {
	ACCESS_RECEIVED: ("Your BenchPress access request — {{ reference }}", "access_request_received.html"),
	ACCESS_FILED: ("Access request from {{ full_name }} ({{ company }})", "access_request_filed.html"),
	ACCESS_APPROVED: ("Your BenchPress account is open", "access_approved.html"),
	ACCESS_DECLINED: ("About your BenchPress access request", "access_declined.html"),
	CONTACT_RECEIVED: ("We got your message", "contact_received.html"),
	CONTACT_FILED: ("[{{ topic }}] {{ sender_name }}", "contact_filed.html"),
	PASSWORD_RESET: ("Reset your BenchPress password", "password_reset.html"),
}

NO_COMPANY = "no company"


def best_effort(send):
	"""Log and swallow anything a send raises."""

	@functools.wraps(send)
	def guarded(*args, **kwargs):
		try:
			return send(*args, **kwargs)
		except Exception:
			frappe.log_error(
				title=f"BenchPress email failed: {send.__name__}", message=frappe.get_traceback()
			)

	return guarded


@best_effort
def send_access_request_received(entry) -> None:
	"""Acknowledge one access request to the person who filed it."""
	_send(ACCESS_RECEIVED, [entry.name], _request_context(entry), WAITLIST, entry.name)


@best_effort
def notify_admins_of_access_request(entry) -> None:
	"""Tell the operator a request is waiting, with every field they need to decide."""
	context = _request_context(entry)
	context["desk_url"] = get_url_to_form(WAITLIST, entry.name)
	context["submitted_on"] = _timestamp(entry.get("creation"))
	address = contact.notify_email()
	if address:
		_send(ACCESS_FILED, [address], context, WAITLIST, entry.name)


@best_effort
def send_access_request_approved(entry, set_password_url: str = "") -> None:
	"""The decision and the way in, in one mail — a second mail can be undone by a stalled queue."""
	context = _request_context(entry)
	context["free_credits"] = cint(config.settings().signup_grant_credits)
	context["set_password_url"] = set_password_url
	_send(ACCESS_APPROVED, [entry.name], context, WAITLIST, entry.name)


@best_effort
def send_access_request_rejected(entry) -> None:
	"""Tell one applicant their request was declined."""
	context = _request_context(entry)
	context["rejection_reason"] = _lines(entry.get("rejection_reason"))
	_send(ACCESS_DECLINED, [entry.name], context, WAITLIST, entry.name)


# Both spellings are in use by callers.
send_access_request_declined = send_access_request_rejected


@best_effort
def send_contact_received(message) -> None:
	"""Acknowledge one contact message to the person who sent it."""
	_send(CONTACT_RECEIVED, [message.email], _contact_context(message), CONTACT, message.name)


@best_effort
def notify_admins_of_contact(message) -> None:
	"""Route one contact message to whoever owns its topic."""
	context = _contact_context(message)
	context["desk_url"] = get_url_to_form(CONTACT, message.name)
	context["submitted_on"] = _timestamp(message.get("creation"))
	recipients = [contact.route_for(message.get("topic"))]
	_send(CONTACT_FILED, recipients, context, CONTACT, message.name, reply_to=message.email)


def send_password_reset(user, link: str) -> None:
	"""Frappe's own reset mail, in BenchPress's chrome. Raises so the caller can report a failure."""
	body = _render(
		PASSWORD_RESET,
		{"full_name": user.get_fullname() or user.name, "email": user.name, "reset_url": link, **_urls()},
	)
	frappe.sendmail(
		recipients=[user.name],
		subject=body["subject"],
		message=body["message"],
		now=True,
		redact_message_after_send=True,
	)


def seed_rows() -> list[dict]:
	"""The seven `Email Template` records as the seed hook should insert them."""
	# `use_html`, or the Text Editor would rewrite these hand-built tables on the first save.
	return [
		{
			"doctype": "Email Template",
			"name": name,
			"subject": subject,
			"use_html": 1,
			"response_html": default_body(name),
		}
		for name, (subject, _file) in DEFAULTS.items()
	]


def default_body(template_name: str) -> str:
	_subject, filename = DEFAULTS[template_name]
	path = frappe.get_app_path("benchpress", "templates", "emails", filename)
	# nosemgrep -- the filename comes from DEFAULTS, never from a request
	with open(path, encoding="utf-8") as body:
		return body.read()


def _send(template_name, recipients, context, doctype, name, reply_to=None) -> None:
	"""Queue one rendered email. Silent when nobody is listening."""
	recipients = [address for address in (recipients or []) if address]
	if not recipients:
		return
	body = _render(template_name, context)
	# Never raises: a site with no outgoing account must still accept the signup or the message.
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=body["subject"],
			message=body["message"],
			reference_doctype=doctype,
			reference_name=name,
			reply_to=reply_to,
			delayed=True,
		)
	except Exception:
		frappe.log_error(title=f"BenchPress mail failed: {template_name}", message=frappe.get_traceback())


def _render(template_name: str, context: dict) -> dict:
	"""The Desk row when it exists, the shipped body when it was deleted."""
	if frappe.db.exists("Email Template", template_name):
		return frappe.get_cached_doc("Email Template", template_name).get_formatted_email(context)
	subject, filename = DEFAULTS[template_name]
	return {
		# nosemgrep -- the subject is a DEFAULTS literal
		"subject": frappe.render_template(subject, context),
		# nosemgrep -- the path is built from DEFAULTS, never from a request
		"message": frappe.render_template(f"{TEMPLATE_DIR}/{filename}", context),
	}


def _request_context(entry) -> dict:
	"""One access request, as the four waitlist templates read it."""
	return {
		# `get_formatted_email` matches an outgoing account on this when `use_html` is set.
		"doctype": WAITLIST,
		"full_name": entry.get("full_name") or entry.name.split("@")[0],
		"email": entry.name,
		"reference": _reference(entry),
		"company": entry.get("company") or NO_COMPANY,
		"team_size": entry.get("team_size") or "",
		"intent": entry.get("intent") or "",
		"expected_apps": entry.get("expected_apps") or "",
		"use_case": _lines(entry.get("use_case")),
		**_urls(),
	}


def _contact_context(message) -> dict:
	"""One contact message, as the two contact templates read it."""
	topic = message.get("topic") or ""
	return {
		"doctype": CONTACT,
		"sender_name": message.get("sender_name") or "",
		"email": message.email,
		"topic": topic,
		"message": _lines(message.get("message")),
		"response_window": contact.response_window(topic),
		**_urls(),
	}


def _urls() -> dict:
	return {
		"site_url": get_url(),
		"login_url": get_url("/login"),
		"logo_url": f"{get_url(LOGO_PATH)}?v={asset_version()}",
		"docs_url": "https://benchpress.cloud/docs",
		"repo_url": REPO_URL,
	}


def _reference(entry) -> str:
	"""`REQ-XXXX-XXXX`, derived by the controller. Blank if the controller has no such method."""
	derive = getattr(entry, "request_reference", None)
	return derive() if callable(derive) else ""


def _timestamp(value) -> str:
	return format_datetime(value) if value else ""


def _lines(value) -> Markup:
	"""Free text as safe HTML: escaped once, newlines kept."""
	# `Markup` because these templates render without autoescape, so `{{ message }}` in Desk must
	# not become a way to render markup a guest typed into the form.
	if not value:
		return Markup("")
	return Markup("<br>").join(escape(str(value)).split("\n"))
