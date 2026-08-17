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


def require_app_user():
	frappe.only_for(APP_ROLES)


def require_bench_access(bench_name: str):
	frappe.has_permission("Bench Instance", "read", doc=bench_name, throw=True)


def get_bench_owner_filter() -> dict:
	if is_admin():
		return {}
	return {"owner": frappe.session.user}


def bench_instance_query_conditions(user):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return ""
	if not set(frappe.get_roles(user)).isdisjoint(ADMIN_ROLES):
		return ""
	return f"`tabBench Instance`.owner = {frappe.db.escape(user)}"


def credit_account_query_conditions(user):
	"""A balance is nobody else's business. The account's name *is* the user's email."""
	return _own_rows_only(user, "`tabCredit Account`.name")


def credit_ledger_query_conditions(user):
	"""Same rule one level down: the ledger's `account` is the account name, so the email."""
	return _own_rows_only(user, "`tabCredit Ledger Entry`.account")


def _own_rows_only(user, column: str) -> str:
	if not user:
		user = frappe.session.user
	if user == "Administrator" or not set(frappe.get_roles(user)).isdisjoint(ADMIN_ROLES):
		return ""
	return f"{column} = {frappe.db.escape(user)}"


def deploy_log_query_conditions(user):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return ""
	if not set(frappe.get_roles(user)).isdisjoint(ADMIN_ROLES):
		return ""
	return f"`tabDeploy Log`.bench IN (SELECT name FROM `tabBench Instance` WHERE owner = {frappe.db.escape(user)})"
