"""Document controller for `Job Receipt` — minting/transition logic lives in `benchpress/job_receipt.py`.

Kept thin on purpose: the module-method hook Frappe calls on `doctype.on_update` only needs
this file to exist and import cleanly. The actual mint/claim/unknown/failed functions are
plain module functions in `benchpress.job_receipt`, not Document methods, so other code
(ingress.py, future retrofit call-sites) imports `job_receipt` directly rather than going
through `frappe.get_doc` for every state transition.
"""

from frappe.model.document import Document


class JobReceipt(Document):
	pass
