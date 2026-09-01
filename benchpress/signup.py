# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Self-serve signup: Frappe's own `sign_up`, behind the hosted plan's two gates."""

import frappe
from frappe import _
from frappe.core.doctype.user.user import sign_up as frappe_sign_up
from frappe.utils import cstr

from benchpress.credits import config, onboarding
from benchpress.public_site import require_public_site
from benchpress.throttle import public_form

SIGNUPS_PER_HOUR = 3


# Overrides a method Frappe already exposes to guests, so the surface is narrowed here, not
# widened.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep -- reviewed, see the note above
@public_form(limit=SIGNUPS_PER_HOUR)
def sign_up(email: str, full_name: str, redirect_to: str = "") -> tuple[int, str]:
	"""Frappe's signup, behind the hosted plan's two gates. Answers exactly as Frappe's does."""
	require_public_site()
	if config.credits_enabled():
		require_signup_open()
		reject_blocked_domain(email)
	with onboarding.self_serve_signup():
		return frappe_sign_up(email, full_name, redirect_to)


def require_signup_open() -> None:
	if config.waitlist_open():
		frappe.throw(
			_("Hosted access is invite-only for now. Join the waitlist and we'll email you a login."),
			title=_("Not Allowed"),
		)


def reject_blocked_domain(email: str) -> None:
	if domain_of(email) in config.blocked_email_domains():
		frappe.throw(
			_("That email domain isn't accepted. Use an address you own, or sign in with GitHub."),
			title=_("Not Allowed"),
		)


def domain_of(email: str) -> str:
	return cstr(email).strip().lower().rpartition("@")[2]
