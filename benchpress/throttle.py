# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Rate limits for the guest-writable forms: a counter per endpoint, under a per-address ceiling."""

from functools import wraps
from inspect import signature

import frappe
from frappe import _
from frappe.utils import cstr

HOUR = 60 * 60
PER_ADDRESS_HOURLY = 10


def public_form(limit: int):
	"""Rate limit a guest endpoint per address and email, and per address alone."""

	def decorator(fn):
		endpoint = f"{fn.__module__}.{fn.__name__}"
		bind = signature(fn).bind_partial

		@wraps(fn)
		def wrapper(*args, **kwargs):
			if frappe.request:
				# The email comes off the call, not `form_dict`: a website post-back reaches the
				# endpoint as a plain Python call and carries no request parameters at all.
				email = cstr(bind(*args, **kwargs).arguments.get("email")).strip().lower()
				address = frappe.local.request_ip
				spend(f"{endpoint}:{address}:{email}", limit)
				spend(f"{endpoint}:{address}", PER_ADDRESS_HOURLY)
			return fn(*args, **kwargs)

		return wrapper

	return decorator


def spend(identity: str, limit: int) -> None:
	key = frappe.cache.make_key(f"rl:{identity}")
	if not frappe.cache.get(key):
		frappe.cache.setex(key, HOUR, 0)
	if frappe.cache.incrby(key, 1) > limit:
		frappe.throw(
			_("You hit the rate limit because of too many requests. Please try after sometime."),
			frappe.RateLimitExceededError,
		)
