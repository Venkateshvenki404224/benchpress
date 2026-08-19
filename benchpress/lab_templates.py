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
CATALOG_VERSION = 6

# Each template names its `Instance Size`. `memory_limit` / `cpu_cores` below must agree
# with it: they are what the card renders, and `Lab.apply_instance_size` overwrites them.

# "Use template" names the lab itself, so a taken id is retried with a numeric
# suffix. The ceiling only exists so a pathological catalog cannot spin.
MAX_LAB_ID_ATTEMPTS = 50

LAB_TEMPLATES = [
	{
		"key": "frappe",
		"eta_minutes": 3,
		"most_used": False,
		"title": "Frappe Framework",
		"description": "Bare Frappe bench with no extra apps — the lightest starting point.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"apps": [],
	},
	{
		"key": "erpnext",
		"eta_minutes": 6,
		"most_used": True,
		"title": "ERPNext",
		"description": "Full ERP suite: accounting, inventory, manufacturing and more.",
		"frappe_version": "version-15",
		"instance_size": "Medium",
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
		"eta_minutes": 4,
		"most_used": False,
		"title": "Frappe CRM",
		"description": "Lightweight sales CRM on Frappe — leads, deals and contacts.",
		"frappe_version": "version-15",
		"instance_size": "Small",
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
		"eta_minutes": 5,
		"most_used": False,
		"title": "Frappe HR",
		"description": "HR & payroll suite — employees, leaves, attendance and payroll.",
		"frappe_version": "version-15",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		# hrms requires erpnext, so erpnext must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-15",
			},
			{
				"app_name": "hrms",
				"app_label": "Frappe HR",
				"git_url": "https://github.com/frappe/hrms",
				"branch": "version-15",
			},
		],
	},
	{
		"key": "lms",
		"eta_minutes": 4,
		"most_used": False,
		"title": "Frappe Learning",
		"description": "Learning management system — courses, quizzes and batches.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		# lms requires payments, so payments must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "payments",
				"app_label": "Payments",
				"git_url": "https://github.com/frappe/payments",
				"branch": "version-15",
			},
			{
				"app_name": "lms",
				"app_label": "Frappe Learning",
				"git_url": "https://github.com/frappe/lms",
				"branch": "main",
			},
		],
	},
	{
		"key": "helpdesk",
		"eta_minutes": 4,
		"most_used": False,
		"title": "Frappe Helpdesk",
		"description": "Customer support desk — tickets, SLAs and a knowledge base.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		# helpdesk requires telephony, so telephony must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "telephony",
				"app_label": "Telephony",
				"git_url": "https://github.com/frappe/telephony",
				"branch": "develop",
			},
			{
				"app_name": "helpdesk",
				"app_label": "Frappe Helpdesk",
				"git_url": "https://github.com/frappe/helpdesk",
				"branch": "main",
			},
		],
	},
	{
		"key": "india-compliance",
		"eta_minutes": 7,
		"most_used": False,
		"title": "ERPNext + India Compliance",
		"description": "ERPNext with GST, e-invoicing and TDS for Indian businesses.",
		"frappe_version": "version-15",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		# india_compliance extends ERPNext, so ERPNext must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-15",
			},
			{
				"app_name": "india_compliance",
				"app_label": "India Compliance",
				"git_url": "https://github.com/resilient-tech/india-compliance",
				"branch": "version-15",
			},
		],
	},
]


def get_templates() -> list[dict]:
	"""Return the full catalog of lab templates."""
	return LAB_TEMPLATES


def get_catalog() -> list[dict]:
	"""The catalog as the Templates page reads it: each template and the lab it built."""
	built = _labs_by_template()
	return [{**template, "lab": built.get(template["key"])} for template in LAB_TEMPLATES]


def _labs_by_template() -> dict[str, dict]:
	"""The newest lab built from each template, of the labs the caller may see."""
	labs = frappe.get_list(
		"Lab",
		filters={"template": ("in", [template["key"] for template in LAB_TEMPLATES])},
		fields=["name", "title", "status", "template"],
		order_by="creation desc",
		limit_page_length=0,
	)
	newest: dict[str, dict] = {}
	for lab in labs:
		newest.setdefault(lab.template, lab)
	return newest


def get_template(key: str) -> dict:
	"""Return a single template by key, or throw if it is unknown."""
	for template in LAB_TEMPLATES:
		if template["key"] == key:
			return template
	frappe.throw(_("Unknown lab template '{0}'.").format(key or ""))


def available_lab_id(base: str) -> str:
	"""A free lab id derived from `base`, suffixed only as far as it must be.

	"Use template" creates the lab without asking for a name, so the id is
	picked here. An id the caller typed is never rewritten — it fails loudly on
	collision, as it always did.
	"""
	if not frappe.db.exists("Lab", base):
		return base
	for suffix in range(2, MAX_LAB_ID_ATTEMPTS + 2):
		candidate = f"{base}-{suffix}"
		if not frappe.db.exists("Lab", candidate):
			return candidate
	frappe.throw(_("Too many labs already use the id '{0}'.").format(base))


def create_lab_from_template(template_key: str, lab_id: str | None = None, title: str | None = None) -> str:
	"""Build a Lab document from a template and return its name."""
	template = get_template(template_key)
	lab = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id or available_lab_id(template_key),
			"template": template_key,
			"title": title or template["title"],
			"description": template["description"],
			"frappe_version": template["frappe_version"],
			"instance_size": seeded_instance_size(template),
			"memory_limit": template["memory_limit"],
			"cpu_cores": template["cpu_cores"],
			"apps": [dict(app) for app in template["apps"]],
		}
	)
	lab.insert()
	return lab.name


def seeded_instance_size(template: dict) -> str | None:
	"""The template's `Instance Size`, or nothing when this install has no such row.

	Without a size a template lab kept resources only this file declared, so it was
	neither priced nor resized like any other lab. The existence check is what keeps
	that true for a self-hoster who renamed the seeded sizes: `Lab` leaves the
	declared `memory_limit` / `cpu_cores` alone when no size is set.
	"""
	size = template.get("instance_size")
	return size if size and frappe.db.exists("Instance Size", size) else None
