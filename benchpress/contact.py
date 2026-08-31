# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The contact form: one guest-writable endpoint, and the admin action that closes a message."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr, now_datetime

from benchpress.benchpress.doctype.contact_message.contact_message import ANSWERED
from benchpress.benchpress.doctype.waitlist_entry.waitlist_entry import normalise_email
from benchpress.permissions import require_admin

DOCTYPE = "Contact Message"
SETTINGS = "Contact Page Settings"
MESSAGES_PER_HOUR = 3
SUCCESS_BODY = "Thanks — it is in front of a person, not a queue. You will hear back within one business day."
MAIL_ERROR_TITLE = "BenchPress contact mail failed"


# Guest-writable by design; answers identically for every caller and is rate limited per IP and
# address.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep -- reviewed, see the note above
@rate_limit(key="email", limit=MESSAGES_PER_HOUR, seconds=60 * 60, ip_based=True)
def submit(name: str, email: str, message: str, topic: str | None = None) -> dict:
	"""Record one contact message. Always answers the same way."""
	settings = page_settings()
	record = frappe.new_doc(DOCTYPE)
	record.update(
		{
			"sender_name": require_text(name, _("Tell us who to reply to.")),
			"email": normalise_email(email),
			"topic": settings.resolve_topic(topic),
			"message": require_text(message, _("Write a message before sending.")),
		}
	)
	record.insert(ignore_permissions=True)
	announce(record, bool(settings.acknowledge_sender))
	return {"sent": True, "message": settings.form_success_body or SUCCESS_BODY}


@frappe.whitelist()
def mark_answered(messages: str | list) -> dict:
	"""Desk bulk action: close the selected messages. Admins only."""
	require_admin()
	names = frappe.parse_json(messages)
	for name in names:
		close(name)
	return {"answered": len(names)}


def close(name: str) -> None:
	"""Stamp who answered and when."""
	frappe.db.set_value(
		DOCTYPE,
		name,
		{"status": ANSWERED, "answered_on": now_datetime(), "answered_by": frappe.session.user},
	)


def page_settings():
	"""The Single that owns every string on /contact."""
	return frappe.get_cached_doc(SETTINGS)


def announce(record, acknowledge_sender: bool) -> None:
	"""Tell the sender and the admins. Both best effort: mail must never lose a message."""
	# Imported here so a broken or missing mailer cannot take the contact form down with it.
	try:
		from benchpress import emails
	except Exception:
		frappe.log_error(title=MAIL_ERROR_TITLE, message=frappe.get_traceback())
		return

	if acknowledge_sender:
		send_quietly(emails.send_contact_received, record)
	send_quietly(emails.notify_admins_of_contact, record)


def send_quietly(mailer, record) -> None:
	try:
		mailer(record)
	except Exception:
		frappe.log_error(title=MAIL_ERROR_TITLE, message=frappe.get_traceback())


def require_text(value, error: str) -> str:
	"""Throw on a blank required field."""
	text = cstr(value).strip()
	if not text:
		frappe.throw(error, frappe.ValidationError)
	return text
