# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

ADMIN_ROLES = {"System Manager", "BenchPress Admin"}
APP_ROLES = {"System Manager", "BenchPress Admin", "BenchPress User"}


def has_app_permission() -> bool:
	"""Check if the current user has any BenchPress role (admin or user)."""
	return bool(APP_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def is_admin() -> bool:
	"""Check if the current user has an admin-level role."""
	return bool(ADMIN_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def require_admin():
	"""Throw PermissionError if the current user is not an admin."""
	if not is_admin():
		frappe.throw(_("You do not have permission to perform this action."), frappe.PermissionError)


def require_bench_access(bench_name: str):
	"""Throw PermissionError if the user is not admin and not the bench owner."""
	if is_admin():
		return
	owner = frappe.db.get_value("Bench Instance", bench_name, "owner")
	if not owner:
		frappe.throw(_("Bench Instance {0} not found.").format(bench_name), frappe.DoesNotExistError)
	if owner != frappe.session.user:
		frappe.throw(_("You do not have permission to access this bench."), frappe.PermissionError)


def get_bench_owner_filter() -> dict:
	"""Return an owner filter dict for non-admin users, empty dict for admins."""
	if is_admin():
		return {}
	return {"owner": frappe.session.user}


def bench_instance_query_conditions(user):
	"""Permission query condition for Bench Instance — scopes to owner for non-admin users."""
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return ""
	if ADMIN_ROLES.intersection(set(frappe.get_roles(user))):
		return ""
	return f"`tabBench Instance`.owner = {frappe.db.escape(user)}"
