# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.installer import update_site_config
from frappe.model.document import Document
from frappe.utils import cstr

HOST_NAME_KEY = "host_name"


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
		claim_host_name(self.base_domain)

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


def claim_host_name(base_domain: str | None) -> None:
	"""`frappe.utils.get_url()` falls back to the site name, so every mailed link needs this key."""
	domain = cstr(base_domain).strip()
	if not domain or domain == "localhost":
		return
	url = f"https://{domain}"
	if frappe.conf.get(HOST_NAME_KEY) == url:
		return
	update_site_config(HOST_NAME_KEY, url)
	# The file as well as the live conf: `get_url` reads the copy loaded at request start.
	frappe.conf[HOST_NAME_KEY] = url
