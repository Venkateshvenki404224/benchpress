# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Stop existing rows claiming a health verdict their container cannot produce, then write the defaults.

A container's healthcheck is fixed when it is created, so every bench that already exists has none
and gains one only at its next redeploy. Until then Docker has no verdict about it and
`get_container_health` answers from run state, which is the honest answer and the one stamped here
— notably over the `Healthy` that every stopped bench still reads, left by the last poll that saw
it running.

A Single stores only the fields somebody has written, so the defaults in the DocType JSON reach a
fresh install and never a site that already had the Single: there the switch would read as off and
every duration as zero. They are written here instead, read from the DocType so this patch holds no
second copy of any number.
"""

import frappe

from benchpress.docker_manager import get_container_health

SETTINGS = "BenchPress Settings"
FIELDS = (
	"enable_bench_healthcheck",
	"bench_health_interval_seconds",
	"bench_health_timeout_seconds",
	"bench_health_retries",
	"bench_health_start_period_seconds",
	"stats_poll_max_benches",
)


def execute():
	for bench in frappe.get_all(
		"Bench Instance", filters={"container_id": ("is", "set")}, fields=["name", "container_id"]
	):
		frappe.db.set_value(
			"Bench Instance",
			bench.name,
			"container_health",
			get_container_health(bench.container_id),
			update_modified=False,
		)

	stored = frappe.db.get_singles_dict(SETTINGS)
	meta = frappe.get_meta(SETTINGS)
	for field in FIELDS:
		if field not in stored:
			frappe.db.set_single_value(SETTINGS, field, meta.get_field(field).default)
