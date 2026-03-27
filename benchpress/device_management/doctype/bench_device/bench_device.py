# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BenchDevice(Document):
	def on_trash(self):
		if self.wg_public_key:
			from benchpress.wg_manager import remove_peer_from_server, sync_wg_config

			try:
				remove_peer_from_server(self.wg_public_key)
				sync_wg_config()
			except Exception:
				frappe.log_error(title=f"Device WG cleanup failed: {self.name}")
