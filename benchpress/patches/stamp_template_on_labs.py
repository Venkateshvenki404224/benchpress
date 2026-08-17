# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Name the template every existing lab was created from.

`Lab.template` is new, so labs built before it carry nothing and the Templates page cannot tell
they exist. "Use template" names a lab after the template key, suffixing only on collision, so
an id of `key` or `key-2` identifies its template. Hand-named labs are left alone.
"""

import re

import frappe

from benchpress.lab_templates import get_templates


def execute():
	for template in get_templates():
		key = template["key"]
		for name in _labs_from(key):
			frappe.db.set_value("Lab", name, "template", key, update_modified=False)


def _labs_from(key: str) -> list[str]:
	"""Labs whose id reads as one "Use template" click on this key."""
	suffixed = re.compile(rf"^{re.escape(key)}(-\d+)?$")
	labs = frappe.get_all(
		"Lab",
		filters={"lab_id": ("like", f"{key}%"), "template": ("in", ["", None])},
		fields=["name", "lab_id"],
	)
	return [lab.name for lab in labs if suffixed.match(lab.lab_id)]
