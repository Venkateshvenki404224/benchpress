# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Catalog of ready-made lab templates.

Templates live in the `Lab Template` DocType, so an admin adds, edits or retires a stack
(Frappe, ERPNext, CRM) from Desk instead of editing source and shipping a PR.
``create_lab_from_template`` materialises a template into an ordinary, editable Lab document,
after which the normal build/deploy flow takes over.
"""

import frappe
from frappe import _

# Each template names its `Instance Size`. `memory_limit` / `cpu_cores` below must agree
# with it: nothing rewrites them at save time, and the card renders what is stored.

# "Use template" names the lab itself, so a taken id is retried with a numeric
# suffix. The ceiling only exists so a pathological catalog cannot spin.
MAX_LAB_ID_ATTEMPTS = 50

TEMPLATE_FIELDS = [
	"name as key",
	"title",
	"logo",
	"description",
	"frappe_version",
	"instance_size",
	"memory_limit",
	"cpu_cores",
	"eta_minutes",
	"most_used",
]
APP_FIELDS = ["app_name", "app_label", "git_url", "branch"]

# Seeded once into `Lab Template` (fresh install and `bench migrate` alike) and never read
# directly at runtime after that — `seed_lab_templates` only inserts what's missing, so an
# admin's edit or deletion in Desk survives every later migrate.
SEED_TEMPLATES = [
	{
		"key": "frappe",
		"title": "Frappe Framework",
		"description": "Bare Frappe bench with no extra apps — the lightest starting point.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 3,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 1,
		"apps": [],
	},
	{
		"key": "erpnext",
		"title": "ERPNext",
		"description": "Full ERP suite: accounting, inventory, manufacturing and more.",
		"frappe_version": "version-15",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 6,
		"most_used": 1,
		"is_active": 1,
		"sort_order": 2,
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
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 3,
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
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 5,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 4,
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
		"title": "Frappe Learning",
		"description": "Learning management system — courses, quizzes and batches.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 5,
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
		"title": "Frappe Helpdesk",
		"description": "Customer support desk — tickets, SLAs and a knowledge base.",
		"frappe_version": "version-15",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 6,
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
		"title": "ERPNext + India Compliance",
		"description": "ERPNext with GST, e-invoicing and TDS for Indian businesses.",
		"frappe_version": "version-15",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 7,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 7,
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
	{
		"key": "erpnext-16",
		"title": "ERPNext",
		"description": "Full ERP suite: accounting, inventory, manufacturing and more.",
		"frappe_version": "version-16",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 6,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 8,
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-16",
			}
		],
	},
	{
		"key": "frappe-16",
		"title": "Frappe Framework",
		"description": "Bare Frappe bench with no extra apps — the lightest starting point.",
		"frappe_version": "version-16",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 3,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 9,
		"apps": [],
	},
	{
		"key": "crm-16",
		"title": "Frappe CRM",
		"description": "Lightweight sales CRM on Frappe — leads, deals and contacts.",
		"frappe_version": "version-16",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 10,
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
		"key": "hrms-16",
		"title": "Frappe HR",
		"description": "HR & payroll suite — employees, leaves, attendance and payroll.",
		"frappe_version": "version-16",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 5,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 11,
		# hrms requires erpnext, so erpnext must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-16",
			},
			{
				"app_name": "hrms",
				"app_label": "Frappe HR",
				"git_url": "https://github.com/frappe/hrms",
				"branch": "version-16",
			},
		],
	},
	{
		"key": "lms-16",
		"title": "Frappe Learning",
		"description": "Learning management system — courses, quizzes and batches.",
		"frappe_version": "version-16",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 12,
		# lms requires payments, so payments must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "payments",
				"app_label": "Payments",
				"git_url": "https://github.com/frappe/payments",
				"branch": "version-16",
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
		"key": "helpdesk-16",
		"title": "Frappe Helpdesk",
		"description": "Customer support desk — tickets, SLAs and a knowledge base.",
		"frappe_version": "version-16",
		"instance_size": "Small",
		"memory_limit": "1g",
		"cpu_cores": 1,
		"eta_minutes": 4,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 13,
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
		"key": "india-compliance-16",
		"title": "ERPNext + India Compliance",
		"description": "ERPNext with GST, e-invoicing and TDS for Indian businesses.",
		"frappe_version": "version-16",
		"instance_size": "Medium",
		"memory_limit": "2g",
		"cpu_cores": 2,
		"eta_minutes": 7,
		"most_used": 0,
		"is_active": 1,
		"sort_order": 14,
		# india_compliance extends ERPNext, so ERPNext must install first. The
		# build/deploy pipeline installs apps in this listed order.
		"apps": [
			{
				"app_name": "erpnext",
				"app_label": "ERPNext",
				"git_url": "https://github.com/frappe/erpnext",
				"branch": "version-16",
			},
			{
				"app_name": "india_compliance",
				"app_label": "India Compliance",
				"git_url": "https://github.com/resilient-tech/india-compliance",
				"branch": "version-16",
			},
		],
	},
]


def get_templates() -> list[dict]:
	"""Return the active catalog of lab templates, in display order."""
	templates = frappe.get_all(
		"Lab Template", filters={"is_active": 1}, fields=TEMPLATE_FIELDS, order_by="sort_order asc"
	)
	apps = _apps_by_template([template.key for template in templates])
	for template in templates:
		template["apps"] = apps.get(template.key, [])
	return templates


def _apps_by_template(keys: list[str]) -> dict[str, list[dict]]:
	"""Every listed template's app rows, fetched in one query and grouped by template key.

	`Lab App` is shared with `Lab.apps` — rows are told apart by `parenttype`, not a second,
	near-duplicate child doctype.
	"""
	if not keys:
		return {}
	rows = frappe.get_all(
		"Lab App",
		filters={"parent": ("in", keys), "parenttype": "Lab Template"},
		fields=["parent", *APP_FIELDS],
		order_by="idx asc",
	)
	grouped: dict[str, list[dict]] = {}
	for row in rows:
		grouped.setdefault(row.pop("parent"), []).append(row)
	return grouped


def get_catalog() -> list[dict]:
	"""The catalog as the Templates page reads it: each template and the lab it built."""
	built = _labs_by_template()
	return [{**template, "lab": built.get(template["key"])} for template in get_templates()]


def _labs_by_template() -> dict[str, dict]:
	"""The newest lab built from each template, of the labs the caller may see."""
	keys = frappe.get_all("Lab Template", pluck="name")
	labs = frappe.get_list(
		"Lab",
		filters={"template": ("in", keys)},
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
	if not frappe.db.exists("Lab Template", key):
		frappe.throw(_("Unknown lab template '{0}'.").format(key or ""))
	doc = frappe.get_doc("Lab Template", key)
	return {
		"key": doc.name,
		"title": doc.title,
		"description": doc.description,
		"frappe_version": doc.frappe_version,
		"instance_size": doc.instance_size,
		"memory_limit": doc.memory_limit,
		"cpu_cores": doc.cpu_cores,
		"eta_minutes": doc.eta_minutes,
		"most_used": doc.most_used,
		"apps": [{field: app.get(field) for field in APP_FIELDS} for app in doc.apps],
	}


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


def create_lab_from_template(
	template_key: str,
	lab_id: str | None = None,
	title: str | None = None,
	*,
	ignore_permissions: bool = False,
) -> str:
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
	# `Lab` grants `create` to admins alone, so a BenchPress User launching a template could not
	# materialise one. The recipe is the template's own either way — the caller authors nothing.
	lab.insert(ignore_permissions=ignore_permissions)
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


def seed_lab_templates() -> None:
	"""Idempotent. Safe to call on every install and from the patch — inserts only what's missing."""
	existing = set(frappe.get_all("Lab Template", pluck="name"))
	for template in SEED_TEMPLATES:
		if template["key"] in existing:
			continue
		frappe.get_doc({"doctype": "Lab Template", **template}).insert(ignore_permissions=True)
