# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The analytics gate. No config, no tracker, no third-party request."""

from html import escape

import frappe
from frappe.utils import cstr

SCRIPT_KEY = "benchpress_analytics_script"
DOMAIN_KEY = "benchpress_analytics_domain"


def tracker() -> dict:
	"""The script URL and site id for this deployment, or empty when none is configured."""
	script = cstr(frappe.conf.get(SCRIPT_KEY)).strip()
	website_id = cstr(frappe.conf.get(DOMAIN_KEY)).strip()
	if not script or not website_id:
		return {}
	return {"script": script, "website_id": website_id}


def website_context(context) -> dict:
	"""Every website route, docs included — the wiki renders through the same context."""
	snippet = script_tag()
	if not snippet:
		return {}
	return {"head_html": (context.get("head_html") or "") + snippet}


def script_tag() -> str:
	values = tracker()
	if not values:
		return ""
	return '<script defer src="{0}" data-website-id="{1}"></script>'.format(
		escape(values["script"], quote=True), escape(values["website_id"], quote=True)
	)
