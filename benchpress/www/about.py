# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress.benchpress.site_content import about_content, canonical_url, chrome_content, preview_tags
from benchpress.public_site import require_public_site

DEFAULT_TITLE = "About BenchPress"

no_cache = 1
sitemap = 1


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.bp_canonical = canonical_url("/about")
	context.body_class = "bp-body"
	context.mode_default = "dark"

	context.update(about_content())
	context.update(chrome_content())

	context.cta_url = context.settings.cta_url or context.signup_route

	context.meta_title = context.meta_title or DEFAULT_TITLE
	context.title = context.meta_title
	context.metatags = preview_tags(context.title, context.meta_description, context.og_image)
	return context
