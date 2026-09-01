# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os

import frappe

from benchpress.benchpress.site_content import (
	about_content,
	chrome_content,
	landing_content,
	preview_tags,
)
from benchpress.credits.config import credits_enabled, waitlist_open
from benchpress.public_site import require_public_site

REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"
DEFAULT_TITLE = "BenchPress — a Frappe environment in one click"

VIDEO_DIRECTORY = ("public", "videos")
HERO_VIDEO = "hero.mp4"
HERO_POSTER = "hero-poster.jpg"

no_cache = 1

NO_COMMERCE = {
	"credits_enabled": False,
	"waitlist_open": False,
}


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.body_class = "bp-body"
	context.mode_default = "dark"

	context.update(landing_content())
	context.update(chrome_content())
	context.update(commerce_context() if credits_enabled() else dict(NO_COMMERCE))

	# The numbers in the About teaser live with the page they came from.
	context.about_stats = about_content()["settings"].stats

	context.title = context.meta_title or DEFAULT_TITLE
	context.metatags = preview_tags(context.title, context.meta_description, context.og_image)
	context.repo_url = REPO_URL
	context.hero_media = hero_media(context.asset_version)
	return context


def commerce_context() -> dict:
	return {"credits_enabled": True, "waitlist_open": waitlist_open()}


def hero_media(version: str) -> dict:
	return {
		"video": asset_url(HERO_VIDEO, version),
		"poster": asset_url(HERO_POSTER, version),
	}


def asset_url(filename: str, version: str) -> str | None:
	# get_app_path scrubs hyphens to underscores in every part that is not exactly "public".
	path = frappe.get_app_path("benchpress", *VIDEO_DIRECTORY, filename)
	if not os.path.exists(path):
		return None
	return f"/assets/benchpress/videos/{filename}?v={version}"
