# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Catalog behavior (ordering, `is_active` filtering, shape) is asserted in
`benchpress/tests/test_lab_templates.py`, next to the accessors that read it."""

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestLabTemplate(IntegrationTestCase):
	pass
