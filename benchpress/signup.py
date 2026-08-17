# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Self-serve signup — the second and last door this app opens to the internet.

Frappe already ships the whole mechanism: the `/login#signup` form, the OAuth buttons behind every
enabled `Social Login Key`, and the verification mail. What it does not ship are the two decisions
a hosted BenchPress has to make before a stranger's address becomes an account with free credits
in it. So this wraps `frappe.core.doctype.user.user.sign_up` through
`override_whitelisted_methods` rather than adding a route of its own — the login page keeps posting
the same `cmd`, and there is no second signup path to keep in step with the first.

The two decisions:

- **Is self-serve open at all?** One switch, `Credit Settings.waitlist_open`. While it is on this
  refuses and the landing page shows the waitlist form; when it is off the CTA becomes "Start
  free" and the waitlist refuses instead.
- **Is this address worth a free grant?** A disposable-domain blocklist, held in Desk so it can be
  extended the afternoon a farm appears. Only the email path is checked — an OAuth signup has
  already proved an account at GitHub or Google, which is why that button is the primary one.

Rate limiting is per (IP, address) like the waitlist's, and for the same reason: a person signs up
once, so a low ceiling costs a real visitor nothing and costs a script everything. Frappe's own
site-wide `max_signups_allowed_per_hour` sits underneath as a backstop, not a substitute — it caps
the total and cannot tell one host from another.

With `enable_credits` off none of this applies and the call is Frappe's unmodified signup, because
a self-hoster who never asked for the hosted plan must not find their login page rewritten by it.
"""

import frappe
from frappe import _
from frappe.core.doctype.user.user import sign_up as frappe_sign_up
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr

from benchpress.credits import config, onboarding

SIGNUPS_PER_HOUR = 3


# Deliberately open to Guest: this *is* the signup form's endpoint, and it replaces a method Frappe
# already exposes to guests, so the surface is not widened here — only narrowed, by the two checks
# below. `test_api_authorization` asserts the app's guest inventory stays exactly this and the
# waitlist, so a third one cannot appear unnoticed.
@frappe.whitelist(allow_guest=True)  # nosemgrep -- reviewed, see the note above
@rate_limit(key="email", limit=SIGNUPS_PER_HOUR, seconds=60 * 60, ip_based=True)
def sign_up(email: str, full_name: str, redirect_to: str = "") -> tuple[int, str]:
	"""Frappe's signup, behind the hosted plan's two gates. Answers exactly as Frappe's does.

	The insert happens inside `self_serve_signup`, which is how `onboarding.after_user_insert` tells
	this `User` from one an operator created — the row itself carries nothing that distinguishes
	them.
	"""
	if config.credits_enabled():
		require_signup_open()
		reject_blocked_domain(email)
	with onboarding.self_serve_signup():
		return frappe_sign_up(email, full_name, redirect_to)


def require_signup_open() -> None:
	"""Refuse while hosted access is still invite-only, and say where the queue is."""
	if config.waitlist_open():
		frappe.throw(
			_("Hosted access is invite-only for now. Join the waitlist and we'll email you a login."),
			title=_("Not Allowed"),
		)


def reject_blocked_domain(email: str) -> None:
	"""Refuse a throwaway domain, and name the rule.

	Naming it is safe here in a way it is not on the waitlist: this discloses which domains the
	site declines, never who is registered, and a visitor who is refused without being told why
	reads a working rule as a broken form.
	"""
	if domain_of(email) in config.blocked_email_domains():
		frappe.throw(
			_("Signups from that email domain aren't accepted. Use an address you own, or sign in with GitHub."),
			title=_("Not Allowed"),
		)


def domain_of(email: str) -> str:
	"""The part after the last `@`, lower-cased. Empty for anything that is not an address."""
	return cstr(email).strip().lower().rpartition("@")[2]
