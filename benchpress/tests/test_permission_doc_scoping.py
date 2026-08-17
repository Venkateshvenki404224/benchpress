# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Document-path permission scoping for the doctypes that hold one tenant's rows.

`permission_query_conditions` feeds the list engine only, so before the `has_permission` hooks
these doctypes are registered under, a single-document read saw the whole table. Every denial
here is paired with a positive control, so a rule that denies everybody cannot pass vacuously.

`frappe.client.get` is exercised in both forms. The `filters` form resolves the document before
checking permission, so it defeats hash autonaming — it is the form an attacker would use, and
the one a by-name test alone would miss.
"""

import json

import frappe
from frappe.client import get as client_get
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.bench_instance import get_instance_id


def _ensure_user(email: str, first_name: str, role: str | None = None) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"roles": [{"role": role}] if role else [],
			}
		).insert(ignore_permissions=True)
	return email


def _as(user: str, action):
	frappe.set_user(user)
	try:
		return action()
	finally:
		frappe.set_user("Administrator")


class TestPermissionDocScoping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.victim = _ensure_user("scope-victim@example.com", "Scope Victim", "BenchPress User")
		cls.attacker = _ensure_user("scope-attacker@example.com", "Scope Attacker", "BenchPress User")
		cls.admin_user = _ensure_user("scope-admin@example.com", "Scope Admin", "BenchPress Admin")
		cls.lab = cls._make_lab()
		cls.bench = cls._make_bench()
		cls.deploy_log = cls._make_log("Deploy Log", {"bench": cls.bench.name}, cls.victim)
		cls.build_log = cls._make_log("Build Log", {"lab": cls.lab.name}, cls.victim)
		cls.account = cls._make_credit_rows()
		frappe.db.commit()  # nosemgrep -- fixtures must outlive the per-test rollback

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("Credit Ledger Entry", {"account": cls.victim})
		frappe.db.delete("Credit Account", {"user": cls.victim})
		for doctype, name in (
			("Deploy Log", cls.deploy_log.name),
			("Build Log", cls.build_log.name),
			("Bench Instance", cls.bench.name),
			("Lab", cls.lab.name),
		):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		for email in (cls.victim, cls.attacker, cls.admin_user):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the fixtures were committed, so removing them must be too
		super().tearDownClass()

	# --- Fixtures -------------------------------------------------------------

	@classmethod
	def _make_lab(cls):
		if frappe.db.exists("Lab", "scope-lab"):
			frappe.delete_doc("Lab", "scope-lab", force=True, ignore_permissions=True)
		return frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": "scope-lab",
				"title": "Scope Lab",
				"frappe_version": "version-15",
				"image_tag": "benchpress/scope:latest",
			}
		).insert(ignore_permissions=True)

	@classmethod
	def _make_bench(cls):
		"""A bench the victim owns. The owner comes from the session, so it has to be set."""
		name = get_instance_id(cls.victim, cls.lab.name)
		if frappe.db.exists("Bench Instance", name):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		return _as(
			cls.victim,
			lambda: frappe.get_doc(
				{
					"doctype": "Bench Instance",
					"lab": cls.lab.name,
					"frappe_version": cls.lab.frappe_version,
					"status": "Running",
					"container_id": "scope-container",
				}
			).insert(ignore_permissions=True),
		)

	@classmethod
	def _make_log(cls, doctype: str, fields: dict, owner: str):
		return _as(
			owner,
			lambda: frappe.get_doc(
				{
					"doctype": doctype,
					"log_type": "info",
					"message": "scope fixture secret line",
					"timestamp": frappe.utils.now_datetime(),
					**fields,
				}
			).insert(ignore_permissions=True),
		)

	@classmethod
	def _make_credit_rows(cls):
		"""The victim's account and one ledger row, built by the module that owns them."""
		from benchpress.credits import account

		frappe.db.set_single_value("BenchPress Settings", "enable_credits", 1)
		frappe.clear_cache(doctype="BenchPress Settings")
		try:
			name = account.ensure_account(cls.victim)
			account.grant(cls.victim, 10, "Scope fixture grant")
			return name
		finally:
			frappe.db.set_single_value("BenchPress Settings", "enable_credits", 0)
			frappe.clear_cache(doctype="BenchPress Settings")

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	# --- Helpers --------------------------------------------------------------

	def assert_doc_denied(self, doctype: str, name: str, filters: dict):
		"""Both document paths refuse the attacker: by name, and by the filters form."""
		for read in (
			lambda: client_get(doctype, name),
			lambda: client_get(doctype, filters=json.dumps(filters)),
		):
			with self.assertRaises(frappe.PermissionError):
				_as(self.attacker, read)

	def assert_admins_still_read(self, doctype: str, name: str):
		for user in (self.admin_user, "Administrator"):
			try:
				_as(user, lambda: client_get(doctype, name))
			except frappe.PermissionError:
				self.fail(f"{user} was refused {doctype} {name}")

	# --- Deploy Log -----------------------------------------------------------

	def test_deploy_log_doc_read_is_denied_across_tenants(self):
		self.assert_doc_denied("Deploy Log", self.deploy_log.name, {"bench": self.bench.name})

	def test_deploy_log_doc_read_is_denied_for_a_computed_bench_name(self):
		"""The real attack path: the bench name is derived, not guessed."""
		target = get_instance_id(self.victim, self.lab.name)
		self.assertEqual(target, self.bench.name)
		with self.assertRaises(frappe.PermissionError):
			_as(self.attacker, lambda: client_get("Deploy Log", filters=json.dumps({"bench": target})))

	def test_deploy_log_owner_still_reads_their_own(self):
		doc = _as(self.victim, lambda: client_get("Deploy Log", self.deploy_log.name))
		self.assertIn("scope fixture secret line", doc["message"])

	def test_deploy_log_admins_still_read_any(self):
		self.assert_admins_still_read("Deploy Log", self.deploy_log.name)

	def test_deploy_log_list_stays_scoped(self):
		rows = _as(self.attacker, lambda: frappe.get_list("Deploy Log", filters={"bench": self.bench.name}))
		self.assertEqual(rows, [])

	# --- Build Log ------------------------------------------------------------

	def test_build_log_doc_read_is_denied_across_tenants(self):
		self.assert_doc_denied("Build Log", self.build_log.name, {"lab": self.lab.name})

	def test_build_log_owner_still_reads_their_own(self):
		doc = _as(self.victim, lambda: client_get("Build Log", self.build_log.name))
		self.assertIn("scope fixture secret line", doc["message"])

	def test_build_log_admins_still_read_any(self):
		self.assert_admins_still_read("Build Log", self.build_log.name)

	def test_build_log_list_is_now_scoped(self):
		"""The assertion that proves the missing query condition was the gap.

		`Build Log` had no `permission_query_conditions` entry, so this returned the victim's rows.
		"""
		rows = _as(self.attacker, lambda: frappe.get_list("Build Log", filters={"lab": self.lab.name}))
		self.assertEqual(rows, [])

	def test_build_log_owner_still_lists_their_own(self):
		rows = _as(self.victim, lambda: frappe.get_list("Build Log", filters={"lab": self.lab.name}))
		self.assertEqual([row.name for row in rows], [self.build_log.name])

	# --- Credit doctypes ------------------------------------------------------

	def test_credit_account_doc_read_is_denied_across_tenants(self):
		self.assert_doc_denied("Credit Account", self.account, {"user": self.victim})

	def test_credit_ledger_doc_read_is_denied_across_tenants(self):
		entry = frappe.get_all("Credit Ledger Entry", filters={"account": self.victim}, pluck="name")[0]
		self.assert_doc_denied("Credit Ledger Entry", entry, {"account": self.victim})

	def test_credit_account_admins_still_read_any(self):
		self.assert_admins_still_read("Credit Account", self.account)

	def test_credit_summary_still_serves_the_holder(self):
		"""The endpoint the SPA actually reads balances through, which is why the grant could go."""
		from benchpress.credits import account

		summary = _as(self.victim, lambda: account.summary(self.victim))
		self.assertFalse(summary["enabled"])

	# --- The failure banner survives the Build Log rule -----------------------

	def test_lab_failure_summary_survives_for_a_non_owner(self):
		"""A non-admin keeps the derived failure, and never the raw build output.

		`_read_failure` reads past the row scoping on purpose: labs are global recipes, so the
		build that failed is usually somebody else's.
		"""
		from benchpress import lab_detail

		frappe.db.set_value("Lab", self.lab.name, "status", "Error")
		frappe.db.set_value("Build Log", self.build_log.name, "log_type", "error")
		self.addCleanup(frappe.db.set_value, "Lab", self.lab.name, "status", "Draft")

		payload = _as(self.attacker, lambda: lab_detail.get_lab(self.lab.name))

		self.assertIsNotNone(payload["failure"])
		self.assertEqual(payload["failure"]["source"], "build")
		self.assertNotIn("message", payload["failure"])
