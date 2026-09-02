# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Every `/vs/<slug>` page renders one seed through `templates/comparison_page.html`."""

from benchpress import structured_data
from benchpress.benchpress.site_content import REPO_URL, canonical_url, chrome_content, preview_tags
from benchpress.public_site import require_public_site


def render(context, route: str, seed: dict):
	require_public_site()

	context.no_cache = 1
	context.bp_canonical = canonical_url(route)
	context.body_class = "bp-body"
	context.mode_default = "dark"

	context.settings = seed
	context.update(chrome_content())

	context.title = seed["meta_title"]
	context.metatags = preview_tags(context.title, seed["meta_description"])
	context.bp_schema = structured_data.comparison(
		route, seed["meta_title"], seed["meta_description"], seed["faq_items"]
	)
	context.repo_url = REPO_URL
	return context
