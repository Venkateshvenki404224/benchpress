# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Retire the `Bench Site` rows the removed create path could strand in `Creating`.

`api.create_site` inserted a row as `Creating` and handed the site build to a worker, so a worker
that died between the insert and the job left the row claiming a site was still on its way — and
nothing ever moved it again. That endpoint is gone, so no new row can reach this state, but the
rows it already made are on existing sites and would sit there forever.

`Creating` means "a job is working on this". No job is. A site nobody is building is Inactive —
the same state a stop leaves behind, and the state the Sites tab already refuses to open.
"""

import frappe


def execute():
	frappe.db.set_value("Bench Site", {"status": "Creating"}, "status", "Inactive", update_modified=False)
