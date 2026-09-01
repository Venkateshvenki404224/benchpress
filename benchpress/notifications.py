# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Best-effort notices to a document's owner — one desk alert, one email."""

import frappe


def notify_owner(user: str, subject: str, document_type: str, document_name: str) -> None:
	"""A desk alert on the document. Never raises."""
	try:
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		# "Alert" bypasses the `for_user == from_user` skip in `make_notification_logs` and sends no
		# email of its own.
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
	"""One queued email. Never raises."""
	try:
		frappe.sendmail(recipients=[_email_of(user)], subject=subject, message=message, delayed=True)
	except Exception:
		frappe.log_error(title=f"BenchPress email failed: {subject}", message=frappe.get_traceback())


def _email_of(user: str) -> str:
	return frappe.db.get_value("User", user, "email") or user
