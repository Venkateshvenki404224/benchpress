# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per person who asked for hosted access.

The doctype autonames on `email`, so the address is the primary key: a second signup from the
same address is a key conflict the database rejects for free, and no pre-flight lookup is needed
anywhere. Approval is the only transition that touches `User`, and it lives here rather than in
the whitelisted endpoint so a Desk edit and a bulk action take the same path.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, validate_email_address

# One definition of "has access to BenchPress", shared with the self-serve path. An invite and a
# signup must land on the same role, or the two doors would grant different products.
from benchpress.credits.onboarding import ACCESS_ROLE, grant_access_role


class WaitlistEntry(Document):
	def validate(self):
		self.email = normalise_email(self.email)
		self.approved_on = now_datetime() if self.status == "Approved" else None

	def approve(self) -> str:
		"""Grant access and record it. Idempotent — re-approving an entry re-sends nothing."""
		if self.status != "Approved":
			self.status = "Approved"
			self.save(ignore_permissions=True)
		return self.invite_user()

	def invite_user(self) -> str:
		"""Create the login if it does not exist, and make sure it carries the access role."""
		if not frappe.db.exists("User", self.email):
			return self.create_user()

		user = frappe.get_doc("User", self.email)
		grant_access_role(user)
		return user.name

	def create_user(self) -> str:
		user = frappe.new_doc("User")
		user.email = self.email
		user.first_name = self.full_name or self.email.split("@")[0]
		user.send_welcome_email = 1
		user.append("roles", {"role": ACCESS_ROLE})
		user.insert(ignore_permissions=True)
		return user.name


def normalise_email(email: str) -> str:
	"""Lower-cased and validated, so `A@x.com` and `a@x.com` cannot both hold a row."""
	address = validate_email_address(frappe.utils.cstr(email).strip().lower(), throw=False)
	if not address:
		frappe.throw(_("Enter a valid email address."), frappe.ValidationError)
	return address
