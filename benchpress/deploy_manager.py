# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import secrets
import time

import frappe

from benchpress.docker_manager import (
	build_lab_image,
	create_bench_container,
	exec_in_container,
	remove_container,
	start_container,
	stop_container,
	write_file_to_container,
)
from benchpress.mariadb_manager import (
	create_mariadb_user,
	drop_mariadb_user,
	ensure_database_server,
	wait_for_mariadb,
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
	"""Deploy pipeline — shared MariaDB, site created at runtime via press agent pattern."""
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

		admin_password = "admin"
		bench.admin_password = admin_password

		# Step 1: Build lab image if not ready
		if lab.status != "Ready" or not lab.image_tag:
			append_log(f"=== Building lab image for {lab.title} ===")
			_build_lab_with_logs(lab, append_log)
		else:
			append_log(f"Using cached lab image: {lab.image_tag}")

		# Step 2: Create and start container
		_remove_stale_container(bench)
		append_log("=== Creating container ===")
		container_id = create_bench_container(bench, lab)
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		start_container(container_id)
		time.sleep(5)

		# Step 3: Capture container IP
		from benchpress.wg_manager import _get_container_ip

		container_ip = _get_container_ip(container_id)
		if container_ip:
			bench.container_ip = container_ip
			bench.save(ignore_permissions=True)
			frappe.db.commit()

		# Step 4: WireGuard VPN setup
		settings = frappe.get_cached_doc("BenchPress Settings")
		if settings.wg_server_public_key and settings.wg_server_endpoint:
			from benchpress.wg_manager import (
				add_peer_to_server,
				allocate_ip,
				ensure_wg_running,
				generate_keypair,
				remove_peer_from_server,
				setup_container_vpn,
				sync_wg_config,
			)

			append_log("=== Configuring WireGuard VPN ===")
			ensure_wg_running()

			if bench.wg_public_key:
				try:
					remove_peer_from_server(bench.wg_public_key)
				except Exception:
					pass

			container_wg_ip = bench.wg_ip if bench.wg_ip else allocate_ip()
			container_keys = generate_keypair()
			add_peer_to_server(container_keys["public_key"], container_wg_ip)
			setup_container_vpn(
				container_id,
				container_keys["private_key"],
				container_wg_ip,
				settings.wg_server_public_key,
				settings.wg_server_port or 51820,
			)
			sync_wg_config()

			bench.wg_ip = container_wg_ip
			bench.wg_private_key = container_keys["private_key"]
			bench.wg_public_key = container_keys["public_key"]
			bench.save(ignore_permissions=True)
			frappe.db.commit()
			append_log(f"Container VPN: {container_wg_ip}")
		else:
			append_log("WireGuard not configured, skipping VPN.", "warning")

		# Step 5: Ensure shared MariaDB is running
		append_log("=== Ensuring shared MariaDB is running ===")
		db_server_name = ensure_database_server()
		db_server = frappe.get_doc("Database Server", db_server_name)
		wait_for_mariadb(db_server_name, timeout=60)
		append_log(f"MariaDB ready at {db_server.container_name}:{db_server.port or 3306}")

		bench.database_server = db_server_name
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		# Step 6: Write common_site_config.json with Docker DNS host
		bench_dir = f"{lab.mount_target or '/home/frappe'}/frappe-bench"
		site_name = bench.site_name
		config = {
			"db_host": db_server.container_name,
			"db_port": db_server.port or 3306,
			"redis_cache": "redis://127.0.0.1:6379",
			"redis_queue": "redis://127.0.0.1:6379",
			"redis_socketio": "redis://127.0.0.1:6379",
			"socketio_port": 9000,
			"webserver_port": 8000,
			"default_site": site_name,
		}
		write_file_to_container(
			container_id, json.dumps(config, indent=2), f"{bench_dir}/sites/common_site_config.json"
		)
		append_log("common_site_config.json written")

		# Step 7: Create site via temp user pattern (press agent/bench.py:194-206)
		append_log(f"=== Creating site {site_name} ===")

		db_name, temp_user, temp_password = create_mariadb_user(db_server_name, site_name)
		try:
			apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name.lower() != "frappe")
			exit_code, output = exec_in_container(
				container_id,
				"bash /opt/benchpress/scripts/setup-site.sh",
				user="frappe",
				workdir=bench_dir,
				environment={
					"SITE_NAME": site_name,
					"ADMIN_PASSWORD": admin_password,
					"APPS": apps_csv,
					"DB_HOST": db_server.container_name,
					"DB_NAME": db_name,
					"MARIADB_ROOT_USERNAME": temp_user,
					"MARIADB_ROOT_PASSWORD": temp_password,
				},
			)
			if exit_code != 0:
				raise Exception(f"bench new-site failed (exit {exit_code}): {output}")
			append_log("Site created successfully")
		finally:
			drop_mariadb_user(db_server_name, site_name, db_name)

		append_log("Building assets...")
		exec_in_container(container_id, "bench build", user="frappe", workdir=bench_dir)

		# Step 8: User provisioning via linkuser.sh
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
		linkuser_cmd = "bash /opt/benchpress/scripts/linkuser.sh " + " ".join(f"'{a}'" for a in linkuser_args)
		exit_code, output = exec_in_container(container_id, linkuser_cmd, user="root")
		if exit_code != 0:
			raise Exception(f"linkuser.sh failed (exit {exit_code}): {output}")

		bench.ssh_password = ssh_password
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

	# Remove the data volume so bench new-site runs clean on redeploy
	from benchpress.docker_manager import get_client

	client = get_client()
	try:
		vol = client.volumes.get(f"benchpress-{bench_name}-data")
		vol.remove(force=True)
	except Exception:
		pass

	# Drop the site database from shared MariaDB so bench new-site can recreate it
	if bench.database_server and bench.site_name:
		from benchpress.mariadb_manager import drop_site_database

		try:
			drop_site_database(bench.database_server, bench.site_name)
		except Exception:
			pass

	bench.container_id = None
	bench.container_image = None
	bench.status = "Draft"
	bench.started_at = None
	bench.save(ignore_permissions=True)
	frappe.db.commit()

	deploy_bench(bench_name)


def _build_lab_with_logs(lab, log_fn) -> None:
	"""Build image with bench + apps (site created at runtime)."""
	lab.status = "Building"
	lab.save(ignore_permissions=True)
	frappe.db.commit()

	image_tag = build_lab_image(lab, log_fn=log_fn)

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
		_build_lab_with_logs(lab, append_log)

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
