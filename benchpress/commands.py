# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import click


@click.group("benchpress")
def benchpress():
	"""BenchPress CLI commands."""


@benchpress.command("quickstart")
@click.option("--site", required=True, help="Site to provision the bench against.")
def quickstart(site: str):
	"""Deploy a ready-to-use ERPNext bench in one command (TB1 walking skeleton)."""
	import frappe

	from benchpress.quickstart import run_quickstart

	frappe.init(site=site)
	frappe.connect()
	try:
		run_quickstart()
	finally:
		frappe.destroy()


commands = [benchpress]
