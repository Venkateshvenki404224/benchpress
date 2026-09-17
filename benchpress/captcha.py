# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Cloudflare Turnstile on the guest forms. No keys, no widget, no check."""

import frappe
import requests
from frappe import _
from frappe.utils import cstr

SITE_KEY = "benchpress_turnstile_site_key"
SECRET_KEY = "benchpress_turnstile_secret_key"

# The hidden input the widget adds to the form it sits in.
TOKEN_FIELD = "cf-turnstile-response"
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT = 5

# These describe this deployment or Cloudflare, not the visitor, so they must not refuse the visitor.
NOT_THE_VISITOR = frozenset({"missing-input-secret", "invalid-input-secret", "internal-error"})
SKIPPED_TITLE = "BenchPress Turnstile check skipped"


def site_key() -> str:
	"""The key the widget renders with. Empty unless the secret is set too, so no half-on check."""
	return config_value(SITE_KEY) if config_value(SECRET_KEY) else ""


def require_human() -> None:
	"""Refuse a guest post that Cloudflare does not vouch for. Does nothing while the keys are unset."""
	# Outside a request there is no visitor to check: a console call, or a test.
	if not frappe.request or not site_key():
		return
	token = cstr(frappe.form_dict.get(TOKEN_FIELD)).strip()
	# An empty token is refused before the outbound call, so a bare script costs one Redis count.
	if not token or not vouched_for(token):
		frappe.throw(
			_("We could not confirm a person sent this. Reload the page and send it again."),
			frappe.ValidationError,
		)


def vouched_for(token: str) -> bool:
	"""Cloudflare's verdict, or True when there is none: spam costs less than a lost request."""
	# `requests`, not `make_post_request`: that helper takes no timeout, and a hung call holds a web worker.
	try:
		response = requests.post(
			VERIFY_URL,
			data={"secret": config_value(SECRET_KEY), "response": token, "remoteip": frappe.local.request_ip},
			timeout=TIMEOUT,
		)
		response.raise_for_status()
		verdict = response.json()
	except (requests.RequestException, ValueError):
		frappe.log_error(title=SKIPPED_TITLE, message=frappe.get_traceback())
		return True

	codes = set(verdict.get("error-codes") or ())
	if codes & NOT_THE_VISITOR:
		frappe.log_error(title=SKIPPED_TITLE, message=", ".join(sorted(codes)))
		return True
	return bool(verdict.get("success"))


def config_value(key: str) -> str:
	return cstr(frappe.conf.get(key)).strip()
