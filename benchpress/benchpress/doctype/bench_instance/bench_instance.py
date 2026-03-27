# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document

from benchpress.benchpress.doctype.bench_instance import get_instance_id


class BenchInstance(Document):
	def before_insert(self):
		instance_id = get_instance_id(frappe.session.user, self.lab)
		self.bench_name = instance_id
		self.site_name = f"{instance_id}.localhost"
		self.ssh_username = self._derive_username()

	def autoname(self):
		self.name = self.bench_name

	def _derive_username(self):
		"""Derive a valid Linux username from the Frappe user email.

		Takes the part before @, lowercases, strips invalid chars, caps at 32 chars.
		e.g., John.Doe@example.com -> johndoe
		"""
		email = frappe.session.user
		username = email.split("@")[0].lower()
		# Keep only valid Linux username characters
		username = re.sub(r"[^a-z0-9_.-]", "", username)
		# Must start with a letter or digit
		username = re.sub(r"^[^a-z0-9]+", "", username)
		username = username[:32]
		# If empty or purely numeric, prefix with 'user'
		if not username or username.isdigit():
			username = "user" + username
		return username

	def on_trash(self):
		if self.wg_public_key:
			try:
				from benchpress.wg_manager import remove_peer_from_server

				remove_peer_from_server(self.wg_public_key)
			except Exception:
				frappe.log_error(title=f"WG cleanup failed: {self.name}")

	@frappe.whitelist()
	def enqueue_deploy(self):
		frappe.enqueue(
			"benchpress.deploy_manager.deploy_bench",
			bench_name=self.name,
			queue="long",
			timeout=1800,
		)
		frappe.msgprint("Deploy started. Watch the Deploy Log for progress.")

	@frappe.whitelist()
	def enqueue_stop(self):
		from benchpress.deploy_manager import stop_bench

		stop_bench(self.name)
		frappe.msgprint("Bench stopped.")

	@frappe.whitelist()
	def enqueue_redeploy(self):
		frappe.enqueue(
			"benchpress.deploy_manager.redeploy_bench",
			bench_name=self.name,
			queue="long",
			timeout=1800,
		)
		frappe.msgprint("Redeploy started. Watch the Deploy Log for progress.")

	@frappe.whitelist()
	def enqueue_start(self):
		from benchpress.docker_manager import start_container

		if not self.container_id:
			frappe.throw("No container to start.")
		start_container(self.container_id)
		self.status = "Running"
		self.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: intentional commit to persist status before response
		frappe.msgprint("Bench started.")
