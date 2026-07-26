# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.vpn_access import SOURCE_ROLE, TARGET_ROLE, VPN_DOCTYPES, grant_vpn_access

RIGHTS = ("read", "write", "create", "delete", "share", "print", "email", "report", "export")
VPN_ADMIN_USER = "vpn-access-admin@example.com"


def _rights(doctype: str, role: str) -> set:
	"""Every right the role holds on the DocType, keyed by permission level."""
	return {
		(perm.permlevel, perm.if_owner, right)
		for perm in frappe.get_meta(doctype).permissions
		if perm.role == role
		for right in RIGHTS
		if perm.get(right)
	}


class TestVPNAccess(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		grant_vpn_access()
		if not frappe.db.exists("User", VPN_ADMIN_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": VPN_ADMIN_USER,
					"first_name": "VPN Access",
					"last_name": "Admin",
					"send_welcome_email": 0,
					"roles": [{"role": TARGET_ROLE}],
				}
			).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		if frappe.db.exists("User", VPN_ADMIN_USER):
			frappe.delete_doc("User", VPN_ADMIN_USER, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_benchpress_admin_matches_vpn_admin(self):
		for doctype in VPN_DOCTYPES:
			with self.subTest(doctype=doctype):
				self.assertEqual(_rights(doctype, TARGET_ROLE), _rights(doctype, SOURCE_ROLE))

	def test_vpn_admin_keeps_its_own_rights(self):
		"""Custom DocPerms shadow the standard rows, so the copied roles must survive."""
		for doctype in VPN_DOCTYPES:
			with self.subTest(doctype=doctype):
				self.assertIn((0, 0, "read"), _rights(doctype, SOURCE_ROLE))
				self.assertIn((0, 0, "read"), _rights(doctype, "System Manager"))

	def test_grant_is_idempotent(self):
		before = frappe.db.count("Custom DocPerm", {"role": TARGET_ROLE})

		self.assertEqual(grant_vpn_access(), [])
		self.assertEqual(frappe.db.count("Custom DocPerm", {"role": TARGET_ROLE}), before)

	def test_benchpress_admin_user_can_reach_the_vpn_doctypes(self):
		"""Read everywhere; write wherever VPN Admin writes (VPN Audit Log stays read-only)."""
		frappe.set_user(VPN_ADMIN_USER)

		for doctype in VPN_DOCTYPES:
			with self.subTest(doctype=doctype):
				self.assertTrue(frappe.has_permission(doctype, "read", user=VPN_ADMIN_USER))
				writable = (0, 0, "write") in _rights(doctype, SOURCE_ROLE)
				self.assertEqual(frappe.has_permission(doctype, "write", user=VPN_ADMIN_USER), writable)

	def test_workspace_network_links_resolve_for_benchpress_admin(self):
		"""The Network group renders only when every DocType it links is readable."""
		workspace = frappe.get_doc("Workspace", "BenchPress")
		network_doctypes = {
			link.link_to
			for link in workspace.links
			if link.link_type == "DocType" and link.link_to in VPN_DOCTYPES
		}

		self.assertTrue(network_doctypes, "workspace links no VPN DocType")
		for doctype in network_doctypes:
			with self.subTest(doctype=doctype):
				self.assertTrue(frappe.has_permission(doctype, "read", user=VPN_ADMIN_USER))
