# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Give every existing Lab the `Instance Size` it is closest to.

Labs written before sizes existed carry hand-typed `memory_limit` / `cpu_cores`, which is exactly
what `config.size_for_lab` falls back to — but only on an *exact* match, so a 512m lab would price
off the default rather than off the size it actually resembles. This resolves that once, at
migration time, so the lab form and the price agree from the first render.

The resources themselves are left alone. They are still what `docker_manager` passes to Docker, and
rewriting a running fleet's memory limits inside a patch is not what "choose a size" asked for; the
next save of the lab aligns them to the size that was chosen.
"""

import re

import frappe
from frappe.utils import cint, cstr, flt

SIZE_FIELDS = ["name", "memory_limit", "cpu_cores"]

# Enough to compare with. `docker_manager` is the only thing that has to parse these for real.
MEGABYTES_PER_UNIT = {"b": 1 / (1024 * 1024), "k": 1 / 1024, "m": 1, "g": 1024, "t": 1024 * 1024}
MEMORY_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([bkmgt])?b?\s*$")


def execute():
	sizes = frappe.get_all("Instance Size", fields=SIZE_FIELDS)
	if not sizes:
		return
	unsized = frappe.get_all(
		"Lab", filters={"instance_size": ("is", "not set")}, fields=["name", "memory_limit", "cpu_cores"]
	)
	for lab in unsized:
		frappe.db.set_value(
			"Lab", lab.name, "instance_size", _nearest(lab, sizes).name, update_modified=False
		)


def _nearest(lab, sizes):
	"""The closest size by memory, then by cores — memory is what a bench actually runs out of."""
	return min(sizes, key=lambda size: _distance(lab, size))


def _distance(lab, size) -> tuple:
	return (
		abs(_megabytes(size.memory_limit) - _megabytes(lab.memory_limit)),
		abs(cint(size.cpu_cores) - cint(lab.cpu_cores)),
	)


def _megabytes(memory_limit) -> float:
	"""`"2g"` → 2048. An unparseable value compares as zero rather than blowing up a migration."""
	match = MEMORY_PATTERN.match(cstr(memory_limit).lower())
	if not match:
		return 0.0
	return flt(match.group(1)) * MEGABYTES_PER_UNIT[match.group(2) or "m"]
