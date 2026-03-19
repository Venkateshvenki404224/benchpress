import frappe
from frappe.utils import get_system_timezone

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw("Please login to access the dashboard", frappe.AuthenticationError)
	csrf_token = frappe.sessions.get_csrf_token()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw("This method is only meant for developer mode")
	return get_boot()


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.version,
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"system_timezone": get_system_timezone(),
		}
	)
