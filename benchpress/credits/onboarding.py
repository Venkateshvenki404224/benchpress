# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""What happens to a person between "signed up" and "can deploy".

Two things, and each exactly once ever: the account gets the `BenchPress User` role, and the
one-time signup grant lands in a `Credit Account`. Once-ever needs no flag and no lock — a
`Credit Account` is named after the email, so `account.ensure_account` is itself the guard, and a
re-signup after a deletion cannot re-grant without an operator's explicit adjustment.

The grant is deliberately *not* posted the moment a `User` row appears. A row proves somebody
typed an address, not that they hold it, and free credits are exactly what a throwaway-address
farm is after. So the grant follows proof, and the two signup paths prove themselves at different
moments:

- **OAuth proves it at insert.** `frappe.utils.oauth` fills the `social_logins` child table before
  it saves the new user, so a row carrying a provider id can only have come from a completed flow.
  This is the real reason GitHub is the primary button: an aged GitHub account is evidence, and a
  fresh address is not.
- **Email proves it at first login.** `sign_up` sets a password the user never sees, so the only
  route to a session is the verification link. The session is the signal; the `User` row is not.

Both paths call `open_account`, so "granted once" needs no agreement between them.

Nothing here is allowed to fail loudly. A signup that 500s loses the person, and an exception
raised on `on_session_creation` locks somebody out of a site they have just authenticated to —
either is a far worse outcome than a grant that has to be posted by hand, so the failure goes to
the Error Log and the login continues.
"""

from contextlib import contextmanager

import frappe

from benchpress.credits import account, config

ACCESS_ROLE = "BenchPress User"

# The provider name `User.validate` claims for the id it generates for every user. Never evidence
# of a login flow — see `signed_up_with_oauth`.
INTERNAL_PROVIDER = "frappe"

# Raised for the duration of `signup.sign_up`, so the insert it performs can be told apart from any
# other `User` row appearing on the site.
SELF_SERVE_FLAG = "benchpress_self_serve_signup"


@contextmanager
def self_serve_signup():
	"""Mark whatever `User` is inserted inside as somebody signing themselves up."""
	frappe.flags[SELF_SERVE_FLAG] = True
	try:
		yield
	finally:
		frappe.flags.pop(SELF_SERVE_FLAG, None)


def after_user_insert(doc, event=None) -> None:
	"""Give a self-serve signup the app role, and the grant if the signup already proved itself."""
	if not config.credits_enabled() or not is_self_serve(doc):
		return
	grant_access_role(doc)
	if signed_up_with_oauth(doc):
		open_account(doc.name)


def is_self_serve(doc) -> bool:
	"""Whether this row is somebody who signed themselves up, rather than an operator's creation.

	One signal per door, and never a guess from the shape of the row: `signup.sign_up` raises a
	flag for the duration of its call, and an OAuth flow leaves a provider row behind. An operator
	adding a `User` by hand matches neither and gets nothing — granting somebody access on their
	behalf is a decision this hook is not entitled to make, and a Website User is not by itself a
	customer.
	"""
	return bool(frappe.flags.get(SELF_SERVE_FLAG)) or signed_up_with_oauth(doc)


def after_login(login_manager) -> None:
	"""The email path's grant, on `on_session_creation` — once per login, not per request.

	Costs one indexed `exists` on `Credit Account` in the usual case, and nothing at all for a user
	without the app role: an operator is not a customer, and a `System Manager` signing in should
	not be handed a balance.
	"""
	if not has_access_role(login_manager.user):
		return
	open_account(login_manager.user)


def open_account(user: str) -> None:
	"""Create the `Credit Account` and post the signup grant, at most once ever."""
	if not config.credits_enabled():
		return
	try:
		account.ensure_account(user)
	except Exception:
		frappe.log_error(
			title="BenchPress signup grant failed",
			reference_doctype="User",
			reference_name=user,
		)


def signed_up_with_oauth(doc) -> bool:
	"""Whether this user arrived through a `Social Login Key` provider rather than a form.

	Not "has a social login row": `User.validate` gives **every** user one, under the provider name
	`frappe`, holding an id it generates itself — so a row proves nothing and that name is not
	evidence of anything. A row naming any other provider is, because only
	`frappe.utils.oauth.update_oauth_user` writes one, and it does so after the flow completed.

	The exclusion costs a site that has also enabled Frappe-as-an-OAuth-provider nothing worse than
	the email path: those signups are granted at first login instead of at insert. Fail-closed is
	the right direction here — a grant one step late is recoverable, a grant to a farm is not.
	"""
	providers = {row.provider for row in doc.get("social_logins") or []}
	return bool(providers - {INTERNAL_PROVIDER})


def grant_access_role(user_doc) -> None:
	"""Append the app role if it is missing. Idempotent, and never a second save."""
	if has_role(user_doc, ACCESS_ROLE):
		return
	user_doc.append("roles", {"role": ACCESS_ROLE})
	user_doc.save(ignore_permissions=True)


def has_role(user_doc, role: str) -> bool:
	return any(row.role == role for row in user_doc.get("roles") or [])


def has_access_role(user: str) -> bool:
	return ACCESS_ROLE in frappe.get_roles(user)
