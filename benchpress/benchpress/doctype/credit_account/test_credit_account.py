# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The accounting lives in `benchpress.credits.account` and is asserted in
`benchpress/tests/test_credits.py`. What belongs here is the one thing the document itself
decides: who may move a balance by hand."""

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditAccount(IntegrationTestCase):
	def test_only_an_admin_may_post_an_adjustment(self):
		# Guest, because no other test opens an account for it: a user who already has one
		# would raise a duplicate-key error and pass this test vacuously.
		account = frappe.new_doc("Credit Account")
		account.update({"user": "Guest"})
		account.insert(ignore_permissions=True)

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, account.post_adjustment, 5, "a reason")
