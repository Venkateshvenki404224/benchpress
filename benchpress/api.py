# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from benchpress import image_cache, lab_detail, lab_templates, labs
from benchpress.credits import account, metering, payments
from benchpress.credits.guard import (
	build_charge,
	cap_builds_per_day,
	cap_concurrent_instances,
	cap_devices,
	cap_sites_per_instance,
	payload_runway,
	requires_credits,
)
from benchpress.permissions import (
	get_bench_owner_filter,
	is_admin,
	require_admin,
	require_app_user,
	require_bench_access,
)


@frappe.whitelist()
def get_labs() -> list[dict]:
	require_app_user()
	return labs.get_labs()


@frappe.whitelist()
def get_lab(name: str) -> dict:
	require_app_user()
	return lab_detail.get_lab(name)


@frappe.whitelist()
def get_lab_form_options() -> dict:
	"""The Lab enum and defaults the New lab form builds itself from."""
	require_admin()
	return labs.get_lab_form_options()


@frappe.whitelist()
def get_lab_templates() -> list[dict]:
	require_app_user()
	return lab_templates.get_catalog()


@frappe.whitelist()
def create_lab_from_template(template: str, lab_id: str | None = None, title: str | None = None) -> dict:
	require_admin()
	name = lab_templates.create_lab_from_template(template, lab_id, title)
	return {"name": name, "status": "Draft"}


@frappe.whitelist()
@requires_credits(cost=build_charge, caps=(cap_builds_per_day,))
def build_lab_image(lab_name: str) -> dict:
	require_admin()
	frappe.enqueue(
		"benchpress.deploy_manager.build_lab",
		lab_name=lab_name,
		queue="long",
		timeout=3600,
	)
	return {"name": lab_name, "status": "Building"}


@frappe.whitelist()
def prewarm_catalog() -> dict:
	"""Build the shared image for every catalog template that has none yet.

	Returns as soon as the work is queued: the builds themselves take minutes each and run on
	`queue-long`, the only worker that can reach the Docker socket.
	"""
	require_admin()
	return image_cache.enqueue_prewarm_catalog()


@frappe.whitelist()
def get_benches() -> list[dict]:
	require_app_user()
	benches = frappe.get_list(
		"Bench Instance",
		filters=get_bench_owner_filter(),
		fields=[
			"name",
			"bench_name",
			"lab",
			"frappe_version",
			"domain",
			"status",
			"container_id",
			"container_ip",
			"wg_ip",
			"cpu_usage",
			"memory_usage",
			"container_health",
			"last_health_check",
			"started_at",
			"ssh_username",
			"code_server_url",
		],
		order_by="creation desc",
	)

	for bench in benches:
		bench["app_count"] = frappe.db.count("Bench App", {"parent": bench["name"]})
		bench["site_count"] = frappe.db.count("Bench Site", {"bench": bench["name"]})

	return benches


