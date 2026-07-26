# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Give `BenchPress Admin` the VPN access the desk workspace already assumes it has.

`vpn_management` grants its DocTypes to `System Manager` and `VPN Admin` only. A user holding
just `BenchPress Admin` therefore loses the workspace `Network` group, both VPN number cards
and onboarding step 2, because Frappe filters desk by DocType read permission. Mirroring
`VPN Admin`'s rows onto `BenchPress Admin` as Custom DocPerms keeps that fix inside this app
instead of editing another repository's DocType JSON.
"""

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import setup_custom_perms

SOURCE_ROLE = "VPN Admin"
TARGET_ROLE = "BenchPress Admin"
VPN_DOCTYPES = (
	"VPN Peer",
	"WireGuard Server",
	"Network Pool",
	"IP Allocation",
	"VPN Audit Log",
	"VPN Settings",
)


def grant_vpn_access() -> list[str]:
	"""Mirror `VPN Admin` onto `BenchPress Admin` for every VPN DocType.

	Idempotent: returns only the DocTypes that gained a permission row this run.
	"""
	granted = [doctype for doctype in VPN_DOCTYPES if _mirror_role(doctype)]
	if granted:
		frappe.clear_cache()
	return granted


def _mirror_role(doctype: str) -> bool:
	if not frappe.db.exists("DocType", doctype):
		return False

	setup_custom_perms(doctype)
	rows = _rows_to_copy(doctype)
	for row in rows:
		_copy_row(row)

	if rows:
		validate_permissions_for_doctype(doctype)
	return bool(rows)


def _rows_to_copy(doctype: str) -> list[frappe._dict]:
	"""Source rows with no target row at the same permission level."""
	held = {_level(row) for row in _permission_rows(doctype, TARGET_ROLE)}
	return [row for row in _permission_rows(doctype, SOURCE_ROLE) if _level(row) not in held]


def _permission_rows(doctype: str, role: str) -> list[frappe._dict]:
	return frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": role}, fields="*")


def _level(row: frappe._dict) -> tuple[int, int]:
	return (row.permlevel, row.if_owner)


def _copy_row(row: frappe._dict) -> None:
	target = frappe.new_doc("Custom DocPerm")
	target.update(row)
	target.name = None  # Custom DocPerm autonames by hash; reusing the source name collides.
	target.role = TARGET_ROLE
	target.insert(ignore_permissions=True)
