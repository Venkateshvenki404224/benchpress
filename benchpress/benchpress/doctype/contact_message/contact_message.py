# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import cstr

NAME_LIMIT = 140
EMAIL_LIMIT = 140
TOPIC_LIMIT = 60
MESSAGE_LIMIT = 4000

NEW = "New"
ANSWERED = "Answered"


class ContactMessage(Document):
	# Rows are written by guests, so autoname is a hash: the table is not enumerable.
	def validate(self):
		self.sender_name = clip(self.sender_name, NAME_LIMIT)
		self.email = clip(self.email, EMAIL_LIMIT)
		self.topic = clip(self.topic, TOPIC_LIMIT)
		self.message = clip(self.message, MESSAGE_LIMIT)


def clip(value, limit: int) -> str:
	return cstr(value).strip()[:limit]
