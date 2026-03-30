# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestPermissions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# Create a regular BenchPress User
		if not frappe.db.exists("User", "perm-user@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "perm-user@example.com",
					"first_name": "Perm",
					"last_name": "User",
					"send_welcome_email": 0,
					"roles": [{"role": "BenchPress User"}],
				}
			).insert(ignore_permissions=True)
		# Create a BenchPress Admin user
		if not frappe.db.exists("User", "perm-admin@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "perm-admin@example.com",
					"first_name": "Perm",
					"last_name": "Admin",
					"send_welcome_email": 0,
					"roles": [{"role": "BenchPress Admin"}],
				}
			).insert(ignore_permissions=True)
		cls.regular_user = "perm-user@example.com"
		cls.admin_user = "perm-admin@example.com"

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in [cls.regular_user, cls.admin_user]:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def test_is_admin_true_for_system_manager(self):
		from benchpress.permissions import is_admin

		frappe.set_user("Administrator")
		self.assertTrue(is_admin())

	def test_is_admin_true_for_benchpress_admin(self):
		from benchpress.permissions import is_admin

		frappe.set_user(self.admin_user)
		self.assertTrue(is_admin())

	def test_is_admin_false_for_benchpress_user(self):
		from benchpress.permissions import is_admin

		frappe.set_user(self.regular_user)
		self.assertFalse(is_admin())

	def test_has_app_permission_true_for_benchpress_user(self):
		from benchpress.permissions import has_app_permission

		frappe.set_user(self.regular_user)
		self.assertTrue(has_app_permission())

	def test_has_app_permission_true_for_benchpress_admin(self):
		from benchpress.permissions import has_app_permission

		frappe.set_user(self.admin_user)
		self.assertTrue(has_app_permission())

	def test_has_app_permission_false_for_guest(self):
		from benchpress.permissions import has_app_permission

		frappe.set_user("Guest")
		self.assertFalse(has_app_permission())

	def test_get_bench_owner_filter_empty_dict_for_administrator(self):
		from benchpress.permissions import get_bench_owner_filter

		frappe.set_user("Administrator")
		result = get_bench_owner_filter()
		self.assertEqual(result, {})

	def test_get_bench_owner_filter_empty_dict_for_benchpress_admin(self):
		from benchpress.permissions import get_bench_owner_filter

		frappe.set_user(self.admin_user)
		result = get_bench_owner_filter()
		self.assertEqual(result, {})

	def test_get_bench_owner_filter_has_owner_clause_for_regular_user(self):
		from benchpress.permissions import get_bench_owner_filter

		frappe.set_user(self.regular_user)
		result = get_bench_owner_filter()
		self.assertEqual(result, {"owner": self.regular_user})

	def test_bench_instance_query_conditions_empty_for_administrator(self):
		from benchpress.permissions import bench_instance_query_conditions

		result = bench_instance_query_conditions("Administrator")
		self.assertEqual(result, "")

	def test_bench_instance_query_conditions_empty_for_benchpress_admin(self):
		from benchpress.permissions import bench_instance_query_conditions

		result = bench_instance_query_conditions(self.admin_user)
		self.assertEqual(result, "")

	def test_bench_instance_query_conditions_has_owner_clause_for_user(self):
		from benchpress.permissions import bench_instance_query_conditions

		result = bench_instance_query_conditions(self.regular_user)
		self.assertIn("owner", result)
		self.assertIn("tabBench Instance", result)

	def test_deploy_log_query_conditions_empty_for_administrator(self):
		from benchpress.permissions import deploy_log_query_conditions

		result = deploy_log_query_conditions("Administrator")
		self.assertEqual(result, "")

	def test_deploy_log_query_conditions_has_subquery_for_regular_user(self):
		from benchpress.permissions import deploy_log_query_conditions

		result = deploy_log_query_conditions(self.regular_user)
		self.assertIn("tabDeploy Log", result)
		self.assertIn("tabBench Instance", result)
		self.assertIn("owner", result)

	def test_require_admin_succeeds_for_administrator(self):
		from benchpress.permissions import require_admin

		frappe.set_user("Administrator")
		try:
			require_admin()
		except frappe.PermissionError:
			self.fail("require_admin raised PermissionError for Administrator")

	def test_require_admin_throws_for_benchpress_user(self):
		from benchpress.permissions import require_admin

		frappe.set_user(self.regular_user)
		with self.assertRaises(frappe.PermissionError):
			require_admin()
