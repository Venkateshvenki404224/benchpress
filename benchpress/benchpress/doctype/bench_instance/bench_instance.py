# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import is_job_enqueued

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits.guard import instance_lease_cost, requires_admission
from benchpress.permissions import is_admin

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

	def validate(self):
		if self.is_new():
			# Not in `before_insert`: `runtime` is permlevel 1, and Frappe resets a permlevel field
			# to its new-doc value in between the two, discarding whatever was chosen there. That
			# value is the Select's empty first option, which is why it carries one.
			if not self.runtime:
				self.runtime = self._default_runtime()
			return
		if not self.has_value_changed("runtime"):
			return
		if not is_admin():
			frappe.throw(_("Only an administrator can change a bench's runtime."), frappe.PermissionError)
		if self.status != "Draft":
			frappe.throw(
				_(
					"'{0}' is already deployed. A container's runtime is fixed when it is created — "
					"delete this instance and deploy again to change it."
				).format(self.name)
			)

	def before_save(self):
		"""The lease fields belong to `lease._write`; never let a stale document write them back.

		A deploy job holds this document for minutes, and `save()` writes every field from that
		copy — including a deadline a renewal has since moved.
		"""
		if self.is_new():
			return
		from benchpress.credits import lease

		lease.refresh_into(self)

	def on_trash(self):
		"""Give the concurrency slot and the site name back.

		`api._delete_bench` deletes with `force=True`, which skips the link check, and
		`Bench Admission.bench` is `Data` - so nothing else would ever notice either orphan.

		The site name goes here rather than at the call site because a `Bench Site` row whose
		instance is gone can no longer drop its own database: only `api._delete_bench` does that,
		and it needs the instance. It runs the drop before this, while the rows are still here.
		"""
		from benchpress.credits import admission

		admission.release(self.name)
		for site in frappe.get_all("Bench Site", filters={"bench": self.name}, pluck="name"):
			frappe.delete_doc("Bench Site", site, force=True, ignore_permissions=True)

	def validate_higher_perm_levels(self):
		"""Refuse a runtime the caller may not set, where Frappe would silently drop it.

		The base method resets a permlevel field the caller cannot write back to its stored value
		and says nothing, so a tenant lowering their own isolation would read as success.
		"""
		requested = self.runtime
		super().validate_higher_perm_levels()
		if not self.is_new() and self.runtime != requested:
			frappe.throw(_("Only an administrator can change a bench's runtime."), frappe.PermissionError)

	def _default_runtime(self) -> str:
		return frappe.get_cached_doc("BenchPress Settings").default_bench_runtime or "runc"

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
	@requires_admission(cost=instance_lease_cost)
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
	@requires_admission(cost=instance_lease_cost)
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
	@requires_admission(cost=instance_lease_cost)
	def enqueue_start(self):
		from benchpress.credits import metering
		from benchpress.deploy_manager import enqueue_route_sync
		from benchpress.docker_manager import start_container

		if not self.container_id:
			frappe.throw(_("No container to start."))
		start_container(self.container_id)
		self.status = "Running"
		self.started_at = frappe.utils.now_datetime()
		# Buys a fresh window before the save writes `Running`. A start that left the old,
		# passed deadline on the row would be claimed by the next sweep and stopped again.
		metering.on_bench_running(self)
		self.save()
		frappe.db.commit()  # nosemgrep: intentional commit to persist status before response
		enqueue_route_sync(self.name)
		frappe.msgprint(_("Bench started."))
