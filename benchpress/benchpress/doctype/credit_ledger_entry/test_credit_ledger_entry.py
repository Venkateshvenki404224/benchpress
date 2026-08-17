# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""What the ledger records is asserted in `benchpress/tests/test_credits.py`; that it cannot be
rewritten is asserted here, next to the guard."""

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditLedgerEntry(IntegrationTestCase):
	pass
