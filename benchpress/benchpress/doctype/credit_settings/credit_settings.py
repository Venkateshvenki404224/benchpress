# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from benchpress.credits.config import credits_enabled

NON_NEGATIVE_FIELDS = (
	"signup_grant_credits",
	"custom_build_credits",
	"low_balance_warn_percent",
	"reap_after_days",
	"max_concurrent_free",
	"max_concurrent_paid",
	"max_devices",
	"max_builds_per_day",
)


WEBSITE_SETTINGS = "Website Settings"


class CreditSettings(Document):
	def validate(self):
		"""0 means unlimited or disabled everywhere, so a negative is never meaningful."""
		for fieldname in NON_NEGATIVE_FIELDS:
			if (self.get(fieldname) or 0) < 0:
				frappe.throw(_("{0} cannot be negative.").format(_(self.meta.get_label(fieldname))))

	def on_update(self):
		self.follow_waitlist_switch()

	def follow_waitlist_switch(self) -> None:
		"""Point Frappe's own signup switch the same way `waitlist_open` points.

		This writes another Single, which is a side effect worth arguing for. `Website Settings.
		disable_signup` gates all three self-serve methods — the email form on `/login`, and, through
		`provider_allows_signup`, both OAuth providers. Left set, retiring the waitlist would put a
		"Start free" button in front of a signup page Frappe refuses to render, and the operator
		would have no reason to connect the two.

		So the decision stays in one field and the other one follows it. An operator who wants
		signup off leaves the waitlist open, which is what "invite-only" already means.

		With `enable_credits` off there is no hosted plan and no waitlist, so a self-hoster saving
		this doctype must not find their login page rewritten by it.
		"""
		if not credits_enabled():
			return
		frappe.db.set_single_value(WEBSITE_SETTINGS, "disable_signup", 1 if self.waitlist_open else 0)
		frappe.clear_cache(doctype=WEBSITE_SETTINGS)
