# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Context for the public landing page.

The pricing on this page is not written into the markup — it is read from `Credit Pack` and
`Instance Size`, so an operator retunes a price in Desk and the page changes on the next request
with no deploy. That single requirement is why the landing page is a Jinja `www` page and not a
static file or a route in the Vue SPA (whose router redirects every guest to `/login`).

The whole page costs two queries: one for the packs, one for the sizes. Everything else is either
a Single served from cache or a module constant, and the price strings are formatted in Python
rather than through `fmt_money`, which reads number-format defaults from the database.
"""

import os

import frappe
from frappe.utils import cint, flt

from benchpress.credits.config import (
	SIGNUP_ROUTE,
	active_packs,
	default_size,
	instance_sizes,
	settings,
	waitlist_open,
)
from benchpress.www.home_content import ACTIVE_PHASE, PHASES

REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
LICENSE_LABEL = "AGPL-3.0"
VIDEO_DIRECTORY = ("public", "videos")
HERO_VIDEO = "hero.mp4"
HERO_POSTER = "hero-poster.jpg"
CACHE_BUST_PATHS = (
	("public", "css", "landing.css"),
	("public", "css", "landing-mock.css"),
	("public", "js", "landing.js"),
	("public", "images", "logo"),
	("public", "manifest.json"),
	("public", "videos"),
)

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "BenchPress — pick a template, press deploy"
	context.sizes = rate_rows()
	context.default_size = default_size()
	context.packs = priced_packs()
	context.build_credits = cint(settings().custom_build_credits)
	context.free_credits = cint(settings().signup_grant_credits)
	context.repo_url = REPO_URL
	context.license_label = LICENSE_LABEL
	context.waitlist_open = waitlist_open()
	context.start_route = start_route(context.waitlist_open)
	context.phases = PHASES
	context.active_phase = ACTIVE_PHASE
	context.csrf_token = session_csrf_token()
	context.asset_version = asset_version()
	context.hero_media = hero_media(context.asset_version)
	return context


def start_route(is_waitlist_open: bool) -> str:
	"""Where every "Start free" on the page points.

	One value, resolved once, because the page carries five of these buttons — header, hero, each
	pack card, the open-source panel and the footer — and a switch that moved four of them would
	be worse than one that moved none.
	"""
	return "#waitlist" if is_waitlist_open else SIGNUP_ROUTE


def session_csrf_token() -> str:
	"""Only for a signed-in visitor.

	Guests are exempt from CSRF, and minting a token for them would write the session store on
	every hit of a page that should be cheap and cacheable.
	"""
	if frappe.session.user == "Guest":
		return ""
	return frappe.sessions.get_csrf_token()


def rate_rows() -> list[dict]:
	"""The hourly rate table. Built as new rows so the request-cached size index stays untouched."""
	return [
		{
			"label": size.size_label,
			"rate": rate_label(size.credits_per_hour),
			"memory": size.memory_limit,
			"cores": cint(size.cpu_cores),
		}
		for size in instance_sizes()
	]


def rate_label(credits_per_hour) -> str:
	"""`1.0` → `1 credit / hour`, `1.5` → `1.5 credits / hour`."""
	amount = flt(credits_per_hour)
	number = cint(amount) if amount == cint(amount) else amount
	return f"{number} credit{'' if number == 1 else 's'} / hour"


def priced_packs() -> list[dict]:
	"""Packs with the two strings the cards need: a formatted price and a plain-English size."""
	hourly_rate = flt(default_size() and default_size().credits_per_hour)
	return [decorate_pack(pack, hourly_rate) for pack in active_packs()]


def decorate_pack(pack: dict, hourly_rate: float) -> dict:
	pack["price"] = rupees(pack["inr_price"])
	pack["credits"] = cint(pack["credits"])
	pack["running_hours"] = cint(pack["credits"] / hourly_rate) if hourly_rate else 0
	return pack


def rupees(amount) -> str:
	"""`499` → `₹499`. Deliberately not `fmt_money`: it reads defaults from the database."""
	return f"₹{cint(amount):,}"


def hero_media(version: str) -> dict:
	"""Which hero assets actually exist on disk.

	The film is rendered outside this repo, so the mp4 lands after the page does. The template
	renders the video when it is there, the poster frame alone when only that is, and a static
	endcard otherwise — dropping the file in is the entire swap.
	"""
	return {
		"video": asset_url(HERO_VIDEO, version),
		"poster": asset_url(HERO_POSTER, version),
	}


def asset_url(filename: str, version: str) -> str | None:
	# The directory is passed as separate parts on purpose: get_app_path scrubs hyphens into
	# underscores in every part unless one of them is exactly "public", so a single
	# "public/videos" would look for `hero_poster.jpg` and never find the poster.
	path = frappe.get_app_path("benchpress", *VIDEO_DIRECTORY, filename)
	if not os.path.exists(path):
		return None
	# Recutting the film keeps the filename, so only the token tells the CDN the bytes changed.
	return f"/assets/benchpress/videos/{filename}?v={version}"


def asset_version() -> str:
	"""Cache-busting token for the page's hand-linked favicons, CSS, JS and logo images.

	Those are referenced by plain filename instead of through Frappe's bundled-asset pipeline, so
	nothing tells Cloudflare's edge cache a file changed underneath a stable URL — the CDN can
	keep serving a pre-edit copy for its full `max-age`. Deriving the token from the newest mtime
	among the watched paths means editing any one of them changes every `?v=` on the page, forcing
	a fresh fetch past the CDN instead of waiting out the cache or a manual purge.
	"""
	mtimes = []
	for parts in CACHE_BUST_PATHS:
		path = frappe.get_app_path("benchpress", *parts)
		if os.path.isdir(path):
			mtimes += [os.path.getmtime(os.path.join(path, name)) for name in os.listdir(path)]
		elif os.path.exists(path):
			mtimes.append(os.path.getmtime(path))
	return str(int(max(mtimes))) if mtimes else "0"
