# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The Settings screen is admin-gated, so a `BenchPress Admin` must be able to save it.

`router.js` restricts `/settings` to admins, and `BenchPress Admin` is an admin
there without being a System Manager. If the DocPerm row for that role ever
loses `write`, the screen stays reachable and stops saving — a failure mode that
is invisible to anyone testing as Administrator, which is why it is asserted
here rather than left to manual checking.
"""

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

SETTINGS = "BenchPress Settings"
ADMIN_EMAIL = "settings-admin@example.com"


class IntegrationTestBenchPressSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", ADMIN_EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ADMIN_EMAIL,
					"first_name": "Settings Admin",
					"send_welcome_email": 0,
					"roles": [{"role": "BenchPress Admin"}],
				}
			).insert(ignore_permissions=True)
		# `base_domain` is `reqd`, so a site that never filled it in cannot save
		# the singleton at all — which would fail this suite for a reason that
		# has nothing to do with permissions.
		cls.original = {
			field: frappe.db.get_single_value(SETTINGS, field) for field in ("base_domain", "traefik_network")
		}
		if not cls.original["base_domain"]:
			frappe.db.set_single_value(SETTINGS, "base_domain", "settings-test.local")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for field, value in cls.original.items():
			frappe.db.set_single_value(SETTINGS, field, value)
		frappe.delete_doc("User", ADMIN_EMAIL, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_benchpress_admin_can_read_and_write_settings(self):
		frappe.set_user(ADMIN_EMAIL)
		self.assertNotIn(
			"System Manager", frappe.get_roles(), "the fixture user must not be a System Manager"
		)
		self.assertTrue(frappe.has_permission(SETTINGS, "read"))
		self.assertTrue(
			frappe.has_permission(SETTINGS, "write"),
			"BenchPress Admin can open /settings but not save it",
		)

	def test_benchpress_admin_save_survives_the_permission_check(self):
		frappe.set_user(ADMIN_EMAIL)
		settings = frappe.get_doc(SETTINGS)
		original = settings.traefik_network
		self.addCleanup(self._restore, original)

		settings.traefik_network = "settings-test-network"
		settings.save()

		self.assertEqual(frappe.db.get_single_value(SETTINGS, "traefik_network"), "settings-test-network")

	def test_a_user_without_an_admin_role_cannot_write_settings(self):
		frappe.set_user("Guest")
		self.assertFalse(frappe.has_permission(SETTINGS, "write"))

	def _restore(self, value):
		frappe.set_user("Administrator")
		settings = frappe.get_doc(SETTINGS)
		settings.traefik_network = value
		settings.save(ignore_permissions=True)
		frappe.db.commit()
