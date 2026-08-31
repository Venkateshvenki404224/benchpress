# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class ContactPageSettings(Document):
	def validate(self):
		self.check_one_default_topic()

	def check_one_default_topic(self) -> None:
		defaults = [row.label for row in self.topics if row.is_default]
		if len(defaults) > 1:
			frappe.throw(_("Only one topic can be the default. These are: {0}.").format(", ".join(defaults)))

	def topic_labels(self) -> list[str]:
		return [row.label for row in self.topics if row.label]

	def default_topic(self) -> str:
		flagged = next((row.label for row in self.topics if row.is_default and row.label), "")
		return flagged or next(iter(self.topic_labels()), "")

	def resolve_topic(self, label: str | None) -> str:
		submitted = cstr(label).strip()
		return submitted if submitted in self.topic_labels() else self.default_topic()

	def route_for(self, topic: str) -> str:
		routed = next((row.route_to_email for row in self.topics if row.label == topic), "")
		return routed or cstr(self.notify_email)

	def response_window(self, topic: str) -> str:
		matched = next((row.window for row in self.response_times if row.subject == topic), "")
		return matched or next((row.window for row in self.response_times), "")
