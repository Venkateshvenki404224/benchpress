# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from benchpress.permissions import (
	get_bench_owner_filter,
	is_admin,
	require_admin,
	require_bench_access,
)


@frappe.whitelist()
def get_labs() -> list[dict]:
	labs = frappe.get_all(
		"Lab",
		fields=[
			"name",
			"lab_id",
			"title",
			"description",
			"frappe_version",
			"status",
			"image_tag",
			"memory_limit",
			"cpu_cores",
		],
		order_by="creation desc",
	)
	for lab in labs:
		apps = frappe.get_all(
			"Lab App",
			filters={"parent": lab["name"]},
			fields=["app_name"],
			limit_page_length=50,
		)
		lab["app_names"] = [a["app_name"] for a in apps]
		lab["app_count"] = len(apps)
		lab["bench_count"] = frappe.db.count("Bench Instance", {"lab": lab["name"]})
	return labs


@frappe.whitelist()
def get_lab(name: str) -> dict:
	lab = frappe.get_cached_doc("Lab", name)
	return {
		"name": lab.name,
		"lab_id": lab.lab_id,
		"title": lab.title,
		"description": lab.description,
		"frappe_version": lab.frappe_version,
		"status": lab.status,
		"image_tag": lab.image_tag,
		"memory_limit": lab.memory_limit,
		"cpu_cores": lab.cpu_cores,
		"apps": [
			{"app_name": a.app_name, "app_label": a.app_label, "git_url": a.git_url, "branch": a.branch}
			for a in lab.apps
		],
	}


@frappe.whitelist()
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
def get_benches() -> list[dict]:
	benches = frappe.get_all(
		"Bench Instance",
		filters=get_bench_owner_filter(),
		fields=[
			"name",
			"bench_name",
			"lab",
			"frappe_version",
			"domain",
			"public_url",
			"is_public",
			"public_username",
			"status",
			"container_id",
			"container_ip",
			"wg_ip",
			"cpu_usage",
			"memory_usage",
			"started_at",
			"ssh_username",
			"code_server_url",
		],
		order_by="creation desc",
	)

	from frappe.utils.password import get_decrypted_password

	for bench in benches:
		bench["app_count"] = frappe.db.count("Bench App", {"parent": bench["name"]})
		bench["site_count"] = frappe.db.count("Bench Site", {"bench": bench["name"]})
		for field in ("ssh_password", "admin_password", "code_server_password", "public_password"):
			try:
				bench[field] = get_decrypted_password("Bench Instance", bench["name"], field)
			except frappe.exceptions.ValidationError:
				bench[field] = None

	return benches


@frappe.whitelist()
def create_bench(data: str) -> dict:
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
		doc.save(ignore_permissions=True)
		frappe.db.commit()
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
		frappe.db.commit()

	frappe.enqueue(
		"benchpress.deploy_manager.deploy_bench",
		bench_name=doc.name,
		queue="long",
		timeout=3600,
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
	elif action == "stop":
		stop_container(bench.container_id)
		bench.status = "Stopped"
	elif action == "restart":
		restart_container(bench.container_id)
		bench.status = "Running"
	elif action == "delete":
		if bench.database_server:
			from benchpress.mariadb_manager import drop_site_database

			sites = frappe.get_all(
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

		remove_bench_volume(bench.bench_name)

		frappe.delete_doc("Bench Instance", bench_name, force=True)
		frappe.db.commit()
		return {"status": "deleted"}
	else:
		frappe.throw(_("Invalid action: {0}").format(action))

	bench.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": bench.name, "status": bench.status}


@frappe.whitelist()
def set_bench_visibility(bench_name: str, is_public: bool | str | int, username: str | None = None) -> dict:
	require_bench_access(bench_name)

	if isinstance(is_public, str):
		is_public = is_public.strip().lower() in ("1", "true", "yes", "on")
	is_public = bool(is_public)

	frappe.enqueue(
		"benchpress.deploy_manager.apply_public_visibility",
		bench_name=bench_name,
		is_public=is_public,
		username=username or None,
		queue="long",
		timeout=1800,
	)
	return {"status": "updating"}


@frappe.whitelist()
def get_deploy_logs(bench_name: str) -> list[dict]:
	require_bench_access(bench_name)
	return frappe.get_all(
		"Deploy Log",
		filters={"bench": bench_name},
		fields=["name", "message", "log_type", "timestamp"],
		order_by="timestamp desc",
		limit_page_length=20,
	)


@frappe.whitelist()
def add_device(device_name: str, device_type: str, public_key: str | None = None) -> dict:
	from benchpress.device_manager import register_device

	return register_device(device_name, device_type, public_key or None)


@frappe.whitelist()
def remove_device(device_name: str) -> dict:
	from benchpress.device_manager import unregister_device

	unregister_device(device_name)
	return {"status": "removed"}


@frappe.whitelist()
def list_devices() -> list[dict]:
	from benchpress.device_manager import list_devices as _list

	return _list()


@frappe.whitelist()
def get_device_wg_config(device_name: str) -> str:
	from benchpress.device_manager import get_device_config

	return get_device_config(device_name)


@frappe.whitelist()
def create_site(data: str) -> dict:
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
	frappe.db.commit()  # nosemgrep

	frappe.enqueue(
		"benchpress.api._create_site_on_bench",
		site_doc_name=doc.name,
		queue="long",
		timeout=600,
	)

	return {"name": doc.name, "status": "Creating"}


def _create_site_on_bench(site_doc_name: str) -> None:
	from benchpress.deploy_manager import create_site_in_container

	site = frappe.get_doc("Bench Site", site_doc_name)
	bench = frappe.get_doc("Bench Instance", site.bench)
	db_server = frappe.get_doc("Database Server", bench.database_server)
	lab = frappe.get_cached_doc("Lab", bench.lab)

	try:
		admin_password = bench.get_password("admin_password")
		site.admin_password = admin_password
		site_name = site.full_domain or site.site_name
		apps_csv = ",".join(a.app_name for a in site.apps_installed if a.app_name.lower() != "frappe")

		exit_code, output = create_site_in_container(
			bench.container_id, db_server, lab, site_name, admin_password, apps_csv
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
	return {
		"is_admin": is_admin(),
		"user": frappe.session.user,
		"roles": frappe.get_roles(frappe.session.user),
	}


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
