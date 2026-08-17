# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Pack ordering and `is_active` filtering are asserted in
`benchpress/tests/test_credit_config.py`, next to the accessor that reads them."""

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditPack(IntegrationTestCase):
	pass
