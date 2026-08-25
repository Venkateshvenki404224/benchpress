"""Bring an existing site onto the lease model: the duration catalog, the price lever, the index.

`price_multiplier` is backfilled rather than left to the DocType default, which only applies to
rows inserted after the field exists. A size reading `0.0` would price every lease at nothing.
"""

import frappe

from benchpress.credits.seed import seed_defaults
from benchpress.indexes import ensure_lease_sweep_index


def execute():
	seed_defaults()
	for name in frappe.get_all("Instance Size", filters={"price_multiplier": 0}, pluck="name"):
		frappe.db.set_value("Instance Size", name, "price_multiplier", 1.0)
	ensure_lease_sweep_index()
