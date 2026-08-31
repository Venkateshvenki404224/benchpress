# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""`/landing`: the marketing page under a name the home-page resolver cannot rewrite."""

from benchpress.www import index

no_cache = 1

# `/` is the canonical route; keep the alias out of sitemap.xml.
sitemap = 0


def get_context(context):
	return index.get_context(context)
