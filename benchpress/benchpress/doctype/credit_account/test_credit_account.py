# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The accounting behaviour is asserted in `benchpress/tests/test_credits.py`, next to the
module that owns it. Only the hand-edit guards belong here."""

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditAccount(IntegrationTestCase):
	def test_a_negative_burn_rate_is_rejected(self):
		# Guest, because no metering test ever opens an account for it: a user who already
		# has one would raise a duplicate-key error and pass this test vacuously.
		account = frappe.new_doc("Credit Account")
		account.update({"user": "Guest", "burn_rate": -1})
		self.assertRaises(frappe.ValidationError, account.insert)
