# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

no_cache = 1


def get_context(context):
	"""Boot payload for the SPA shell — frappe-ui reads window.csrf_token from it."""
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep -- get_csrf_token writes the session store; the shell renders before the request transaction commits
	context.boot = {"csrf_token": csrf_token}
	return context
