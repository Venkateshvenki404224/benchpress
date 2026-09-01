# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GitHubTrafficSnapshot(Document):
	def validate(self):
		if self.duplicate_name():
			frappe.throw(_("A snapshot for {0} on {1} already exists.").format(self.repository, self.snapshot_date))

	def duplicate_name(self) -> str | None:
		table = frappe.qb.DocType("GitHub Traffic Snapshot")
		rows = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.repository == self.repository)
			.where(table.snapshot_date == self.snapshot_date)
			.where(table.name != self.name)
			.limit(1)
		).run()
		return rows[0][0] if rows else None
