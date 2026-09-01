# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

CONFIG_KEY = "benchpress_public_site"


def public_site_enabled() -> bool:
	return bool(frappe.conf.get(CONFIG_KEY))


def require_public_site() -> None:
	# Not found rather than forbidden: without the key these routes and endpoints do not exist.
	if not public_site_enabled():
		raise frappe.PageDoesNotExistError
