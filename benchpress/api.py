# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def has_app_permission() -> bool:
	return "System Manager" in frappe.get_roles(frappe.session.user)


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
	"""Trigger lab image build as a background job."""
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
			"started_at",
			"ssh_username",
		],
		order_by="creation desc",
	)

	for bench in benches:
		bench["app_count"] = frappe.db.count("Bench App", {"parent": bench["name"]})
		bench["site_count"] = frappe.db.count("Bench Site", {"bench": bench["name"]})
		try:
			bench["ssh_password"] = frappe.utils.password.get_decrypted_password(
				"Bench Instance", bench["name"], "ssh_password"
			)
		except frappe.exceptions.ValidationError:
			bench["ssh_password"] = None

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

		frappe.enqueue(
			"benchpress.deploy_manager.deploy_bench",
			bench_name=doc.name,
			queue="long",
			timeout=3600,
		)
		return {"name": doc.name, "status": "Deploying"}

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
		if bench.container_id:
			try:
				stop_container(bench.container_id)
			except Exception:
				pass
			remove_container(bench.container_id)
		from benchpress.docker_manager import get_client

		client = get_client()
		for suffix in ("data", "mariadb"):
			try:
				client.volumes.get(f"benchpress-{bench.bench_name}-{suffix}").remove(force=True)
			except Exception:
				pass
		if bench.wg_public_key:
			from benchpress.wg_manager import remove_peer_from_server

			try:
				remove_peer_from_server(bench.wg_public_key)
			except Exception:
				pass
		bench.status = "Stopped"
		bench.save(ignore_permissions=True)
		frappe.delete_doc("Bench Instance", bench_name, force=True)
		frappe.db.commit()
		return {"status": "deleted"}
	else:
		frappe.throw(_("Invalid action: {0}").format(action))

	bench.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": bench.name, "status": bench.status}


@frappe.whitelist()
def get_deploy_logs(bench_name: str) -> list[dict]:
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

	doc = frappe.get_doc(
		{
			"doctype": "Bench Site",
			"site_name": data.get("site_name"),
			"bench": data.get("bench"),
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
	frappe.db.commit()

	frappe.enqueue(
		"benchpress.api._create_site_on_bench",
		site_doc_name=doc.name,
		queue="long",
		timeout=600,
	)

	return {"name": doc.name, "status": "Creating"}


def _create_site_on_bench(site_doc_name: str) -> None:
	"""Background job to create a site inside a bench container."""
	import secrets

	from benchpress.docker_manager import exec_in_container

	site = frappe.get_doc("Bench Site", site_doc_name)
	bench = frappe.get_doc("Bench Instance", site.bench)

	try:
		admin_password = secrets.token_urlsafe(16)
		site.admin_password = admin_password

		apps_csv = ",".join(a.app_name for a in site.apps_installed)
		exit_code, output = exec_in_container(
			bench.container_id,
			f"bash /var/labsdata/scripts/setup-site.sh {site.full_domain} {admin_password} {apps_csv}",
		)
		if exit_code != 0:
			site.status = "Error"
			site.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.log_error(title=f"Site creation failed: {site.full_domain}", message=output[:500])
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
