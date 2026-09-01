# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os

import frappe

from benchpress.benchpress.site_content import about_content, chrome_content, preview_tags
from benchpress.public_site import require_public_site

DEFAULT_TITLE = "About BenchPress"

CACHE_BUST_PATHS = (
	("public", "css", "brand.css"),
	("public", "css", "pages.css"),
	("public", "js", "site.js"),
	("public", "images", "logo"),
	("public", "manifest.json"),
)

no_cache = 1


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.full_width = 1
	context.body_class = "bp-body"
	context.mode_default = "dark"

	context.update(about_content())
	context.update(chrome_content(is_landing=False))

	context.cta_url = context.settings.cta_url or context.signup_route

	context.meta_title = context.meta_title or DEFAULT_TITLE
	context.title = context.meta_title
	context.metatags = preview_tags(context.title, context.meta_description, context.og_image)
	context.asset_version = asset_version()
	return context


def asset_version() -> str:
	"""Newest mtime among the assets this page links by plain filename."""
	mtimes = []
	for parts in CACHE_BUST_PATHS:
		path = frappe.get_app_path("benchpress", *parts)
		if os.path.isdir(path):
			mtimes += [os.path.getmtime(os.path.join(path, name)) for name in os.listdir(path)]
		elif os.path.exists(path):
			mtimes.append(os.path.getmtime(path))
	return str(int(max(mtimes))) if mtimes else "0"
