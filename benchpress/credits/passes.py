# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The Always On Pass — prepaid time, and the only exemption from the clock.

A pass is bought per instance and, while it is unexpired, that instance is exempt from **both**
the TTL auto-stop and the hourly burn. Those two go together on purpose: exempting an instance
from the clock but still charging it by the hour would sell the same time twice.

Every read here is one indexed query on `(bench_instance, valid_until)`. The set-returning form
exists so the enforcement sweep can ask about a whole fleet at once instead of once per instance;
`frappe.get_all` is deliberate over `get_list` — the sweep runs as the scheduler and metering runs
as the deploying user, and neither is asking a permission question.
"""

import frappe
from frappe.utils import today

PASS = "Always On Pass"


def active_pass_benches(bench_names) -> set[str]:
	"""Which of these instances hold an unexpired pass, in one query for the whole set."""
	names = list(bench_names or [])
	if not names:
		return set()
	return set(
		frappe.get_all(
			PASS,
			filters={"bench_instance": ("in", names), "valid_until": (">=", today())},
			pluck="bench_instance",
		)
	)


def has_active_pass(bench_name: str) -> bool:
	"""Whether this one instance is exempt right now."""
	return bool(active_pass_name(bench_name))


def active_pass_name(bench_name: str, exclude: str | None = None) -> str | None:
	"""The unexpired pass on this instance, or `None`. `exclude` skips the pass being saved."""
	if not bench_name:
		return None
	filters = {"bench_instance": bench_name, "valid_until": (">=", today())}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.db.get_value(PASS, filters, "name")
