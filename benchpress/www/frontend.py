# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from benchpress.boot import get_bootinfo
from benchpress.permissions import has_app_permission

no_cache = 1


def get_context():
	if not has_app_permission():
		frappe.throw(_("You do not have permission to access BenchPress"), frappe.PermissionError)

	frappe.db.commit()  # nosemgrep -- GET-rendered pages are rolled back; persist the csrf_token generated above (matches CRM/Gameplan)
	context = frappe._dict()
	context.boot = get_boot()
	return context


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"socketio_port": frappe.conf.get("socketio_port"),
			"benchpress": get_bootinfo(),
		}
	)
