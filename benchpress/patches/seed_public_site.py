# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Give an existing site the public-page copy and mail templates a fresh install gets."""

from benchpress.public_site.seed import seed_public_site


def execute():
	seed_public_site()
