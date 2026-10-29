# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per refused claim. The artifact `admission.claim` did not leave before this.

A refusal raises `frappe.ValidationError` and the caller's transaction rolls back — so a row
written in the normal way, as part of that same transaction, vanishes with it. This doctype
exists to be written and committed *before* the throw, specifically so it survives the
rollback that erases everything else the refused call touched. See
`benchpress.credits.admission._deny` for the write path and why it commits early.
"""

from frappe.model.document import Document


class AdmissionDenial(Document):
	pass
