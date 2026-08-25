# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Every doctype that grants a non-admin `read` declares how it is scoped.

Four doctypes made the same mistake independently — two of them in one PR — because nothing
recorded which doctypes hold per-tenant rows and what that obliges an author to do. The bug is
cheap to make and expensive to notice: a `permission_query_conditions` entry scopes the list
path, the list path is what gets tested by hand, and the document path leaks the whole table.

This is a metadata test. It reads the app's DocType JSONs and the hooks Frappe actually
registered — not `hooks.py` as text, because an unregistered hook is indistinguishable from a
permissive one: `has_controller_permissions` returns True when it finds none.
"""

import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.permissions import ADMIN_ROLES

# Rows belong to one tenant. Both paths must be scoped: a list rule AND a document rule.
TENANT_SCOPED = {
	"Bench Instance",  # the deployment itself
	"Bench Site",  # a site on somebody's deployment
	"Credit Account",  # a balance
	"Credit Ledger Entry",  # what that balance is made of
	"Deploy Log",  # one deployment's output
	"Build Log",  # one image build's output, which is credential-adjacent
}

# Shared catalogues. Every app user may read every row, and no user can create one.
GLOBAL_BY_DESIGN = {
	"Lab": "admin-authored recipes; BenchPress User has no create",
	"Lab Template": "the ready-made catalog; BenchPress User has no create",
	"Credit Pack": "the price list",
	"Lease Plan": "the duration catalog",
	"Instance Size": "the size list",
	"Always On Pass": "read through owner-scoped endpoints; rows name their own bench",
}


def _doctype_files() -> list[Path]:
	root = Path(frappe.get_app_path("benchpress"))
	return sorted(root.glob("**/doctype/*/*.json"))


def _load_doctypes() -> dict[str, dict]:
	doctypes = {}
	for path in _doctype_files():
		if path.stem != path.parent.name:
			continue
		definition = json.loads(path.read_text())
		if definition.get("doctype") != "DocType":
			continue
		doctypes[definition.get("name") or path.stem] = definition
	return doctypes


def _non_admin_read_roles(definition: dict) -> list[str]:
	return [
		perm["role"]
		for perm in definition.get("permissions", [])
		if perm.get("read") and perm.get("role") not in ADMIN_ROLES
	]


def _grants_read_if_owner(definition: dict) -> bool:
	return any(
		perm.get("read") and perm.get("if_owner") and perm.get("role") not in ADMIN_ROLES
		for perm in definition.get("permissions", [])
	)


class TestDoctypeScoping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.doctypes = _load_doctypes()
		cls.query_rules = frappe.get_hooks("permission_query_conditions") or {}
		cls.doc_rules = frappe.get_hooks("has_permission") or {}

	def test_the_app_actually_has_doctypes_to_check(self):
		"""Guards against a glob that matches nothing and passes everything."""
		self.assertGreater(len(self.doctypes), 10)

	def test_every_non_admin_readable_doctype_declares_its_scoping(self):
		undeclared = [
			name
			for name, definition in self.doctypes.items()
			if _non_admin_read_roles(definition)
			and name not in TENANT_SCOPED
			and name not in GLOBAL_BY_DESIGN
		]
		self.assertEqual(
			undeclared,
			[],
			f"{undeclared} grant a non-admin read without saying how they are scoped. Add each to "
			"TENANT_SCOPED (and give it a list rule and a document rule) or to GLOBAL_BY_DESIGN "
			"with a justification.",
		)

	def test_the_two_sets_do_not_overlap(self):
		self.assertEqual(TENANT_SCOPED & set(GLOBAL_BY_DESIGN), set())

	def test_every_tenant_scoped_doctype_has_a_document_rule(self):
		"""The half that was missing. A query condition never reaches a single-doc read."""
		for name in sorted(TENANT_SCOPED):
			definition = self.doctypes.get(name)
			if not definition or not _non_admin_read_roles(definition):
				continue
			has_rule = name in self.doc_rules or _grants_read_if_owner(definition)
			self.assertTrue(
				has_rule,
				f"{name} grants a non-admin read with no document rule: register a `has_permission` "
				"hook for it, or grant its read `if_owner`.",
			)

	def test_every_tenant_scoped_doctype_has_a_list_rule(self):
		for name in sorted(TENANT_SCOPED):
			definition = self.doctypes.get(name)
			if not definition or not _non_admin_read_roles(definition):
				continue
			has_rule = name in self.query_rules or _grants_read_if_owner(definition)
			self.assertTrue(
				has_rule,
				f"{name} grants a non-admin read with no list rule: register a "
				"`permission_query_conditions` hook for it, or grant its read `if_owner`.",
			)

	def test_every_registered_rule_resolves(self):
		"""A rename in `permissions.py` that forgets `hooks.py` silently disables the rule."""
		for registry in (self.query_rules, self.doc_rules):
			for doctype, paths in registry.items():
				for path in frappe.utils.data.cstr(paths).split(",") if isinstance(paths, str) else paths:
					try:
						self.assertTrue(callable(frappe.get_attr(path)), f"{doctype}: {path} is not callable")
					except (ImportError, AttributeError) as error:
						self.fail(f"{doctype}: {path} does not resolve ({error})")

	def test_the_credit_doctypes_no_longer_grant_a_blanket_read(self):
		"""Least privilege on top of the hook, since `Custom DocPerm` can shadow the JSON."""
		for name in ("Credit Account", "Credit Ledger Entry"):
			self.assertEqual(_non_admin_read_roles(self.doctypes[name]), [], name)
