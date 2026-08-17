# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The single read path for every commercial number.

Every rate, cap and price is data — `Credit Settings`, `Instance Size`, `Credit Pack` — so an
operator retunes the economics in Desk without a deploy. No rate literal belongs anywhere else
in the codebase; call these accessors instead.

Reads go through `frappe.get_cached_doc`, which serves the Singles from Redis, so a rate lookup
in a request path never hits the database. The `Instance Size` lookup table is memoised on
`frappe.local` for the life of one request rather than in a module global, because workers are
forked and a module global would outlive the request that built it.
"""

import frappe
from frappe.utils import cint, cstr

from benchpress.request_cache import clear_local_cache, local_cache

SETTINGS = "Credit Settings"
BENCHPRESS_SETTINGS = "BenchPress Settings"
SIZE_INDEX_ATTRIBUTE = "benchpress_instance_size_index"


def settings():
	"""`Credit Settings`, served from cache. Never `get_doc`, never inside a loop."""
	return frappe.get_cached_doc(SETTINGS)


def credits_enabled() -> bool:
	"""The master switch. Off on a fresh site, and off means the feature does not exist."""
	return bool(frappe.get_cached_doc(BENCHPRESS_SETTINGS).enable_credits)


def default_size():
	"""The one `Instance Size` flagged `is_default`, or `None` if none is."""
	return size_index().get("default")


def size_for_lab(lab_doc):
	"""Resolve a Lab's memory and cores to an `Instance Size`. Falls back to the default.

	One indexed read builds the whole lookup table per request, so this stays O(1) per call
	and never becomes an N+1 when pricing a list of labs.
	"""
	index = size_index()
	key = size_key(lab_doc.memory_limit, lab_doc.cpu_cores)
	return index["by_resources"].get(key) or index["default"]


def instance_sizes() -> list[dict]:
	"""Every size in display order. Shares the request-scoped index, so it costs no extra query."""
	return size_index()["rows"]


def active_packs() -> list[dict]:
	"""Purchasable packs in display order. Read by the landing page and the buy dialog."""
	return frappe.get_all(
		"Credit Pack",
		filters={"is_active": 1},
		fields=["name", "pack_label", "inr_price", "credits", "highlight", "sort_order"],
		order_by="sort_order asc, inr_price asc",
	)


def size_key(memory_limit, cpu_cores) -> tuple[str, int]:
	"""Normalise a (memory, cores) pair so `1G` and `1g` resolve to the same size."""
	return (cstr(memory_limit).strip().lower(), cint(cpu_cores))


def size_index() -> dict:
	"""`{"by_resources": {(memory, cores): row}, "default": row | None}`, once per request."""
	return local_cache(SIZE_INDEX_ATTRIBUTE, build_size_index)


def clear_size_index() -> None:
	"""Drop the memoised table so a size edited in this request is seen by the next read."""
	clear_local_cache(SIZE_INDEX_ATTRIBUTE)


def build_size_index() -> dict:
	rows = frappe.get_all(
		"Instance Size",
		fields=[
			"name",
			"size_label",
			"memory_limit",
			"cpu_cores",
			"credits_per_hour",
			"max_sites",
			"is_default",
			"sort_order",
		],
		order_by="sort_order asc",
	)
	return {
		"rows": rows,
		"by_resources": {size_key(row.memory_limit, row.cpu_cores): row for row in rows},
		"default": next((row for row in rows if row.is_default), None),
	}
