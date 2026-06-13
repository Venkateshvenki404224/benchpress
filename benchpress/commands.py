# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import click
import frappe
from frappe.commands import pass_context
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils.bench_helper import CliCtxObj


@click.group("benchpress")
def benchpress():
	"""BenchPress operational commands."""


@benchpress.command("doctor")
@click.option("--site", help="Site to run the doctor against.")
@click.option(
	"--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON instead of the report."
)
@click.option("--strict", is_flag=True, default=False, help="Exit non-zero when any check fails (CI gate).")
@pass_context
def doctor(context: CliCtxObj, site: str | None = None, as_json: bool = False, strict: bool = False):
	"""Check host readiness for BenchPress and print a pass/warn/fail report."""
	from benchpress.doctor import run

	sites = [site] if site else context.sites
	if not sites:
		raise SiteNotSpecifiedError

	for site_name in sites:
		frappe.init(site_name)
		frappe.connect()
		try:
			run(as_json=as_json, strict=strict)
		finally:
			frappe.destroy()


commands = [benchpress]
