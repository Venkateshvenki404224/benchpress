# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import is_job_enqueued

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits.guard import cap_concurrent_instances, instance_runway, requires_credits

DEPLOY_JOB_TIMEOUT = 7200


class BenchInstance(Document):
	def before_insert(self):
		instance_id = get_instance_id(frappe.session.user, self.lab)
		self.bench_name = instance_id
		if not self.site_name:
			base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
			suffix = base_domain if base_domain and base_domain != "localhost" else "localhost"
			self.site_name = f"{instance_id}.{suffix}"
		self.ssh_username = self._derive_username()

	def autoname(self):
		self.name = self.bench_name

	def _derive_username(self, email: str | None = None):
		"""Derive a valid Linux username from the Frappe user email.

		Takes the part before @, lowercases, strips invalid chars, caps at 32 chars.
		e.g., John.Doe@example.com -> johndoe
		"""
		email = email or frappe.session.user
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

	@frappe.whitelist()
	@requires_credits(cost=instance_runway, caps=(cap_concurrent_instances,))
	def enqueue_deploy(self):
		if is_job_enqueued(self._deploy_job_id()):
			frappe.msgprint(_("A deploy is already in progress for this bench."))
			return
		frappe.enqueue(
			"benchpress.deploy_manager.deploy_bench",
			bench_name=self.name,
			queue="long",
			timeout=DEPLOY_JOB_TIMEOUT,
			job_id=self._deploy_job_id(),
			deduplicate=True,
			enqueue_after_commit=True,
		)
		frappe.msgprint(_("Deploy started. Watch the Deploy Log for progress."))

	@frappe.whitelist()
	def enqueue_stop(self):
		from benchpress.deploy_manager import stop_bench

		stop_bench(self.name)
		frappe.msgprint(_("Bench stopped."))

	@frappe.whitelist()
	@requires_credits(cost=instance_runway, caps=(cap_concurrent_instances,))
	def enqueue_redeploy(self):
		if is_job_enqueued(self._deploy_job_id()):
			frappe.msgprint(_("A deploy is already in progress for this bench."))
			return
		frappe.enqueue(
			"benchpress.deploy_manager.redeploy_bench",
			bench_name=self.name,
			queue="long",
			timeout=DEPLOY_JOB_TIMEOUT,
			job_id=self._deploy_job_id(),
			deduplicate=True,
			enqueue_after_commit=True,
		)
		frappe.msgprint(_("Redeploy started. Watch the Deploy Log for progress."))

	def _deploy_job_id(self) -> str:
		return f"deploy_bench:{self.name}"

	@frappe.whitelist()
	@requires_credits(cost=instance_runway, caps=(cap_concurrent_instances,))
	def enqueue_start(self):
		from benchpress.credits import metering
		from benchpress.docker_manager import start_container

		if not self.container_id:
			frappe.throw(_("No container to start."))
		start_container(self.container_id)
		self.status = "Running"
		self.started_at = frappe.utils.now_datetime()
		metering.on_bench_running(self)
		self.save()
		frappe.db.commit()  # nosemgrep: intentional commit to persist status before response
		frappe.msgprint(_("Bench started."))
