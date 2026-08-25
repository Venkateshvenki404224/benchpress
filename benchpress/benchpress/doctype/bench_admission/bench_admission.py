# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per bench that currently holds a concurrency slot. Its existence is the slot.

Nothing writes this by hand. `benchpress.credits.admission` inserts it under the caller's
`Credit Account` row lock and deletes it on every path a bench leaves `Deploying` or `Running`;
`benchpress.credits.admission_repair` heals whatever a killed worker left behind.
"""

from frappe.model.document import Document


class BenchAdmission(Document):
	pass
