# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Transactional mail for the public site — six operator-editable `Email Template` rows."""

import functools

import frappe
from frappe.utils import cint, format_datetime, get_url, get_url_to_form
from markupsafe import Markup, escape

from benchpress.benchpress.site_content import REPO_URL
from benchpress.credits import config
from benchpress.permissions import ADMIN_ROLES

WAITLIST = "Waitlist Entry"
CONTACT = "Contact Message"
CONTACT_SETTINGS = "Contact Page Settings"

ACCESS_RECEIVED = "BenchPress Access Request Received"
ACCESS_FILED = "BenchPress Access Request Filed"
ACCESS_APPROVED = "BenchPress Access Approved"
ACCESS_DECLINED = "BenchPress Access Declined"
CONTACT_RECEIVED = "BenchPress Contact Message Received"
CONTACT_FILED = "BenchPress Contact Message Filed"

TEMPLATE_DIR = "benchpress/templates/emails"

# Template name -> (subject, body file). The file is both the fallback body and the Desk seed.
DEFAULTS = {
	ACCESS_RECEIVED: ("Your BenchPress access request — {{ reference }}", "access_request_received.html"),
	ACCESS_FILED: ("Access request from {{ full_name }} ({{ company }})", "access_request_filed.html"),
	ACCESS_APPROVED: ("Your BenchPress account is open", "access_approved.html"),
	ACCESS_DECLINED: ("About your BenchPress access request", "access_declined.html"),
	CONTACT_RECEIVED: ("We got your message", "contact_received.html"),
	CONTACT_FILED: ("[{{ topic }}] {{ sender_name }}", "contact_filed.html"),
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
	"""Tell the admins a request is waiting, with every field they need to decide."""
	context = _request_context(entry)
	context["desk_url"] = get_url_to_form(WAITLIST, entry.name)
	context["submitted_on"] = _timestamp(entry.get("creation"))
	_send(ACCESS_FILED, admin_recipients(), context, WAITLIST, entry.name)


@best_effort
def send_access_request_approved(entry) -> None:
	"""The decision, never a credential — Frappe's welcome mail carries the password link."""
	context = _request_context(entry)
	context["free_credits"] = cint(config.settings().signup_grant_credits)
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
	"""Acknowledge a contact message, unless acknowledgements are off."""
	if not _acknowledges_sender():
		return
	_send(CONTACT_RECEIVED, [message.email], _contact_context(message), CONTACT, message.name)


@best_effort
def notify_admins_of_contact(message) -> None:
	"""Route one contact message to whoever owns its topic."""
	context = _contact_context(message)
	context["desk_url"] = get_url_to_form(CONTACT, message.name)
	context["submitted_on"] = _timestamp(message.get("creation"))
	recipients = _contact_notice_recipients(message.get("topic"))
	_send(CONTACT_FILED, recipients, context, CONTACT, message.name, reply_to=message.email)


def admin_recipients() -> list[str]:
	"""Enabled system users holding an admin role; the contact notify address when there are none."""
	has_role = frappe.qb.DocType("Has Role")
	user = frappe.qb.DocType("User")
	addresses = (
		frappe.qb.from_(has_role)
		.join(user)
		.on(has_role.parent == user.name)
		.select(user.email)
		.distinct()
		.where(has_role.parenttype == "User")
		.where(has_role.role.isin(list(ADMIN_ROLES)))
		.where(user.enabled == 1)
		.where(user.user_type == "System User")
		.where(user.email.notnull())
		.where(user.email != "")
	).run(pluck=True)
	return sorted(set(addresses)) or _fallback_recipients()


def seed_rows() -> list[dict]:
	"""The six `Email Template` records as the seed hook should insert them."""
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
	"""The shipped body for one template, read from `templates/emails/`."""
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
		"response_window": _response_window(topic),
		**_urls(),
	}


def _urls() -> dict:
	return {
		"site_url": get_url(),
		"login_url": get_url("/login"),
		"docs_url": "https://benchpress.cloud/docs",
		"repo_url": REPO_URL,
	}


def _reference(entry) -> str:
	"""`REQ-XXXX-XXXX`, derived by the controller. Blank if the controller has no such method."""
	derive = getattr(entry, "request_reference", None)
	return derive() if callable(derive) else ""


def _contact_notice_recipients(topic: str) -> list[str]:
	"""The topic's own address, then the page's notify address, then whoever holds a role."""
	route = _topic_route(topic)
	if route:
		return [route]
	notify = _contact_setting("notify_email")
	return [notify] if notify else admin_recipients()


def _topic_route(topic: str) -> str:
	rows = getattr(_contact_settings(), "topics", None) or []
	for row in rows:
		if topic and row.label == topic and row.route_to_email:
			return row.route_to_email
	return ""


def _response_window(topic: str) -> str:
	"""The window whose subject matches the topic, else the first row's."""
	rows = getattr(_contact_settings(), "response_times", None) or []
	for row in rows:
		if topic and row.subject == topic:
			return row.window
	return rows[0].window if rows else ""


def _acknowledges_sender() -> bool:
	"""Checked by default, including on a never-saved Single."""
	value = _contact_setting("acknowledge_sender")
	return True if value is None else bool(cint(value))


def _fallback_recipients() -> list[str]:
	notify = _contact_setting("notify_email")
	return [notify] if notify else []


def _contact_setting(fieldname: str):
	"""One `Contact Page Settings` field, `None` when the doctype is not installed yet."""
	# Read off the document, not `get_single_value`, which casts a missing row to 0 — reading an
	# unset `acknowledge_sender` as switched off.
	settings = _contact_settings()
	return settings.get(fieldname) if settings else None


def _contact_settings():
	try:
		return frappe.get_cached_doc(CONTACT_SETTINGS)
	except Exception:
		return None


def _timestamp(value) -> str:
	return format_datetime(value) if value else ""


def _lines(value) -> Markup:
	"""Free text as safe HTML: escaped once, newlines kept."""
	# `Markup` because these templates render without autoescape, so `{{ message }}` in Desk must
	# not become a way to render markup a guest typed into the form.
	if not value:
		return Markup("")
	return Markup("<br>").join(escape(str(value)).split("\n"))
