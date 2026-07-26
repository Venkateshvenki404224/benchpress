# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress.vpn_access import grant_vpn_access


def execute():
	"""Backfill the VPN permissions the desk workspace assumes `BenchPress Admin` holds."""
	grant_vpn_access()
