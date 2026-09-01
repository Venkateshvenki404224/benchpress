# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The analytics gate. No config, no tracker, no third-party request."""

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
