# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe

from benchpress.permissions import is_admin


def get_bootinfo() -> dict:
	return {
		"is_admin": is_admin(),
		"user": frappe.session.user,
		"roles": frappe.get_roles(frappe.session.user),
	}


def extend_bootinfo(bootinfo):
	bootinfo.benchpress = get_bootinfo()
