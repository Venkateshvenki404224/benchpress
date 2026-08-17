# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Add the composite indexes behind the lab, site and log reads on an existing site.

`after_install` covers a fresh site; every site already deployed needs them applied once.
`ensure_indexes` is idempotent.
"""

from benchpress.indexes import ensure_indexes


def execute():
	ensure_indexes()
