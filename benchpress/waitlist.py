# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The hosted waitlist: one guest-writable endpoint, and the admin actions that work the queue."""

import frappe
from frappe import _
from frappe.database import savepoint
from frappe.utils import cint, cstr, get_url, now_datetime

from benchpress.benchpress.doctype.waitlist_entry.waitlist_entry import derive_reference, send_notice
from benchpress.credits import config
from benchpress.permissions import require_admin
from benchpress.public_site import require_public_site
from benchpress.throttle import public_form

DOCTYPE = "Waitlist Entry"
JOINS_PER_HOUR = 3
DATA_LIMIT = 140
TEXT_LIMIT = 1000
APPROVED = "Approved"


# Guest-writable by design; answers identically for a known and an unknown address so it cannot
# be used to enumerate members.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep -- reviewed, see the note above
@public_form(limit=JOINS_PER_HOUR)
def join(
	email: str,
	full_name: str | None = None,
	company: str | None = None,
	use_case: str | None = None,
	team_size: str | None = None,
	intent: str | None = None,
	expected_apps: str | None = None,
	consented: int | str | None = None,
	source: str | None = None,
) -> dict:
	"""Record an interest in hosted access. Always answers the same way."""
	require_public_site()
	require_waitlist_open()
	entry = frappe.new_doc(DOCTYPE)
	entry.update(
		{
			"email": email,
			"full_name": clip(full_name, DATA_LIMIT),
			"company": clip(company, DATA_LIMIT),
			"expected_apps": clip(expected_apps, DATA_LIMIT),
			"use_case": clip(use_case, TEXT_LIMIT),
			"team_size": match_option("team_size", team_size),
			"intent": match_option("intent", intent),
			"source": match_option("source", source),
			# Recorded, not enforced: refusing here would leak the form's shape to a script.
			"consented": cint(consented),
		}
	)
	if insert_once(entry):
		announce_request(entry)
	# Derived from the argument, not read back off the row, so a repeat address answers identically.
	return {
		"joined": True,
		"reference": derive_reference(email),
		"message": _("You're on the list. We'll email you when a slot opens."),
	}


def require_waitlist_open() -> None:
	"""Refuse a join once signup has replaced the list."""
	if config.credits_enabled() and not config.waitlist_open():
		frappe.throw(
			_("The waitlist is closed — hosted access is open to everyone now. Sign up at {0}.").format(
				config.SIGNUP_ROUTE
			)
		)


@frappe.whitelist()
def notify_of_signup() -> dict:
	"""Tell everybody still on the list that signup is live. One email each, ever."""
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
	try:
		frappe.sendmail(
			recipients=[entry.name],
			subject=_("Hosted BenchPress is open — your slot is ready"),
			message=_(
				"<p>Hi {0},</p><p>You asked for hosted BenchPress access a while back. It no longer needs an invite — anyone can start, and the free credits are waiting on your account.</p><p><a href='{1}'>{1}</a></p><p>Self-hosting is still free and unmetered; the repo is linked from the site.</p>"
			).format(entry.full_name or entry.name.split("@")[0], link),
		)
	except Exception:
		# Not stamped, so the next run offers this entry again rather than recording a silent miss.
		frappe.log_error(title="BenchPress invite failed", message=frappe.get_traceback())
		return
	frappe.db.set_value(DOCTYPE, entry.name, "invite_sent_on", now_datetime(), update_modified=False)


@frappe.whitelist()
def approve(entries: str | list) -> dict:
	"""Approve the selected entries and invite each one. Desk bulk action, admins only."""
	require_admin()
	names = frappe.parse_json(entries)
	users = [approve_entry(name) for name in names]
	return {"approved": len(users), "users": users}


def approve_entry(name: str) -> str:
	return frappe.get_doc(DOCTYPE, name).approve()


@frappe.whitelist()
def reject(entries: str | list, reason: str = "") -> dict:
	"""Decline the selected entries and tell each one. Desk bulk action, admins only."""
	# Only this path mails; a status flipped in the Desk form is a correction, not a decline.
	require_admin()
	names = frappe.parse_json(entries)
	for name in names:
		frappe.get_doc(DOCTYPE, name).reject(reason)
	return {"rejected": len(names)}


def insert_once(entry) -> bool:
	"""Insert, treating a repeat address as success. Returns whether a row was written."""
	# The doctype autonames on the email, so a duplicate is a primary-key conflict; swallowing it
	# inside a savepoint keeps the surrounding transaction usable.
	written = False
	with savepoint(catch=frappe.DuplicateEntryError):
		entry.insert(ignore_permissions=True)
		written = True
	return written


def announce_request(entry) -> None:
	"""Acknowledge the request and tell the admins. Insert path only, so a repeat mails nobody."""
	send_notice("send_access_request_received", entry)
	send_notice("notify_admins_of_access_request", entry)


def match_option(fieldname: str, value) -> str:
	"""Keep a Select value only if the column offers it; anything else becomes the field default."""
	field = frappe.get_meta(DOCTYPE).get_field(fieldname)
	options = [line.strip() for line in cstr(field.options).split("\n") if line.strip()]
	chosen = cstr(value).strip()
	return chosen if chosen in options else cstr(field.default)


def clip(value, limit: int) -> str:
	return cstr(value).strip()[:limit]
