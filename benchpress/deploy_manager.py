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


def _remove_stale_container(bench) -> None:
	"""Remove any existing container, preserving the data volume."""
	from benchpress.docker_manager import get_client

	client = get_client()

	if bench.container_id:
		try:
			client.containers.get(bench.container_id).remove(force=True)
		except Exception:
			pass
		bench.container_id = None

	try:
		container = client.containers.get(bench.bench_name)
		container.remove(force=True)
	except Exception:
		pass


def deploy_bench(bench_name: str) -> None:
	"""Deploy pipeline. Image already has bench + apps + site baked in.

	Step 1: Build lab image if not ready (layered Dockerfile with caching)
	Step 2: Create and start container — everything is ready to go
	"""
	bench = frappe.get_doc("Bench Instance", bench_name)
	lab = frappe.get_doc("Lab", bench.lab)

	deploy_log = frappe.get_doc(
		{
			"doctype": "Deploy Log",
			"bench": bench_name,
			"message": "=== Deploy started ===\n",
			"log_type": "info",
			"timestamp": frappe.utils.now_datetime(),
		}
	)
	deploy_log.insert(ignore_permissions=True)
	frappe.db.commit()
	deploy_log_name = deploy_log.name

	def append_log(line: str, log_type: str = "info") -> None:
		frappe.publish_realtime(
			event="bench_deploy_log",
			message={"bench": bench_name, "log": line, "type": log_type, "deploy_log": deploy_log_name},
			after_commit=False,
		)
		current = frappe.db.get_value("Deploy Log", deploy_log_name, "message") or ""
		frappe.db.set_value(
			"Deploy Log", deploy_log_name, "message", current + line + "\n", update_modified=False
		)
		frappe.db.commit()

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

			append_log(f"=== Building lab image for {lab.title} ===")
			_build_lab_with_logs(lab, bench.site_name, admin_password, append_log)
		else:
			append_log(f"Using cached lab image: {lab.image_tag}")

		# Step 2: Create and start container (remove stale container by name if exists)
		_remove_stale_container(bench)

		append_log(f"=== Creating container ===")
		append_log(f"Memory: {lab.memory_limit}, CPU: {lab.cpu_cores}")
		container_id = create_bench_container(bench, lab)
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		append_log("Starting container...")
		start_container(container_id)
		time.sleep(5)

		# Step 3: Capture container IP (eth0 / Docker network IP)
		from benchpress.wg_manager import _get_container_ip

		container_ip = _get_container_ip(container_id)
		if container_ip:
			bench.container_ip = container_ip
			bench.save(ignore_permissions=True)
			frappe.db.commit()

		# Step 4: WireGuard VPN setup (inside container)
		settings = frappe.get_cached_doc("BenchPress Settings")
		if settings.wg_server_public_key and settings.wg_server_endpoint:
			from benchpress.wg_manager import (
				add_peer_to_server,
				allocate_ip,
				ensure_wg_running,
				generate_keypair,
				generate_peer_config,
				remove_peer_from_server,
				setup_container_vpn,
				sync_wg_config,
			)

			append_log("=== Configuring WireGuard VPN ===")
			ensure_wg_running()

			if bench.wg_ip and bench.wg_public_key:
				try:
					remove_peer_from_server(bench.wg_public_key)
				except Exception:
					pass
				wg_ip = bench.wg_ip
				append_log(f"Reusing VPN IP {wg_ip}")
			else:
				wg_ip = allocate_ip()

			keys = generate_keypair()
			config = generate_peer_config(
				private_key=keys["private_key"],
				peer_ip=wg_ip,
				server_public_key=settings.wg_server_public_key,
				server_endpoint=settings.wg_server_endpoint,
				server_port=settings.wg_server_port or 51820,
			)
			add_peer_to_server(keys["public_key"], wg_ip)
			setup_container_vpn(
				container_id,
				keys["private_key"],
				wg_ip,
				settings.wg_server_public_key,
				settings.wg_server_port or 51820,
			)
			sync_wg_config()

			bench.wg_ip = wg_ip
			bench.wg_private_key = keys["private_key"]
			bench.wg_public_key = keys["public_key"]
			bench.wg_config = config
			bench.save(ignore_permissions=True)
			frappe.db.commit()
			append_log(f"VPN configured at {wg_ip}")
		else:
			append_log("WireGuard not configured, skipping VPN.", "warning")

		# Step 5: User provisioning via linkuser.sh
		from benchpress.docker_manager import exec_in_container

		if not bench.ssh_username:
			bench.ssh_username = bench.owner.split("@")[0].lower()[:32] or "frappe"

		ssh_password = secrets.token_urlsafe(12)
		settings = frappe.get_cached_doc("BenchPress Settings")

		linkuser_args = [
			bench.ssh_username,
			bench.owner,
			lab.title,
			bench.wg_ip or "0.0.0.0",
			ssh_password,
			bench.bench_name,
			settings.base_domain or "localhost",
			lab.mount_target or "/home/frappe",
		]

		append_log(f"=== Provisioning SSH user '{bench.ssh_username}' ===")
		linkuser_cmd = "bash /opt/benchpress/scripts/linkuser.sh " + " ".join(
			f"'{a}'" for a in linkuser_args
		)
		exit_code, output = exec_in_container(container_id, linkuser_cmd, user="root")
		if exit_code != 0:
			append_log(f"linkuser.sh output: {output}", "warning")
			raise Exception(f"linkuser.sh failed (exit {exit_code}): {output}")

		bench.ssh_password = ssh_password
		append_log(f"SSH user '{bench.ssh_username}' provisioned.")

		# Done — user will SSH in and run bench start
		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		append_log("=== Deploy complete ===", "success")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "success")
		frappe.db.commit()

	except Exception as e:
		bench.reload()
		bench.status = "Error"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		append_log(f"=== Deploy failed: {e!s} ===", "error")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "error")
		frappe.db.commit()
		frappe.log_error(
			title=f"BenchPress deploy failed: {bench_name}",
			message=frappe.get_traceback(),
		)


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


def stop_bench(bench_name: str) -> None:
	"""Stop a bench container. VPN stops automatically with the container."""
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		stop_container(bench.container_id)

	bench.status = "Stopped"
	bench.save(ignore_permissions=True)
	frappe.db.commit()
