# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

ADMIN_ROLES = ("System Manager", "BenchPress Admin")
APP_ROLES = ("System Manager", "BenchPress Admin", "BenchPress User")


def has_app_permission() -> bool:
	return not set(frappe.get_roles()).isdisjoint(APP_ROLES)


def is_admin() -> bool:
	return not set(frappe.get_roles()).isdisjoint(ADMIN_ROLES)


def require_admin():
	frappe.only_for(ADMIN_ROLES)


def require_bench_access(bench_name: str):
	frappe.has_permission("Bench Instance", "read", doc=bench_name, throw=True)


def get_bench_owner_filter() -> dict:
	if is_admin():
		return {}
	return {"owner": frappe.session.user}


def deploy_log_query_conditions(user):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return ""
	if not set(frappe.get_roles(user)).isdisjoint(ADMIN_ROLES):
		return ""
	return f"`tabDeploy Log`.bench IN (SELECT name FROM `tabBench Instance` WHERE owner = {frappe.db.escape(user)})"
