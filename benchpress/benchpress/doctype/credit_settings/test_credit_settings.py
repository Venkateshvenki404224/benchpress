# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Defaults and cached reads are asserted in `benchpress/tests/test_credit_config.py`,
next to the accessor that is the only supported way to read them."""

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.credit_settings.credit_settings import get_non_negative_fields

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestCreditSettings(IntegrationTestCase):
	def test_schema_derivation_covers_every_int_float_field(self):
		"""get_non_negative_fields() must track the real schema, not a frozen snapshot.

		#406 and #407 were both "the hand-maintained tuple silently fell behind the
		doctype's real Int/Float field list" -- the same bug shape twice. Asserting
		against frappe.get_meta() directly (not a copy of today's field names) means
		a *future* field added to credit_settings.json without an explicit exemption
		fails this test too, instead of just not throwing in validate().
		"""
		meta = frappe.get_meta("Credit Settings")
		schema_int_float_fields = {
			field.fieldname for field in meta.fields if field.fieldtype in ("Int", "Float")
		}
		self.assertEqual(set(get_non_negative_fields()), schema_int_float_fields)

	def test_validate_rejects_negative_on_every_derived_field(self):
		"""Every field the guard claims to cover must actually throw on a negative save.

		Exercises the fix end-to-end (not just the derivation list) so a future
		exemption added to NEGATIVE_MEANINGFUL_FIELDS without updating this test
		would still be caught if validate() stopped reading that list correctly.
		"""
		settings = frappe.get_single("Credit Settings")
		for fieldname in get_non_negative_fields():
			settings.set(fieldname, -1)
			with self.assertRaises(frappe.ValidationError, msg=f"{fieldname} did not reject -1"):
				settings.validate()
			settings.reload()
