# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BenchPressSettings(Document):
	def on_update(self):
		"""Re-anchor the wildcard when the bench zone changes.

		Enqueued, not called: this controller runs in `backend`, which does not mount the
		Traefik route directory. A direct write would land in that container's own
		filesystem and Traefik would never see it — silently, with every check green.
		`queue-long` is the only worker that consumes `long` and the only one with the mount.

		The guard keeps an unrelated settings save — a toggle, a timeout — from queueing a
		directory sweep.
		"""
		if not self.has_value_changed("base_domain"):
			return

		frappe.enqueue(
			"benchpress.reconcile.run",
			queue="long",
			job_id="reconcile_instance_routes",
			deduplicate=True,
			# The job re-reads `base_domain` from the database, so it must not start before
			# the new value is committed. Same mistake `6e25962` fixed for deploys.
			enqueue_after_commit=True,
		)
