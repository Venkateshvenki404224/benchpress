# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import secrets
import time

import frappe

from benchpress.docker_manager import (
	build_lab_image,
	create_bench_container,
	remove_container,
	start_container,
	stop_container,
)


def log_deploy(bench_name: str, message: str, log_type: str = "info") -> None:
	frappe.get_doc(
		{
			"doctype": "Deploy Log",
			"bench": bench_name,
			"message": message,
			"log_type": log_type,
			"timestamp": frappe.utils.now_datetime(),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	frappe.publish_realtime(
		event="bench_deploy_log",
		message={"bench": bench_name, "log": message, "type": log_type},
		doctype="Bench Instance",
		docname=bench_name,
		after_commit=False,
	)


def _remove_stale_container(bench) -> None:
	"""Remove any existing container and its volume (for orphaned containers)."""
	from benchpress.docker_manager import get_client

	client = get_client()

	# Try by stored container_id first
	if bench.container_id:
		try:
			client.containers.get(bench.container_id).remove(force=True, v=True)
		except Exception:
			pass
		bench.container_id = None

	# Also try by name — handles orphaned containers from failed deploys
	try:
		container = client.containers.get(bench.bench_name)
		container.remove(force=True, v=True)
	except Exception:
		pass

	# Remove the named volume so Docker repopulates it from the image on next create
	volume_name = f"benchpress-{bench.bench_name}-data"
	try:
		client.volumes.get(volume_name).remove(force=True)
	except Exception:
		pass


def deploy_bench(bench_name: str) -> None:
	"""Deploy pipeline. Image already has bench + apps + site baked in.

	Step 1: Build lab image if not ready (layered Dockerfile with caching)
	Step 2: Create and start container — everything is ready to go
	"""
	bench = frappe.get_doc("Bench Instance", bench_name)
	lab = frappe.get_doc("Lab", bench.lab)

	try:
		bench.status = "Deploying"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		# Step 1: Build lab image if not ready
		if lab.status != "Ready" or not lab.image_tag:
			admin_password = secrets.token_urlsafe(16)
			bench.admin_password = admin_password
			bench.save(ignore_permissions=True)
			frappe.db.commit()

			log_deploy(bench_name, f"Building lab image for {lab.title}...")
			_build_lab_with_logs(
				lab, bench.site_name, admin_password, lambda msg: log_deploy(bench_name, msg)
			)
		else:
			log_deploy(bench_name, f"Using cached lab image: {lab.image_tag}")

		# Step 2: Create and start container (remove stale container by name if exists)
		_remove_stale_container(bench)

		log_deploy(bench_name, f"Creating container (mem: {lab.memory_limit}, cpu: {lab.cpu_cores})...")
		container_id = create_bench_container(bench, lab)
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		log_deploy(bench_name, "Starting container...")
		start_container(container_id)
		time.sleep(5)

		# Setup SSH user password
		from benchpress.docker_manager import exec_in_container

		ssh_password = secrets.token_urlsafe(12)
		exec_in_container(
			container_id,
			f"echo 'frappe:{ssh_password}' | sudo chpasswd",
			user="root",
		)
		log_deploy(bench_name, "SSH user 'frappe' password set.")

		# Done — user will SSH in and run bench start
		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		log_deploy(bench_name, "Bench ready! SSH in and run 'bench start'.", "success")

	except Exception as e:
		bench.reload()
		bench.status = "Error"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		log_deploy(bench_name, f"Deploy failed: {e!s}", "error")
		frappe.log_error(
			title=f"BenchPress deploy failed: {bench_name}",
			message=frappe.get_traceback(),
		)


def stop_bench(bench_name: str) -> None:
	bench = frappe.get_doc("Bench Instance", bench_name)
	if not bench.container_id:
		frappe.throw("No container to stop.")

	stop_container(bench.container_id)
	bench.status = "Stopped"
	bench.save(ignore_permissions=True)
	frappe.db.commit()


def redeploy_bench(bench_name: str) -> None:
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		try:
			stop_container(bench.container_id)
		except Exception:
			pass
		try:
			remove_container(bench.container_id)
		except Exception:
			pass

	bench.container_id = None
	bench.container_image = None
	bench.status = "Draft"
	bench.started_at = None
	bench.save(ignore_permissions=True)
	frappe.db.commit()

	deploy_bench(bench_name)


def _build_lab_with_logs(lab, site_name, admin_password, log_fn) -> None:
	"""Build image with bench + apps + site baked in via layered Dockerfile."""
	lab.status = "Building"
	lab.save(ignore_permissions=True)
	frappe.db.commit()

	image_tag = build_lab_image(lab, site_name, admin_password, log_fn=log_fn)

	lab.reload()
	lab.image_tag = image_tag
	lab.status = "Ready"
	lab.save(ignore_permissions=True)
	frappe.db.commit()
	if log_fn:
		log_fn(f"Lab image ready: {image_tag}")


def build_lab(lab_name: str) -> None:
	"""Build a lab image as a background job with realtime log streaming."""
	lab = frappe.get_doc("Lab", lab_name)

	build_log = frappe.get_doc(
		{
			"doctype": "Build Log",
			"lab": lab_name,
			"message": "=== Build started ===\n",
			"log_type": "info",
			"timestamp": frappe.utils.now_datetime(),
		}
	)
	build_log.insert(ignore_permissions=True)
	frappe.db.commit()
	build_log_name = build_log.name

	def append_log(line: str, log_type: str = "info") -> None:
		frappe.publish_realtime(
			event="lab_build_log",
			message={"lab": lab_name, "log": line, "type": log_type, "build_log": build_log_name},
			after_commit=False,
		)
		current = frappe.db.get_value("Build Log", build_log_name, "message") or ""
		frappe.db.set_value(
			"Build Log", build_log_name, "message", current + line + "\n", update_modified=False
		)
		frappe.db.commit()

	try:
		# Generate a default site name and password for the baked-in site
		from benchpress.benchpress.doctype.bench_instance import get_instance_id

		site_name = f"{get_instance_id('default', lab_name)}.localhost"
		admin_password = secrets.token_urlsafe(16)

		_build_lab_with_logs(lab, site_name, admin_password, append_log)

		append_log(f"=== Build complete: {lab.image_tag} ===", "success")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "success")
		frappe.db.commit()

	except Exception as e:
		lab.reload()
		lab.status = "Error"
		lab.save(ignore_permissions=True)
		frappe.db.commit()

		append_log(f"=== Build failed: {e!s} ===", "error")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "error")
		frappe.db.commit()
		frappe.log_error(
			title=f"Lab image build failed: {lab_name}",
			message=frappe.get_traceback(),
		)
