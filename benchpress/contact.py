# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The contact form: one guest-writable endpoint, and the admin action that closes a message."""

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime

from benchpress.benchpress.doctype.contact_message.contact_message import ANSWERED
from benchpress.benchpress.doctype.waitlist_entry.waitlist_entry import normalise_email
from benchpress.permissions import require_admin
from benchpress.public_site import require_public_site
from benchpress.throttle import public_form

DOCTYPE = "Contact Message"
MESSAGES_PER_HOUR = 3
SUCCESS_BODY = "Thanks — it is in front of a person, not a queue. You will hear back within one business day."
MAIL_ERROR_TITLE = "BenchPress contact mail failed"

# Two different addresses. `NOTIFY_KEY` is where submissions are forwarded and is never shown;
# `PUBLIC_KEY` is what the page prints and the JSON-LD publishes. Conflating them puts an
# operator's personal inbox on a public page.
NOTIFY_KEY = "benchpress_contact_email"
PUBLIC_KEY = "benchpress_public_email"

ACKNOWLEDGE_SENDER = True

TOPICS = (
	{"label": "Hosted access", "route_to_email": ""},
	{"label": "Setup or migration", "route_to_email": ""},
	{"label": "Custom app work", "route_to_email": ""},
	{"label": "Bug or issue", "route_to_email": ""},
)

RESPONSE_TIMES = (
	{"subject": "Hosted access requests", "window": "1 business day"},
	{"subject": "Sales and quotes", "window": "1 business day"},
	{"subject": "GitHub issues", "window": "2–3 days"},  # noqa: RUF001 -- verbatim spec copy
)


# Guest-writable by design; answers identically for every caller and is rate limited per IP and
# address.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep -- reviewed, see the note above
@public_form(limit=MESSAGES_PER_HOUR)
def submit(name: str, email: str, message: str, topic: str | None = None) -> dict:
	"""Record one contact message. Always answers the same way."""
	require_public_site()
	record = frappe.new_doc(DOCTYPE)
	record.update(
		{
			"sender_name": require_text(name, _("Tell us who to reply to.")),
			"email": normalise_email(email),
			"topic": resolve_topic(topic),
			"message": require_text(message, _("Write a message before sending.")),
		}
	)
	record.insert(ignore_permissions=True)
	announce(record)
	return {"sent": True, "message": SUCCESS_BODY}


def notify_email() -> str:
	"""Where a submission is forwarded. Empty means nobody has said, so nothing is sent."""
	return cstr(frappe.conf.get(NOTIFY_KEY)).strip()


def public_email() -> str:
	"""The address the page prints. Empty means the site offers the form and GitHub instead."""
	return cstr(frappe.conf.get(PUBLIC_KEY)).strip()


def default_topic() -> str:
	"""The first row; the page opens with this chip selected."""
	return TOPICS[0]["label"] if TOPICS else ""


def resolve_topic(label: str | None) -> str:
	submitted = cstr(label).strip()
	return submitted if any(row["label"] == submitted for row in TOPICS) else default_topic()


def route_for(topic: str) -> str:
	routed = next((row["route_to_email"] for row in TOPICS if row["label"] == topic), "")
	return routed or notify_email()


def response_window(topic: str) -> str:
	matched = next((row["window"] for row in RESPONSE_TIMES if row["subject"] == topic), "")
	return matched or (RESPONSE_TIMES[0]["window"] if RESPONSE_TIMES else "")


@frappe.whitelist()
def mark_answered(messages: str | list) -> dict:
	"""Desk bulk action: close the selected messages. Admins only."""
	require_admin()
	names = frappe.parse_json(messages)
	for name in names:
		close(name)
	return {"answered": len(names)}


def close(name: str) -> None:
	frappe.db.set_value(
		DOCTYPE,
		name,
		{"status": ANSWERED, "answered_on": now_datetime(), "answered_by": frappe.session.user},
	)


def announce(record) -> None:
	"""Tell the sender and the admins. Both best effort: mail must never lose a message."""
	# Imported here so a broken or missing mailer cannot take the contact form down with it.
	try:
		from benchpress import emails
	except Exception:
		frappe.log_error(title=MAIL_ERROR_TITLE, message=frappe.get_traceback())
		return

	if ACKNOWLEDGE_SENDER:
		send_quietly(emails.send_contact_received, record)
	send_quietly(emails.notify_admins_of_contact, record)


def send_quietly(mailer, record) -> None:
	try:
		mailer(record)
	except Exception:
		frappe.log_error(title=MAIL_ERROR_TITLE, message=frappe.get_traceback())


def require_text(value, error: str) -> str:
	text = cstr(value).strip()
	if not text:
		frappe.throw(error, frappe.ValidationError)
	return text
