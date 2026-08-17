# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The exactly-one-default invariant is asserted in `benchpress/tests/test_credit_config.py`
alongside the accessor module that depends on it."""

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestInstanceSize(IntegrationTestCase):
	pass
