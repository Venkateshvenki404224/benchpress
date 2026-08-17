# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Add the ledger's `(reference_doctype, reference_name)` index on an existing site.

`benchpress.patches.index_credit_ledger` already ran and only added the statement index, so the
replay guard the payment flow depends on needs a patch of its own. `ensure_ledger_index` adds
both and is idempotent, so re-running the earlier one would have worked too — this exists because
a patch that has already executed never runs again.
"""

from benchpress.credits.seed import ensure_ledger_index


def execute():
	ensure_ledger_index()
