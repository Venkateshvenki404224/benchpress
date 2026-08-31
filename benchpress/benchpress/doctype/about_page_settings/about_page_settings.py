# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from benchpress.benchpress.site_content import clear_content_cache


class AboutPageSettings(Document):
	def on_update(self):
		clear_content_cache()
