# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Memoise a value for the life of one request or job — never in a module global.

Workers are forked, so a module-level dict outlives the request that filled it and leaks into
every later job in the same process. `frappe.local` is torn down with the request, which is
exactly the lifetime a lookup table wants: built once, reused by every call in the same run,
gone afterwards.
"""

import frappe


def local_cache(attribute: str, build):
	"""The value cached under `attribute`, built on its first use in this request."""
	if not hasattr(frappe.local, attribute):
		setattr(frappe.local, attribute, build())
	return getattr(frappe.local, attribute)


def clear_local_cache(attribute: str) -> None:
	"""Drop the cached value so the next read rebuilds it."""
	if hasattr(frappe.local, attribute):
		delattr(frappe.local, attribute)
