# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import secrets
import time

import frappe
from frappe import _

from benchpress.docker_manager import (
	build_lab_image,
	create_bench_container,
	exec_in_container,
	start_container,
	write_file_to_container,
)
from benchpress.wg_manager import (
	add_peer_to_server,
	allocate_ip,
	generate_keypair,
	generate_peer_config,
)


def log_deploy(bench_name: str, message: str, log_type: str = "info") -> None:
	"""Insert a deploy log entry and push realtime update to the browser."""
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
	)


def deploy_bench(bench_name: str) -> None:
	"""Full deployment pipeline. Runs as a background job via frappe.enqueue."""
	bench = frappe.get_doc("Bench Instance", bench_name)
	lab = frappe.get_doc("Lab", bench.lab)
	settings = frappe.get_cached_doc("BenchPress Settings")

	try:
		bench.status = "Deploying"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		# Step 1: Build lab image if not ready
		if lab.status != "Ready" or not lab.image_tag:
			log_deploy(bench_name, f"Building lab image for {lab.title}...")
			lab.status = "Building"
			lab.save(ignore_permissions=True)
			frappe.db.commit()

			image_tag = build_lab_image(lab, log_fn=lambda msg: log_deploy(bench_name, msg))
			lab.image_tag = image_tag
			lab.status = "Ready"
			lab.save(ignore_permissions=True)
			frappe.db.commit()
			log_deploy(bench_name, f"Lab image built: {image_tag}", "success")
		else:
			log_deploy(bench_name, f"Using cached lab image: {lab.image_tag}")

		# Step 2: Create container
		log_deploy(bench_name, f"Creating container (mem: {lab.memory_limit}, cpu: {lab.cpu_cores})...")
		container_id = create_bench_container(bench, lab)
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		# Step 3: Start container (entry.sh starts MariaDB, Redis, SSH)
		log_deploy(bench_name, "Starting container...")
		start_container(container_id)
		log_deploy(bench_name, "Waiting for services to initialize...")
		time.sleep(15)

		# Step 4: WireGuard setup (host-side)
		log_deploy(bench_name, "Configuring WireGuard VPN...")
		keys = generate_keypair()
		wg_ip = allocate_ip()
		config = generate_peer_config(
			private_key=keys["private_key"],
			peer_ip=wg_ip,
			server_public_key=settings.wg_server_public_key,
			server_endpoint=settings.wg_server_endpoint,
			server_port=settings.wg_server_port,
		)
		add_peer_to_server(keys["public_key"], wg_ip)

		# Write WG config into container and bring up interface
		write_file_to_container(container_id, config, "/etc/wireguard/wg0.conf")
		exec_in_container(container_id, "wg-quick up wg0", user="root")

		bench.wg_ip = wg_ip
		bench.wg_private_key = keys["private_key"]
		bench.wg_public_key = keys["public_key"]
		bench.wg_config = config
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		log_deploy(bench_name, f"WireGuard peer configured at {wg_ip}.")

		# Step 5: Create Frappe site
		admin_password = secrets.token_urlsafe(16)
		bench.admin_password = admin_password
		apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name != "frappe")

		log_deploy(bench_name, f"Creating site {bench.domain}...")
		exit_code, output = exec_in_container(
			container_id,
			f"bash /var/labsdata/scripts/setup-site.sh {bench.domain} {admin_password} {apps_csv}",
		)
		if exit_code != 0:
			log_deploy(bench_name, f"Site setup warning: {output[:500]}", "warning")
		else:
			log_deploy(bench_name, "Site created and apps installed.")

		# Done
		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		log_deploy(bench_name, "Bench deployed. SSH in and run 'bench start' to access your site.", "success")

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


def build_lab(lab_name: str) -> None:
	"""Build a lab image as a background job with realtime log streaming.
	Creates a single Build Log document and appends all lines to it.
	"""
	lab = frappe.get_doc("Lab", lab_name)

	# Create one Build Log doc for this entire build
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
		"""Append a line to the Build Log doc and push realtime."""
		frappe.publish_realtime(
			event="lab_build_log",
			message={"lab": lab_name, "log": line, "type": log_type, "build_log": build_log_name},
			after_commit=False,
		)
		current = frappe.db.get_value("Build Log", build_log_name, "message") or ""
		frappe.db.set_value("Build Log", build_log_name, "message", current + line + "\n", update_modified=False)
		frappe.db.commit()

	try:
		lab.status = "Building"
		lab.save(ignore_permissions=True)
		frappe.db.commit()

		image_tag = build_lab_image(lab, log_fn=append_log)

		lab.reload()
		lab.image_tag = image_tag
		lab.status = "Ready"
		lab.save(ignore_permissions=True)
		frappe.db.commit()

		append_log(f"=== Build complete: {image_tag} ===", "success")
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
