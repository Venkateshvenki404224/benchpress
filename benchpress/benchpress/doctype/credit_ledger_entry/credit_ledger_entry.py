# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The audit trail behind every balance. Append-only, by construction.

`Credit Account.balance` is the materialised aggregate every screen reads; these rows exist so a
disputed balance can be explained, which only holds if a row can never be rewritten after the
fact. The guard lives on the document rather than in the writing module so a Desk edit and an API
call meet the same wall.

Nobody sums this table to display a balance — the statement page paginates it on the
`(account, creation)` index added by `benchpress.patches.index_credit_ledger`.
"""

import frappe
from frappe import _
from frappe.model.document import Document

IMMUTABLE = "A credit ledger entry cannot be changed once written. Post a correcting entry instead."


class CreditLedgerEntry(Document):
	def before_save(self):
		if not self.is_new():
			frappe.throw(_(IMMUTABLE), frappe.ValidationError)
