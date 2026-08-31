# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class SignupPageSettings(Document):
	"""Copy for /signup and the branded /login."""

	# No cache to drop: both pages read this through frappe.get_cached_doc.
