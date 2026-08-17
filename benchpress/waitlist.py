# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The hosted waitlist — the app's only guest-reachable endpoint.

`join` is the single door left open to unauthenticated traffic, so it is written as a security
boundary rather than as a form handler: the address is validated before it reaches the database,
the free-text fields are truncated to their column widths, everything else in the request is
dropped, and the answer is identical whether the address was new or already on the list. Telling
a stranger which addresses are registered is a membership oracle, and a waitlist for a paid
product is exactly the list an attacker would enumerate.

Rate limiting is per (IP, email) so one address cannot be sprayed from one host, and the cap is
deliberately low: a human joins a waitlist once.

Once `Credit Settings.waitlist_open` is turned off, self-serve signup has replaced the list and
`join` refuses — a queue nobody is going to work through is worse than no queue. The doctype and
its rows are kept: it is the record of who asked and when, and `notify_of_signup` is the one-shot
that tells everybody on it that the door is now open.
"""

import frappe
from frappe import _
from frappe.database import savepoint
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr, get_url, now_datetime

from benchpress.credits import config
from benchpress.permissions import require_admin

DOCTYPE = "Waitlist Entry"
JOINS_PER_HOUR = 3
DATA_LIMIT = 140
TEXT_LIMIT = 1000
APPROVED = "Approved"


# Deliberately open to Guest: the landing page's waitlist form is the only door this app opens to
# the internet. It writes one row of clipped text, answers identically for a known and an unknown
# address so it cannot enumerate members, and is rate limited per IP and address.
# `test_api_authorization` asserts this stays the app's *only* `allow_guest` method.
@frappe.whitelist(allow_guest=True)  # nosemgrep -- reviewed, see the note above
@rate_limit(key="email", limit=JOINS_PER_HOUR, seconds=60 * 60, ip_based=True)
def join(
	email: str, full_name: str | None = None, company: str | None = None, use_case: str | None = None
) -> dict:
	"""Record an interest in hosted access. Always answers the same way."""
	require_waitlist_open()
	entry = frappe.new_doc(DOCTYPE)
	entry.update(
		{
			"email": email,
			"full_name": clip(full_name, DATA_LIMIT),
			"company": clip(company, DATA_LIMIT),
			"use_case": clip(use_case, TEXT_LIMIT),
		}
	)
	insert_once(entry)
	return {"joined": True, "message": _("You're on the list. We'll email you when a slot opens.")}


def require_waitlist_open() -> None:
	"""Refuse a join once signup has replaced the list, and point at the door that is open.

	Checked before anything is written and before the address is even validated, so a closed list
	costs one cached read. The switch is only consulted when credits are on: a self-hoster running
	this app without the hosted plan has no waitlist to close.
	"""
	if config.credits_enabled() and not config.waitlist_open():
		frappe.throw(
			_("The waitlist is closed — hosted access is open to everyone now. Sign up at {0}.").format(
				config.SIGNUP_ROUTE
			)
		)


@frappe.whitelist()
def notify_of_signup() -> dict:
	"""Tell everybody still on the list that self-serve signup is live. One email each, ever.

	The one-shot the waitlist gets when it is retired. "Ever" is stored on the row rather than
	inferred from the status, because the obvious thing for an operator to do when a run stops
	half-way through a batch is to run it again — and nobody may be mailed twice for that.

	An approved entry already has a login, so it is sent to the login page; anyone else is sent to
	signup. Same email, one link decided by what the person already has.
	"""
	require_admin()
	entries = frappe.get_all(
		DOCTYPE,
		filters={"invite_sent_on": ("is", "not set")},
		fields=["name", "full_name", "status"],
	)
	for entry in entries:
		announce_signup(entry)
	return {"notified": len(entries)}


def announce_signup(entry) -> None:
	route = "/login" if entry.status == APPROVED else config.SIGNUP_ROUTE
	link = get_url(route)
	frappe.sendmail(
		recipients=[entry.name],
		subject=_("Hosted BenchPress is open — your slot is ready"),
		message=_(
			"<p>Hi {0},</p><p>You asked for hosted BenchPress access a while back. It no longer needs an invite — anyone can start, and the free credits are waiting on your account.</p><p><a href='{1}'>{1}</a></p><p>Self-hosting is still free and unmetered; the repo is linked from the site.</p>"
		).format(entry.full_name or entry.name.split("@")[0], link),
	)
	frappe.db.set_value(DOCTYPE, entry.name, "invite_sent_on", now_datetime(), update_modified=False)


@frappe.whitelist()
def approve(entries: str | list) -> dict:
	"""Approve the selected entries and invite each one. Desk bulk action, admins only."""
	require_admin()
	names = frappe.parse_json(entries)
	users = [approve_entry(name) for name in names]
	return {"approved": len(users), "users": users}


def approve_entry(name: str) -> str:
	"""One document per call — approval writes a `User`, so it cannot be a bulk update."""
	return frappe.get_doc(DOCTYPE, name).approve()


def insert_once(entry) -> None:
	"""Insert, and treat a repeat address as success.

	The doctype autonames on the email, so a duplicate is a primary-key conflict the database
	rejects without a lookup. Swallowing it inside a savepoint keeps the surrounding transaction
	usable and keeps the response indistinguishable from a first-time join.
	"""
	with savepoint(catch=frappe.DuplicateEntryError):
		entry.insert(ignore_permissions=True)


def clip(value, limit: int) -> str:
	"""Trim optional free text to its column width before it reaches the database."""
	return cstr(value).strip()[:limit]
