# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Add the ledger's `(account, request_id)` index on an existing site.

The replay guard reads that key under a lock, so it holds the gap its own ledger row is inserted
into. Scoped to one account the gap is one account's, and two tenants renewing at the same
instant no longer deadlock over the same range. The earlier index patches have already run and
never run again, so the third index needs a patch of its own.
"""

from benchpress.credits.seed import ensure_ledger_index


def execute():
	ensure_ledger_index()
