# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Give an existing site the `waitlist_open` default that only a fresh install materialises.

A Single stores nothing but the fields somebody has written, so a field added to `Credit Settings`
by a migrate reads `None` on every site that already had the Single — the `default` in the DocType
JSON only applies when the document is built. `None` is falsy, and falsy here means *closed*, so
without this patch a migrate would silently retire the waitlist and open self-serve signup on a
site whose operator asked for neither.

Written only when the field has never been set, so an operator who has already turned it off keeps
that decision through the next migrate. "Never been set" has to be asked of the stored rows, not
of `get_single_value`: that reader casts a missing value through the field's type, so an unset
`Check` comes back as `0` and is indistinguishable from a deliberate zero. `get_singles_dict`
returns only the fields that actually have a row, which is the question this patch is asking.
"""

import frappe

SETTINGS = "Credit Settings"
FIELD = "waitlist_open"


def execute():
	if FIELD not in frappe.db.get_singles_dict(SETTINGS):
		frappe.db.set_single_value(SETTINGS, FIELD, 1)
