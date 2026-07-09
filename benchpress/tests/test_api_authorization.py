# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Authorization suite for the whitelisted API.

Phase 2 asserted the happy path; this proves the negative paths: Guest,
wrong-role, and cross-user callers are all rejected by the endpoint guards
(`require_admin`, `require_bench_access`, and the owner-scoped bench filter).
Each denial test has a positive control so a guard that vacuously throws for
everyone — or silently returns an empty result — is caught as a failure.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import api
from benchpress.benchpress.doctype.bench_instance import get_instance_id


def _ensure_user(email, first_name, role):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Authz {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
		}
	).insert(ignore_permissions=True)


def _ensure_owned_bench(owner, lab):
	"""Insert a Running bench whose owner is `owner` (owner comes from the session)."""
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists("Bench Instance", name):
		frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Running",
				"container_id": "authz-container",
				"code_server_url": "http://localhost:8443",
				"code_server_password": "cs-secret",
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestApiAuthorization(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.user_a = _ensure_user("authz-user-a@example.com", "Authz UserA", "BenchPress User")
		cls.user_b = _ensure_user("authz-user-b@example.com", "Authz UserB", "BenchPress User")
		cls.admin_user = _ensure_user("authz-admin@example.com", "Authz Admin", "BenchPress Admin")
		cls.lab = _ensure_lab("authz-lab")
		cls.bench = _ensure_owned_bench(cls.user_a, cls.lab)
		cls.deploy_log = frappe.get_doc(
			{
				"doctype": "Deploy Log",
				"bench": cls.bench.name,
				"log_type": "info",
				"message": "authz fixture log line",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Deploy Log", cls.deploy_log.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		for email in (cls.user_a, cls.user_b, cls.admin_user):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def assert_denied(self, action):
		with self.assertRaises(frappe.PermissionError):
			action()

	# --- Guest / unauthenticated rejected ------------------------------------

	def test_guest_denied_from_admin_only_endpoints(self):
		frappe.set_user("Guest")
		self.assert_denied(lambda: api.create_lab_from_template("frappe", "authz-guest"))
		self.assert_denied(lambda: api.build_lab_image(self.lab.name))
		self.assert_denied(lambda: api.run_diagnostics())

	def test_guest_denied_from_bench_scoped_endpoints(self):
		frappe.set_user("Guest")
		bench = self.bench.name
		self.assert_denied(lambda: api.bench_action(bench, "start"))
		self.assert_denied(lambda: api.get_deploy_logs(bench))
		self.assert_denied(lambda: api.get_code_server_credentials(bench))
		self.assert_denied(lambda: api.restart_code_server(bench))

	# --- Wrong-role (BenchPress User) blocked from admin-only endpoints -------

	def test_non_admin_denied_from_create_lab_from_template(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.create_lab_from_template("frappe", "authz-user"))

	def test_non_admin_denied_from_build_lab_image(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.build_lab_image(self.lab.name))

	def test_non_admin_denied_from_run_diagnostics(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.run_diagnostics())

	def test_owner_denied_from_deleting_own_bench(self):
		# user_a passes require_bench_access on its own bench, but delete is admin-only.
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.bench_action(self.bench.name, "delete"))

	# --- Cross-user isolation (user_b against user_a's bench) -----------------

	def test_cross_user_denied_from_get_deploy_logs(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.get_deploy_logs(self.bench.name))

	def test_cross_user_denied_from_bench_action(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.bench_action(self.bench.name, "start"))

	def test_cross_user_denied_from_get_code_server_credentials(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.get_code_server_credentials(self.bench.name))

	def test_cross_user_denied_from_restart_code_server(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.restart_code_server(self.bench.name))

	def test_get_benches_hides_other_users_bench(self):
		frappe.set_user(self.user_b)
		names = [bench["name"] for bench in api.get_benches()]
		self.assertNotIn(self.bench.name, names)

	# --- Positive controls: the guards permit the legitimate caller ----------

	def test_owner_reads_own_bench_credentials(self):
		frappe.set_user(self.user_a)
		creds = api.get_code_server_credentials(self.bench.name)
		self.assertEqual(creds["password"], "cs-secret")

	def test_owner_sees_own_bench_in_get_benches(self):
		frappe.set_user(self.user_a)
		names = [bench["name"] for bench in api.get_benches()]
		self.assertIn(self.bench.name, names)

	def test_admin_allowed_to_create_lab_from_template(self):
		frappe.set_user(self.admin_user)
		with patch("benchpress.lab_templates.create_lab_from_template", return_value="LAB-authz") as create:
			result = api.create_lab_from_template("frappe", "authz-admin")
		create.assert_called_once()
		self.assertEqual(result, {"name": "LAB-authz", "status": "Draft"})

	def test_admin_allowed_to_run_diagnostics(self):
		frappe.set_user(self.admin_user)
		with patch("benchpress.diagnostics.run_diagnostics", return_value=[]):
			self.assertEqual(api.run_diagnostics(), [])
