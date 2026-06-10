# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.bench_instance import get_instance_id


def _make_lab(lab_id="test-lab-perms"):
	if frappe.db.exists("Lab", lab_id):
		return frappe.get_doc("Lab", lab_id)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": "Test Lab (Permissions)",
			"frappe_version": "version-15",
		}
	).insert(ignore_permissions=True)


def _make_bench(lab_name):
	existing = get_instance_id(frappe.session.user, lab_name)
	if frappe.db.exists("Bench Instance", existing):
		return frappe.get_doc("Bench Instance", existing)
	return frappe.get_doc(
		{
			"doctype": "Bench Instance",
			"lab": lab_name,
		}
	).insert(ignore_permissions=True)


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
		cls.lab = _make_lab()
		frappe.set_user(cls.regular_user)
		cls.user_bench = _make_bench(cls.lab.name).name
		frappe.set_user("Administrator")
		cls.admin_bench = _make_bench(cls.lab.name).name

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in [cls.user_bench, cls.admin_bench]:
			if frappe.db.exists("Bench Instance", name):
				frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
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

	def test_bench_list_shows_only_own_benches_for_regular_user(self):
		frappe.set_user(self.regular_user)
		names = frappe.get_list("Bench Instance", pluck="name", limit_page_length=0)
		self.assertIn(self.user_bench, names)
		self.assertNotIn(self.admin_bench, names)

	def test_bench_list_shows_all_benches_for_benchpress_admin(self):
		frappe.set_user(self.admin_user)
		names = frappe.get_list("Bench Instance", pluck="name", limit_page_length=0)
		self.assertIn(self.user_bench, names)
		self.assertIn(self.admin_bench, names)

	def test_bench_list_shows_all_benches_for_administrator(self):
		frappe.set_user("Administrator")
		names = frappe.get_list("Bench Instance", pluck="name", limit_page_length=0)
		self.assertIn(self.user_bench, names)
		self.assertIn(self.admin_bench, names)

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
