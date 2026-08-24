# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Name the runtime every existing bench already runs, then make sysbox the default for new ones.

The stamp has to land before the seed. A container's runtime is fixed when it is created, so a
row filled in by the new default would claim an isolation its container was never built with,
and every reader downstream would believe it. Rows that already name a runtime are left alone:
a bench deployed on sysbox is telling the truth and must not be relabelled either way.
"""

import frappe

SETTINGS = "BenchPress Settings"
FIELD = "default_bench_runtime"


def execute():
	for name in frappe.get_all("Bench Instance", filters={"runtime": ("in", ["", None])}, pluck="name"):
		frappe.db.set_value("Bench Instance", name, "runtime", "runc", update_modified=False)

	if FIELD not in frappe.db.get_singles_dict(SETTINGS):
		frappe.db.set_single_value(SETTINGS, FIELD, "sysbox")
