# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One email to the operator when a deploy or a teardown fails."""

import frappe
from frappe.utils import escape_html, get_url_to_form

SETTINGS = "BenchPress Settings"
FAILURE_LIMIT = 300


def alert_operator(subject: str, text: str) -> None:
	"""Queue one email to the operator address. Never raises; a no-op while the address is unset."""
	try:
		recipient = frappe.db.get_single_value(SETTINGS, "operator_alert_email")
		if not recipient:
			return
		frappe.sendmail(
			recipients=[recipient], subject=subject, message=f"<pre>{escape_html(text)}</pre>", delayed=True
		)
	except Exception:
		frappe.log_error(title=f"BenchPress operator alert failed: {subject}", message=frappe.get_traceback())


def deploy_failed(bench, lab_title: str, reason: str) -> None:
	"""Tell the operator a deploy failed: whose it was, and the first part of why."""
	alert_operator(
		f"BenchPress deploy failed: {lab_title}",
		f"Owner: {bench.owner}\n{get_url_to_form('Bench Instance', bench.name)}\n\n{reason[:FAILURE_LIMIT]}",
	)
