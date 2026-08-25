# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Turn every live Always On Pass into a lease, then retire the doctype.

A pass was prepaid time that exempted an instance from the meter and the run limit. A lease is
prepaid time too, so the conversion is a deadline rather than a refund. It runs before the
doctype goes because the pass rows are the only record of what was bought.

The deadline is built by adding the remaining seconds to `now`, never by converting a stored
date to an epoch second. `valid_until` is a naive site-local Date and this deployment's database
clock is 5h30m from the app's — the subtraction of two site-local datetimes carries no timezone,
`now_ts` supplies the anchor, and nobody who paid loses time to a refactor.
"""

import frappe
from frappe.utils import add_days, cint, getdate, now_datetime, time_diff_in_seconds, today

from benchpress.credits import lease

PASS = "Always On Pass"
BENCH = "Bench Instance"


def execute() -> list[str]:
	converted = convert_live_passes()
	_retire_doctype()
	return converted


def convert_live_passes() -> list[str]:
	"""Give every unexpired pass's instance a lease that outlasts it. Returns what moved.

	Guarded on the DocType rather than the table, because the two are not retired together: the
	record goes first and the table is dropped after it, so between them there is a moment when
	reading the rows would ask for meta that no longer exists.
	"""
	if not frappe.db.exists("DocType", PASS):
		return []
	now = lease.now_ts()
	converted = []
	for row in _live_passes():
		bench = frappe.db.get_value(BENCH, row.bench_instance, lease.LEASE_FIELDS, as_dict=True)
		if not bench:
			continue
		deadline = lease_deadline(row.valid_until, now)
		if bench.lease_state == lease.ACTIVE and cint(bench.expires_at_ts) >= deadline:
			continue
		bench.name = row.bench_instance
		lease.arm_at(bench, deadline)
		converted.append(bench.name)
	return converted


def lease_deadline(valid_until, now: int) -> int:
	"""The epoch second a pass valid through `valid_until` is worth, and never earlier than now.

	End of that day rather than the start of it: a pass sold "until the 14th" was good for all
	of the 14th, and that is what the holder bought.
	"""
	remaining = time_diff_in_seconds(add_days(getdate(valid_until), 1), now_datetime())
	return now + max(int(remaining), 0)


def _live_passes() -> list[dict]:
	return frappe.get_all(
		PASS, filters={"valid_until": (">=", today())}, fields=["bench_instance", "valid_until"]
	)


def _retire_doctype() -> None:
	"""Delete the DocType and then its table. Idempotent, and safe with no rows.

	The table is dropped by hand because `delete_doc` does not: Frappe leaves `tab<name>` behind
	on purpose, so a DocType deleted by accident loses no data. Here it is not an accident, and a
	table nothing declares is the second system this phase exists to remove.
	"""
	if frappe.db.exists("DocType", PASS):
		frappe.delete_doc("DocType", PASS, force=True, ignore_permissions=True)
	frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{PASS}`")
