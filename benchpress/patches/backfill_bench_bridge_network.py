# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Name the Docker network every existing bench is already attached to.

Every container that predates the bridge family sits on `benchpress`. A row stamped
`benchpress-0` would send its own IP read-back and its WireGuard gateway to a network
its container is not on, and the deploy that follows would read an empty address and
time out. Nothing is migrated: the legacy network drains as its benches are destroyed.
"""

import frappe

from benchpress.docker_manager import LEGACY_NETWORK


def execute():
	for name in frappe.get_all(
		"Bench Instance", filters={"bridge_network": ("in", ["", None])}, pluck="name"
	):
		frappe.db.set_value(
			"Bench Instance", name, "bridge_network", LEGACY_NETWORK, update_modified=False
		)
