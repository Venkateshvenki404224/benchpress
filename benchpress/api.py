# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def has_app_permission() -> bool:
	return "System Manager" in frappe.get_roles(frappe.session.user)


# --- Lab endpoints ---


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
def create_lab(data: str) -> dict:
	data = frappe.parse_json(data)

	doc = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": data.get("lab_id"),
			"title": data.get("title"),
			"description": data.get("description", ""),
			"frappe_version": data.get("frappe_version"),
			"memory_limit": data.get("memory_limit", "512m"),
			"cpu_cores": data.get("cpu_cores", 1),
		}
	)

	for app in data.get("apps", []):
		doc.append(
			"apps",
			{
				"app_name": app.get("app_name"),
				"app_label": app.get("app_label", app.get("app_name")),
				"git_url": app.get("git_url"),
				"branch": app.get("branch"),
			},
		)

	doc.insert()
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status}


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


# --- Bench endpoints ---


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
			"wg_ip",
			"cpu_usage",
			"memory_usage",
			"started_at",
		],
		order_by="creation desc",
	)

	for bench in benches:
		bench["app_count"] = frappe.db.count("Bench App", {"parent": bench["name"]})
		bench["site_count"] = frappe.db.count("Bench Site", {"bench": bench["name"]})

	return benches


@frappe.whitelist()
def get_bench(name: str) -> dict:
	bench = frappe.get_cached_doc("Bench Instance", name)
	apps = [{"app_name": a.app_name, "app_label": a.app_label} for a in bench.apps]
	sites = frappe.get_all(
		"Bench Site",
		filters={"bench": name},
		fields=["name", "site_name", "full_domain", "status"],
	)

	return {
		"name": bench.name,
		"bench_name": bench.bench_name,
		"lab": bench.lab,
		"frappe_version": bench.frappe_version,
		"domain": bench.domain,
		"status": bench.status,
		"container_id": bench.container_id,
		"container_image": bench.container_image,
		"wg_ip": bench.wg_ip,
		"cpu_usage": bench.cpu_usage,
		"memory_usage": bench.memory_usage,
		"started_at": bench.started_at,
		"admin_password": bench.admin_password,
		"apps": apps,
		"sites": sites,
	}


@frappe.whitelist()
def create_bench(data: str) -> dict:
	data = frappe.parse_json(data)

	lab_name = data.get("lab")
	if not lab_name:
		frappe.throw(_("Lab is required to create a bench."))

	lab = frappe.get_cached_doc("Lab", lab_name)

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

	# Copy apps from lab to bench
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
		fields=["message", "log_type", "timestamp"],
		order_by="timestamp asc",
		limit_page_length=100,
	)


@frappe.whitelist()
def get_build_logs(lab_name: str) -> list[dict]:
	return frappe.get_all(
		"Build Log",
		filters={"lab": lab_name},
		fields=["name", "message", "log_type", "timestamp"],
		order_by="timestamp desc",
		limit_page_length=20,
	)


@frappe.whitelist()
def get_wg_config(bench_name: str) -> str:
	bench = frappe.get_cached_doc("Bench Instance", bench_name)
	if not bench.wg_config:
		frappe.throw(_("WireGuard config not yet generated for this bench."))
	return bench.wg_config


@frappe.whitelist()
def get_bench_stats(bench_name: str) -> dict:
	from benchpress.docker_manager import get_container_stats

	container_id = frappe.db.get_value("Bench Instance", bench_name, "container_id")
	if not container_id:
		frappe.throw(_("No container found for this bench."))
	return get_container_stats(container_id)


# --- Site endpoints ---


@frappe.whitelist()
def get_sites(bench_name: str) -> list[dict]:
	return frappe.get_all(
		"Bench Site",
		filters={"bench": bench_name},
		fields=["name", "site_name", "full_domain", "status"],
		order_by="creation desc",
	)


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


@frappe.whitelist()
def site_action(site_name: str, action: str) -> dict:
	from benchpress.docker_manager import exec_in_container

	site = frappe.get_doc("Bench Site", site_name)
	bench = frappe.get_doc("Bench Instance", site.bench)

	if action == "enable":
		exec_in_container(bench.container_id, f"bench --site {site.full_domain} enable-scheduler")
		site.status = "Active"
	elif action == "disable":
		exec_in_container(bench.container_id, f"bench --site {site.full_domain} disable-scheduler")
		site.status = "Inactive"
	elif action == "drop":
		exec_in_container(bench.container_id, f"bench drop-site {site.full_domain} --force")
		frappe.delete_doc("Bench Site", site_name, force=True)
		frappe.db.commit()
		return {"status": "deleted"}
	elif action == "backup":
		exec_in_container(bench.container_id, f"bench --site {site.full_domain} backup")
		return {"name": site.name, "status": site.status, "message": "Backup initiated"}
	else:
		frappe.throw(_("Invalid action: {0}").format(action))

	site.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": site.name, "status": site.status}


# --- System endpoints ---


@frappe.whitelist()
def get_available_apps() -> list[dict]:
	return [
		{
			"name": "frappe",
			"label": "Frappe Framework",
			"git_url": "https://github.com/frappe/frappe",
			"branch": "version-15",
			"required": True,
		},
		{
			"name": "erpnext",
			"label": "ERPNext",
			"git_url": "https://github.com/frappe/erpnext",
			"branch": "version-15",
		},
		{
			"name": "hrms",
			"label": "HRMS",
			"git_url": "https://github.com/frappe/hrms",
			"branch": "version-15",
		},
		{"name": "lms", "label": "LMS", "git_url": "https://github.com/frappe/lms", "branch": "develop"},
		{
			"name": "helpdesk",
			"label": "Helpdesk",
			"git_url": "https://github.com/frappe/helpdesk",
			"branch": "develop",
		},
		{"name": "wiki", "label": "Wiki", "git_url": "https://github.com/frappe/wiki", "branch": "develop"},
		{
			"name": "webshop",
			"label": "Webshop",
			"git_url": "https://github.com/frappe/webshop",
			"branch": "version-15",
		},
		{"name": "crm", "label": "CRM", "git_url": "https://github.com/frappe/crm", "branch": "develop"},
	]


@frappe.whitelist()
def get_settings() -> dict:
	settings = frappe.get_cached_doc("BenchPress Settings")
	return {
		"base_domain": settings.base_domain,
		"traefik_network": settings.traefik_network,
		"default_image": settings.default_image,
		"wg_server_ip": settings.wg_server_ip,
	}


@frappe.whitelist()
def health_check() -> dict:
	result = {"docker": False, "wireguard": False}

	try:
		from benchpress.docker_manager import get_client

		client = get_client()
		client.ping()
		result["docker"] = True
	except Exception:
		pass

	try:
		import subprocess

		output = subprocess.run(
			["sudo", "wg", "show", "wg0"],
			capture_output=True,
			text=True,
			timeout=5,
		)
		result["wireguard"] = output.returncode == 0
	except Exception:
		pass

	return result
