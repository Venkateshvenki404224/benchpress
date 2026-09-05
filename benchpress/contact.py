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
# The mail names the window for the topic; the page says nothing narrower than every topic keeps.
SUCCESS_BODY = (
	"Thanks — it is in front of a person, not a queue. Most messages get an answer within one business day."
)
MAIL_ERROR_TITLE = "BenchPress contact mail failed"

# Two different addresses. `NOTIFY_KEY` is where submissions are forwarded and is never shown;
# `PUBLIC_KEY` is what the page prints and the JSON-LD publishes. Conflating them puts an
# operator's personal inbox on a public page.
NOTIFY_KEY = "benchpress_contact_email"
PUBLIC_KEY = "benchpress_public_email"

ACKNOWLEDGE_SENDER = True

# One row per chip the form offers: the label, where the message goes, and the window the
# acknowledgement promises. Held together so a label cannot drift from its window.
TOPICS = (
	{"label": "Hosted access", "route_to_email": "", "window": "1 business day"},
	{"label": "Setup or migration", "route_to_email": "", "window": "1 business day"},
	{"label": "Custom app work", "route_to_email": "", "window": "1 business day"},
	{"label": "Bug or issue", "route_to_email": "", "window": "2–3 days"},  # noqa: RUF001 -- verbatim spec copy
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
	return topic_row(topic).get("route_to_email") or notify_email()


def response_window(topic: str) -> str:
	"""What the acknowledgement promises. A topic no longer offered reads the default chip."""
	return topic_row(topic).get("window") or topic_row(default_topic()).get("window", "")


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


def topic_row(label: str) -> dict:
	"""The row behind a chip, empty when the form no longer offers that label."""
	return next((row for row in TOPICS if row["label"] == label), {})


def require_text(value, error: str) -> str:
	text = cstr(value).strip()
	if not text:
		frappe.throw(error, frappe.ValidationError)
	return text