@frappe.whitelist()
@requires_credits(cost=payload_runway, caps=(cap_concurrent_instances,))
def create_bench(data: str) -> dict:
	require_app_user()
	from benchpress.benchpress.doctype.bench_instance import get_instance_id

	data = frappe.parse_json(data)

	lab_name = data.get("lab")
	if not lab_name:
		frappe.throw(_("Lab is required to create a bench."))

	lab = frappe.get_cached_doc("Lab", lab_name)

	instance_id = get_instance_id(frappe.session.user, lab_name)
	if frappe.db.exists("Bench Instance", instance_id):
		doc = frappe.get_doc("Bench Instance", instance_id)
		doc.status = "Deploying"
		doc.save()
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"bench_name": data.get("bench_name"),
				"lab": lab_name,
				"frappe_version": lab.frappe_version,
				"domain": data.get("domain"),
				"status": "Draft",
			}
		)

		for app in lab.apps:
			doc.append(
				"apps",
				{
					"app_name": app.app_name,
					"app_label": app.app_label,
					"git_url": app.git_url,
					"branch": app.branch,
				},
			)

		doc.insert()

	frappe.enqueue(
		"benchpress.deploy_manager.deploy_bench",
		bench_name=doc.name,
		queue="long",
		timeout=3600,
		job_id=f"deploy_bench:{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)

	return {"name": doc.name, "status": "Deploying"}


@frappe.whitelist()
def bench_action(bench_name: str, action: str) -> dict:
	from benchpress.docker_manager import (
		remove_container,
		restart_container,
		start_container,
		stop_container,
	)

	require_bench_access(bench_name)
	if action == "delete" and not is_admin():
		frappe.throw(_("Only admins can delete bench instances."), frappe.PermissionError)

	bench = frappe.get_doc("Bench Instance", bench_name)

	if action == "start":
		start_container(bench.container_id)
		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		metering.on_bench_running(bench)
	elif action == "stop":
		stop_container(bench.container_id)
		bench.status = "Stopped"
		metering.on_bench_stopped(bench)
	elif action == "restart":
		restart_container(bench.container_id)
		bench.status = "Running"
		# A restart does not interrupt the session — the instance was billable before and is
		# billable after — so this only starts a meter that was not already running.
		metering.on_bench_running(bench)
	elif action == "delete":
		metering.on_bench_stopped(bench)
		if bench.database_server:
			from benchpress.mariadb_manager import drop_site_database

			sites = frappe.get_list(
				"Bench Site", filters={"bench": bench.name}, fields=["site_name", "full_domain"]
			)
			for s in sites:
				try:
					drop_site_database(bench.database_server, s.full_domain or s.site_name)
				except Exception:
					frappe.log_error(
						title=f"Failed to drop DB for {s.site_name}", message=frappe.get_traceback()
					)

		if bench.container_id:
			try:
				stop_container(bench.container_id)
			except Exception:
				pass  # best-effort
			remove_container(bench.container_id)

		from benchpress.deploy_manager import remove_bench_volume
		from benchpress.vpn_adapter import remove_bench_peer

		remove_bench_volume(bench.bench_name)
		remove_bench_peer(bench)

		frappe.delete_doc("Bench Instance", bench_name, force=True)
		frappe.db.commit()
		return {"status": "deleted"}
	else:
		frappe.throw(_("Invalid action: {0}").format(action))

	bench.save()
	frappe.db.commit()
	return {"name": bench.name, "status": bench.status}


@frappe.whitelist()
def get_deploy_logs(bench_name: str) -> list[dict]:
	require_bench_access(bench_name)
	return frappe.get_list(
		"Deploy Log",
		filters={"bench": bench_name},
		fields=["name", "message", "log_type", "timestamp"],
		order_by="timestamp desc",
		limit_page_length=20,
	)


@frappe.whitelist()
def get_build_history() -> dict:
	"""Image-build runs. Scoped in `run_history`: Build Log has no query condition."""
	from benchpress.run_history import get_build_history as _get_build_history

	return _get_build_history()


@frappe.whitelist()
def get_deploy_history() -> dict:
	from benchpress.run_history import get_deploy_history as _get_deploy_history

	return _get_deploy_history()


@frappe.whitelist()
@requires_credits(caps=(cap_devices,))
def add_device(device_name: str, device_type: str, public_key: str | None = None) -> dict:
	require_app_user()
	from benchpress.vpn_adapter import register_device

	return register_device(device_name, device_type, public_key or None)


@frappe.whitelist()
def remove_device(device_name: str) -> dict:
	require_app_user()
	from benchpress.vpn_adapter import unregister_device

	unregister_device(device_name)
	return {"status": "removed"}


@frappe.whitelist()
def list_devices() -> list[dict]:
	require_app_user()
	from benchpress.vpn_adapter import list_devices as _list

	return _list()


@frappe.whitelist()
def get_device_types() -> list[str]:
	"""The device types register_device accepts, so no screen hand-types them."""
	require_app_user()
	from benchpress.vpn_adapter import DEVICE_TYPES

	return DEVICE_TYPES


@frappe.whitelist()
def get_device_wg_config(device_name: str) -> str:
	require_app_user()
	from benchpress.vpn_adapter import get_device_config

	return get_device_config(device_name)


@frappe.whitelist()
@requires_credits(caps=(cap_sites_per_instance,))
def create_site(data: str) -> dict:
	require_app_user()
	data = frappe.parse_json(data)

	bench_name = data.get("bench")
	if bench_name:
		require_bench_access(bench_name)

	doc = frappe.get_doc(
		{
			"doctype": "Bench Site",
			"site_name": data.get("site_name"),
			"bench": bench_name,
		}
	)

	for app in data.get("apps", []):
		doc.append(
			"apps_installed",
			{
				"app_name": app.get("name"),
				"app_label": app.get("label", app.get("name")),
			},
		)

	doc.insert()

	frappe.enqueue(
		"benchpress.api._create_site_on_bench",
		site_doc_name=doc.name,
		queue="long",
		timeout=600,
		enqueue_after_commit=True,
	)

	return {"name": doc.name, "status": "Creating"}


def _create_site_on_bench(site_doc_name: str) -> None:
	from benchpress.deploy_manager import create_site_in_container

	site = frappe.get_doc("Bench Site", site_doc_name)
	bench = frappe.get_doc("Bench Instance", site.bench)
	db_server = frappe.get_doc("Database Server", bench.database_server)

	try:
		admin_password = bench.get_password("admin_password")
		site.admin_password = admin_password
		site_name = site.full_domain or site.site_name
		apps_csv = ",".join(a.app_name for a in site.apps_installed if a.app_name.lower() != "frappe")

		exit_code, output = create_site_in_container(
			bench.container_id, db_server, site_name, admin_password, apps_csv
		)

		if exit_code != 0:
			site.status = "Error"
			site.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.log_error(title=f"Site creation failed: {site_name}", message=output[:500])
			return

		site.status = "Active"
		site.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception:
		site.reload()
		site.status = "Error"
		site.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.log_error(
			title=f"Site creation failed: {site_doc_name}",
			message=frappe.get_traceback(),
		)


@frappe.whitelist()
def get_user_context() -> dict:
	"""Who the caller is, and whether credits exist at all.

	The switch is exposed here rather than through an endpoint of its own so the SPA learns it in
	the call it already makes on boot, and every credit surface hides behind the same gate the API
	enforces.
	"""
	return {
		"is_admin": is_admin(),
		"user": frappe.session.user,
		"roles": frappe.get_roles(frappe.session.user),
		"credits": account.summary(frappe.session.user),
	}


@frappe.whitelist()
def get_credit_summary() -> dict:
	"""The balance chip's refresh: one indexed read, no ledger scan."""
	require_app_user()
	return account.summary(frappe.session.user)


@frappe.whitelist()
def get_credit_statement(limit_start: int = 0, limit_page_length: int = 20) -> dict:
	"""One page of the caller's own ledger. Never another user's — the filter is the session."""
	require_app_user()
	return account.statement(frappe.session.user, limit_start, limit_page_length)


@frappe.whitelist()
def get_purchase_options() -> dict:
	"""What is for sale, and whether a gateway exists to sell it."""
	require_app_user()
	return payments.purchase_options()


@frappe.whitelist()
def buy_credits(pack: str) -> dict:
	"""Open a Razorpay order for a credit pack. The price is the pack's, never the caller's."""
	require_app_user()
	return payments.buy_credits(pack)


@frappe.whitelist()
def buy_always_on_pass(bench_name: str) -> dict:
	"""Open a Razorpay order for a pass on one instance the caller is allowed to see."""
	require_bench_access(bench_name)
	return payments.buy_always_on_pass(bench_name)


@frappe.whitelist()
def get_code_server_credentials(bench_name: str) -> dict:
	require_bench_access(bench_name)
	bench = frappe.get_cached_doc("Bench Instance", bench_name)
	if bench.status != "Running":
		frappe.throw(_("Bench must be running to access code-server"))
	if not bench.code_server_url:
		frappe.throw(_("Code-server is not enabled for this lab"))
	from frappe.utils.password import get_decrypted_password

	password = get_decrypted_password("Bench Instance", bench_name, "code_server_password")
	return {"url": bench.code_server_url, "password": password}


@frappe.whitelist()
def get_bench_credentials(bench_name: str) -> dict:
	require_bench_access(bench_name)
	from frappe.utils.password import get_decrypted_password

	credentials = {}
	for field in ("ssh_password", "admin_password", "code_server_password"):
		try:
			credentials[field] = get_decrypted_password("Bench Instance", bench_name, field)
		except frappe.exceptions.ValidationError:
			credentials[field] = None
	return credentials


@frappe.whitelist()
def restart_code_server(bench_name: str) -> dict:
	require_bench_access(bench_name)
	bench = frappe.get_cached_doc("Bench Instance", bench_name)
	if bench.status != "Running" or not bench.container_id:
		frappe.throw(_("Bench must be running"))
	from benchpress.docker_manager import exec_in_container

	exit_code, output = exec_in_container(
		bench.container_id,
		"bash /opt/benchpress/scripts/restart.sh",
		user="root",
	)
	if exit_code != 0:
		frappe.throw(_("restart failed: {0}").format(output))
	return {"ok": True}


@frappe.whitelist()
def get_overview() -> dict:
	require_app_user()
	from benchpress.overview import get_overview as _get_overview

	return _get_overview()


@frappe.whitelist()
def get_vpn_status() -> dict:
	require_app_user()
	from benchpress.vpn_adapter import get_device_vpn_status

	return get_device_vpn_status()


@frappe.whitelist()
def run_connection_test() -> list[dict]:
	"""The user-facing tunnel test: their own peer, never the shared infrastructure."""
	require_app_user()
	from benchpress.connection_test import run_connection_test as _run_connection_test

	return _run_connection_test()


@frappe.whitelist()
def run_diagnostics() -> list[dict]:
	require_admin()
	from benchpress.diagnostics import run_diagnostics as _run_diagnostics

	return _run_diagnostics()
