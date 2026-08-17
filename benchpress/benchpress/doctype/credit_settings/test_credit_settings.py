# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Defaults and cached reads are asserted in `benchpress/tests/test_credit_config.py`,
next to the accessor that is the only supported way to read them."""

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditSettings(IntegrationTestCase):
	pass
