# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

NON_NEGATIVE_FIELDS = (
	"signup_grant_credits",
	"custom_build_credits",
	"low_balance_warn_percent",
	"max_run_hours",
	"reap_after_days",
	"max_concurrent_free",
	"max_concurrent_paid",
	"max_devices",
	"max_builds_per_day",
	"always_on_monthly_inr",
)


class CreditSettings(Document):
	def validate(self):
		"""0 means unlimited or disabled everywhere, so a negative is never meaningful."""
		for fieldname in NON_NEGATIVE_FIELDS:
			if (self.get(fieldname) or 0) < 0:
				frappe.throw(_("{0} cannot be negative.").format(_(self.meta.get_label(fieldname))))
