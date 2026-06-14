# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Catalog of ready-made lab templates.

Templates are versioned in code so an admin can spin up a common stack
(Frappe, ERPNext, CRM) without typing every app's git URL and resources by
hand. ``create_lab_from_template`` materialises a template into an ordinary,
editable Lab document, after which the normal build/deploy flow takes over.
"""

import frappe
from frappe import _

# Bumped whenever the template set or its fields change so an install can tell
# which catalog a lab was created against.
CATALOG_VERSION = 2

LAB_TEMPLATES = [
	{
		"key": "frappe",
		"title": "Frappe Framework",
		"description": "Bare Frappe bench with no extra apps — the lightest starting point.",
		"frappe_version": "version-15",
		"memory_limit": "512m",
		"cpu_cores": 1,
		"apps": [],
	},
	{
		"key": "erpnext",
		"title": "ERPNext",
		"description": "Full ERP suite: accounting, inventory, manufacturing and more.",
		"frappe_version": "version-15",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-15",
			}
		],
	},
	{
		"key": "crm",
		"title": "Frappe CRM",
		"description": "Lightweight sales CRM on Frappe — leads, deals and contacts.",
		"frappe_version": "version-15",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"apps": [
			{
				"app_name": "crm",
				"app_label": "Frappe CRM",
				"git_url": "https://github.com/frappe/crm",
				"branch": "main",
			}
		],
	},
	{
		"key": "hrms",
		"title": "Frappe HR",
		"description": "HR & payroll suite — employees, leaves, attendance and payroll.",
		"frappe_version": "version-15",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"apps": [
			{
				"app_name": "hrms",
				"app_label": "Frappe HR",
				"git_url": "https://github.com/frappe/hrms",
				"branch": "version-15",
			}
		],
	},
	{
		"key": "lms",
		"title": "Frappe Learning",
		"description": "Learning management system — courses, quizzes and batches.",
		"frappe_version": "version-15",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"apps": [
			{
				"app_name": "lms",
				"app_label": "Frappe Learning",
				"git_url": "https://github.com/frappe/lms",
				"branch": "main",
			}
		],
	},
	{
		"key": "helpdesk",
		"title": "Frappe Helpdesk",
		"description": "Customer support desk — tickets, SLAs and a knowledge base.",
		"frappe_version": "version-15",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"apps": [
			{
				"app_name": "helpdesk",
				"app_label": "Frappe Helpdesk",
				"git_url": "https://github.com/frappe/helpdesk",
				"branch": "main",
			}
		],
	},
]


def get_templates() -> list[dict]:
	"""Return the full catalog of lab templates."""
	return LAB_TEMPLATES


def get_template(key: str) -> dict:
	"""Return a single template by key, or throw if it is unknown."""
	for template in LAB_TEMPLATES:
		if template["key"] == key:
			return template
	frappe.throw(_("Unknown lab template '{0}'.").format(key or ""))


def create_lab_from_template(template_key: str, lab_id: str, title: str | None = None) -> str:
	"""Build a Lab document from a template and return its name."""
	template = get_template(template_key)
	lab = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": title or template["title"],
			"description": template["description"],
			"frappe_version": template["frappe_version"],
			"memory_limit": template["memory_limit"],
			"cpu_cores": template["cpu_cores"],
			"apps": [dict(app) for app in template["apps"]],
		}
	)
	lab.insert()
	return lab.name
