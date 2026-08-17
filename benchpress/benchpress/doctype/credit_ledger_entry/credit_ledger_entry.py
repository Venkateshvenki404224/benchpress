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
BY_HAND = (
	"Post credits from the Credit Account form. A ledger row written here would not move the "
	"balance, and a statement that disagrees with the balance is worse than no statement."
)
NEEDS_REASON = "An {0} entry needs a reason in its description."


class CreditLedgerEntry(Document):
	def before_insert(self):
		"""Only the accounting module may open a row.

		`Credit Account.balance` is the settled figure every screen reads; these rows explain it.
		A row inserted beside the module that maintains the balance explains nothing — it invents a
		second, contradictory answer — so the Desk form sends an operator to the account instead.
		"""
		if not self.flags.from_engine:
			frappe.throw(_(BY_HAND), frappe.ValidationError)

	def validate(self):
		if self.entry_type in ("Adjustment", "Refund") and not (self.description or "").strip():
			frappe.throw(_(NEEDS_REASON).format(self.entry_type.lower()), frappe.ValidationError)

	def before_save(self):
		if not self.is_new():
			frappe.throw(_(IMMUTABLE), frappe.ValidationError)
