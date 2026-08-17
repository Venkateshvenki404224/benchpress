# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Add the ledger's composite index on an existing site.

A fresh install gets it from `seed_defaults` (via `after_install`), which is also where the
reason for a hand-added index is written down.
"""

from benchpress.credits.seed import ensure_ledger_index


def execute():
	ensure_ledger_index()
