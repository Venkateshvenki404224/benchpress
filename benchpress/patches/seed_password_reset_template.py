# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Plant the seventh `Email Template` row on a site the first seeding pass predates."""

from benchpress.public_site.seed import seed_public_site


def execute():
	seed_public_site()
