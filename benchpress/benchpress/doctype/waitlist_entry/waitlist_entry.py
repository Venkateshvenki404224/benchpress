# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""One row per person who asked for hosted access.

The doctype autonames on `email`, so the address is the primary key: a second signup from the
same address is a key conflict the database rejects for free, and no pre-flight lookup is needed
anywhere. Approval is the only transition that touches `User`, and it lives here rather than in
the whitelisted endpoint so a Desk edit and a bulk action take the same path.
"""

import hashlib
import hmac

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, validate_email_address
from frappe.utils.password import get_encryption_key

# One definition of "has access to BenchPress", shared with the self-serve path. An invite and a
# signup must land on the same role, or the two doors would grant different products.
from benchpress.credits.onboarding import ACCESS_ROLE, grant_access_role

REFERENCE_PREFIX = "REQ"
WEBSITE_USER = "Website User"


class WaitlistEntry(Document):
	def onload(self):
		self.set_onload("reference", self.request_reference())

	def validate(self):
		self.email = normalise_email(self.email)
		self.approved_on = now_datetime() if self.status == "Approved" else None
		self.rejected_on = now_datetime() if self.status == "Rejected" else None

	def request_reference(self) -> str:
		"""A short, stable handle for this request. Derived on read, never stored."""
		return derive_reference(self.name)

	def approve(self) -> str:
		"""Grant access and record it. Idempotent — re-approving an entry re-sends nothing."""
		# The decision, not the call, is what gets mailed: an operator re-running the bulk action
		# over a page of rows must not mail everybody on it a second time.
		decided_now = self.status != "Approved"
		if decided_now:
			self.status = "Approved"
			self.save(ignore_permissions=True)
		created_now = not frappe.db.exists("User", self.email)
		user = self.invite_user()
		if decided_now:
			send_notice(
				"send_access_request_approved",
				self,
				set_password_url=set_password_url(user) if created_now else "",
			)
		return user

	def reject(self, reason: str = "") -> None:
		"""The other half of `approve` — records the decision so the notice can name it."""
		# Imported here, not at module scope: `waitlist` imports this module for `derive_reference`.
		from benchpress.waitlist import TEXT_LIMIT, clip

		self.status = "Rejected"
		self.rejection_reason = clip(reason, TEXT_LIMIT)
		self.save(ignore_permissions=True)
		send_notice("send_access_request_declined", self)

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
		# The approval mail carries the set-password link itself, so Frappe's welcome mail would
		# be a second mail saying the same thing — and a second key, invalidating the first.
		user.send_welcome_email = 0
		user.append("roles", {"role": ACCESS_ROLE})
		user.insert(ignore_permissions=True)
		# After the insert, not before: `User.set_system_user` re-derives the type from role desk
		# access on every save.
		user.db_set("user_type", WEBSITE_USER)
		return user.name


def derive_reference(email: str) -> str:
	"""`REQ-XXXX-XXXX` from the row name, keyed so a stranger cannot recompute it."""
	# Keyed with the site's encryption key, so holding a candidate address is not enough to
	# confirm it, and a pure function of the address, so a repeat join answers identically.
	key = get_encryption_key().encode()
	digest = hmac.new(key, normalise_email(email).encode(), hashlib.sha256).hexdigest()
	return f"{REFERENCE_PREFIX}-{digest[:4].upper()}-{digest[4:8].upper()}"


def set_password_url(user: str) -> str:
	"""Frappe's own one-time key, so the approval mail carries the way in. Never raises."""
	try:
		return frappe.get_doc("User", user)._reset_password()
	except Exception:
		frappe.log_error(title="BenchPress set-password link failed", message=frappe.get_traceback())
		return ""


def send_notice(sender: str, entry, **context) -> None:
	"""Fire one `benchpress.emails` sender. Never raises — mail must not undo a decision."""
	try:
		from benchpress import emails

		getattr(emails, sender)(entry, **context)
	except Exception:
		frappe.log_error(
			title=f"BenchPress access request email failed: {sender}",
			message=frappe.get_traceback(),
		)


def normalise_email(email: str) -> str:
	"""Lower-cased and validated, so `A@x.com` and `a@x.com` cannot both hold a row."""
	address = validate_email_address(frappe.utils.cstr(email).strip().lower(), throw=False)
	if not address:
		frappe.throw(_("Enter a valid email address."), frappe.ValidationError)
	return address
