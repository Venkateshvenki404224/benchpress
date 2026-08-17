# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Best-effort notices to a document's owner — one desk alert, one email.

Both are best-effort by design: a notification failure must never disturb the outcome it is
describing. A deploy that worked and could not be announced is still a deploy that worked, and a
reaped instance whose warning email bounced is still reaped.

`notify_owner` is the desk alert. type "Alert" both bypasses the `for_user == from_user` skip in
`make_notification_logs` — a background job usually runs as the owner — and is exempt from
notification emails, so it stays inside Desk.

`email_owner` is for a notice that must outlive the session: nobody watching the sidebar at 3am
will see an alert about an instance being deleted in two days.
"""

import frappe


def notify_owner(user: str, subject: str, document_type: str, document_name: str) -> None:
	"""A desk alert on the document. Never raises."""
	try:
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		enqueue_create_notification(
			[_email_of(user)],
			{
				"type": "Alert",
				"subject": subject,
				"document_type": document_type,
				"document_name": document_name,
			},
		)
	except Exception:
		frappe.log_error(
			title=f"BenchPress notification failed: {document_name}",
			message=frappe.get_traceback(),
		)


def email_owner(user: str, subject: str, message: str) -> None:
	"""One queued email. Never raises — a site with no outgoing account must still function."""
	try:
		frappe.sendmail(recipients=[_email_of(user)], subject=subject, message=message, delayed=True)
	except Exception:
		frappe.log_error(title=f"BenchPress email failed: {subject}", message=frappe.get_traceback())


def _email_of(user: str) -> str:
	return frappe.db.get_value("User", user, "email") or user
