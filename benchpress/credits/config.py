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

# Where every refusal and every stop notice sends somebody who wants to keep going. One constant,
# so the sentence and the router entry can never drift apart.
TOP_UP_ROUTE = "/frontend/credits"

# Where a stranger goes to become a user. Frappe's own login page carries the email form, the
# OAuth buttons for every enabled `Social Login Key` and the verification mail, so self-serve
# signup is a route we point at rather than a page we own.
SIGNUP_ROUTE = "/login#signup"


def settings():
	"""`Credit Settings`, served from cache. Never `get_doc`, never inside a loop."""
	return frappe.get_cached_doc(SETTINGS)


def credits_enabled() -> bool:
	"""The master switch. Off on a fresh site, and off means the feature does not exist."""
	return bool(frappe.get_cached_doc(BENCHPRESS_SETTINGS).enable_credits)


def waitlist_open() -> bool:
	"""Whether hosted access is still invite-only.

	One switch drives both doors, because they are the same door: while it is on the landing page
	shows the waitlist form and `signup.sign_up` refuses; off, the CTA becomes "Start free" and
	the waitlist refuses instead. Two flags would let a site offer a waitlist that signup had
	already made pointless, and there is no state in which both should accept a stranger.
	"""
	return bool(settings().waitlist_open)


def blocked_email_domains() -> set[str]:
	"""Domains an email signup may not use, lower-cased and without a leading `@`.

	Data rather than a bundled list: the afternoon a throwaway-address farm shows up, the fix has
	to be one line typed into Desk, not a deploy.
	"""
	lines = cstr(settings().blocked_email_domains).splitlines()
	return {line.strip().lower().lstrip("@") for line in lines if line.strip()}


def default_size():
	"""The one `Instance Size` flagged `is_default`, or `None` if none is."""
	return size_index().get("default")


def size_by_name(name):
	"""One `Instance Size` by name, or `None` — the top rung of the deploy's resolution chain."""
	return size_index()["by_name"].get(name) if name else None


def size_for_lab(lab_doc):
	"""The `Instance Size` a Lab deploys at. Falls back to its resources, then to the default.

	The chosen size wins: `Lab.instance_size` is what the user picked and paid attention to the
	price of. Resources are the fallback for a lab written before sizes existed, or hand-tuned by
	a self-hoster, and the patch that mapped existing labs used exactly the same rule.

	One indexed read builds the whole lookup table per request, so this stays O(1) per call and
	never becomes an N+1 when pricing a list of labs.
	"""
	index = size_index()
	chosen = index["by_name"].get(lab_doc.get("instance_size"))
	if chosen:
		return chosen
	key = size_key(lab_doc.get("memory_limit"), lab_doc.get("cpu_cores"))
	return index["by_resources"].get(key) or index["default"]


def size_for_instance(bench_doc):
	"""The `Instance Size` a bench was deployed at — what billing prices, not what its Lab now says.

	A Lab may be re-pointed at another size while a bench of the old one is still running, so the
	price has to follow the numbers Docker was actually given. Falls back to the Lab for a bench
	that predates the recorded size.
	"""
	chosen = size_index()["by_name"].get(bench_doc.get("instance_size"))
	if chosen:
		return chosen
	return size_for_lab(frappe.get_cached_doc("Lab", bench_doc.get("lab")))


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
	"""`{"rows", "by_name", "by_resources", "default"}` — built once per request."""
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
			"price_multiplier",
			"default_lease_plan",
			"max_sites",
			"pids_limit",
			"iops_limit",
			"bps_limit",
			"disk_limit",
			"include_code_server",
			"inflight_limit",
			"rate_average",
			"rate_burst",
			"is_default",
			"sort_order",
		],
		order_by="sort_order asc",
	)
	return {
		"rows": rows,
		"by_name": {row.name: row for row in rows},
		"by_resources": {size_key(row.memory_limit, row.cpu_cores): row for row in rows},
		"default": next((row for row in rows if row.is_default), None),
	}
