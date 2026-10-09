"""Document controller for `Admission Denial` -- the decision envelope `admission.claim()`
writes before it throws.

Kept thin, same convention as `job_receipt.py`'s doctype controller: the write/read logic is
a plain module function (`admission.record_denial`), not a Document method, so a future caller
never has to go through `frappe.get_doc` just to log a refusal.
"""

from frappe.model.document import Document


class AdmissionDenial(Document):
	pass
