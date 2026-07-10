# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import secrets

import frappe
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.synchronization import filelock

from benchpress.docker_manager import (
	build_lab_image,
	create_bench_container,
	exec_in_container,
	remove_container,
	start_container,
	stop_container,
	wait_for_container_running,
	write_file_to_container,
)
from benchpress.mariadb_manager import (
	create_mariadb_user,
	drop_mariadb_user,
	ensure_infrastructure,
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
			pass  # best-effort
		bench.container_id = None

	try:
		container = client.containers.get(bench.bench_name)
		container.remove(force=True)
	except Exception:
		pass  # best-effort


def remove_bench_volume(bench_name: str) -> None:
	"""Remove the bench data volume if it exists."""
	from benchpress.docker_manager import get_client

	try:
		get_client().volumes.get(f"benchpress-{bench_name}-data").remove(force=True)
	except Exception:
		pass  # best-effort


def build_linkuser_args(bench, lab, settings, ssh_password: str) -> list[str]:
	"""Positional arguments for linkuser.sh, in the order the script reads them.

	Order must match scripts/linkuser.sh:
	USERNAME EMAIL LAB_NAME WG_IP SSH_PASSWORD BENCH_NAME BASE_DOMAIN LOGIN_SHELL
	"""
	return [
		bench.ssh_username,
		bench.owner,
		lab.title,
		bench.wg_ip or "0.0.0.0",
		ssh_password,
		bench.bench_name,
		settings.base_domain or "localhost",
		lab.shell or "/bin/bash",
	]


def _make_log_appender(doctype: str, log_name: str, event: str, context: dict):
	def append_log(line: str, log_type: str = "info") -> None:
		frappe.publish_realtime(  # nosemgrep -- the SPA listens via raw socket.io without doc-room subscription; room-scoping would drop its events
			event=event,
			message={**context, "log": line, "type": log_type},
			after_commit=False,
		)
		current = frappe.db.get_value(doctype, log_name, "message") or ""
		frappe.db.set_value(doctype, log_name, "message", current + line + "\n", update_modified=False)
		frappe.db.commit()

	return append_log


def _notify_owner(user: str, subject: str, document_type: str, document_name: str) -> None:
	"""Best-effort desk notification on a terminal deploy/build state.

	type "Alert" both bypasses the for_user == from_user skip in
	make_notification_logs (the job usually runs as the owner) and is exempt
	from notification emails, so this stays desk-only. Never raises — a
	notification failure must not disturb the deploy/build outcome.
	"""
	try:
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		email = frappe.db.get_value("User", user, "email") or user
		enqueue_create_notification(
			[email],
			{
				"type": "Alert",
				"subject": subject,
				"document_type": document_type,
				"document_name": document_name,
			},
		)
	except Exception:
		frappe.log_error(
			title=f"BenchPress notification failed: {document_name}",
			message=frappe.get_traceback(),
		)


def create_site_in_container(
	container_id: str, db_server, site_name: str, admin_password: str, apps_csv: str
) -> tuple[int, str]:
	"""Run setup-site.sh inside a bench container using a temporary MariaDB user."""
	bench_dir = "/home/frappe/frappe-bench"  # fixed: the data volume binds at /home/frappe
	db_name, temp_user, temp_password = create_mariadb_user(db_server.name, site_name)
	try:
		return exec_in_container(
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
	finally:
		drop_mariadb_user(db_server.name, site_name, db_name)


def _log_deploy_skipped(bench_name: str) -> None:
	frappe.get_doc(
		{
			"doctype": "Deploy Log",
			"bench": bench_name,
			"message": "=== Deploy skipped: another deploy is already in progress ===\n",
			"log_type": "warning",
			"timestamp": frappe.utils.now_datetime(),
		}
	).insert(ignore_permissions=True)
	# no manual commit: the job ends right after this, and the worker commits on return


def deploy_bench(bench_name: str) -> None:
	"""Deploy a bench, refusing to run concurrently with another deploy of the same bench."""
	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_deploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _deploy_bench(bench_name: str) -> None:
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

	append_log = _make_log_appender(
		"Deploy Log",
		deploy_log_name,
		"bench_deploy_log",
		{"bench": bench_name, "deploy_log": deploy_log_name},
	)

	try:
		bench.status = "Deploying"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		admin_password = secrets.token_urlsafe(10)
		bench.admin_password = admin_password

		append_log("=== Checking shared infrastructure (MariaDB + Redis) ===")
		db_server_name = ensure_infrastructure()
		db_server = frappe.get_doc("Database Server", db_server_name)
		wait_for_mariadb(db_server_name, timeout=60)
		append_log(f"MariaDB reachable at {db_server.container_name}:{db_server.port or 3306}")

		bench.database_server = db_server_name
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		if lab.status != "Ready" or not lab.image_tag:
			append_log(f"=== Building lab image for {lab.title} ===")
			_build_lab_with_logs(lab, append_log)
		else:
			append_log(f"Using cached lab image: {lab.image_tag}")

		_remove_stale_container(bench)
		append_log("=== Creating container ===")
		container_id = create_bench_container(bench, lab)
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		start_container(container_id)
		append_log("Waiting for container to report running with an IP...")
		container_ip = wait_for_container_running(container_id, timeout=60)
		bench.container_ip = container_ip
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		settings = frappe.get_cached_doc("BenchPress Settings")

		_setup_container_vpn(bench, container_id, append_log)

		bench_dir = "/home/frappe/frappe-bench"  # fixed: the data volume binds at /home/frappe
		site_name = bench.site_name
		config = {
			**db_server.get_connection_config(),
			"redis_cache": "redis://benchpress-redis:6379/0",
			"redis_queue": "redis://benchpress-redis:6379/1",
			"redis_socketio": "redis://benchpress-redis:6379/2",
			"socketio_port": 9000,
			"webserver_port": 8000,
			"default_site": site_name,
		}
		write_file_to_container(
			container_id, json.dumps(config, indent=2), f"{bench_dir}/sites/common_site_config.json"
		)
		append_log("common_site_config.json written")

		append_log(f"=== Creating site {site_name} ===")

		apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name.lower() != "frappe")
		exit_code, output = create_site_in_container(
			container_id, db_server, site_name, admin_password, apps_csv
		)
		if exit_code != 0:
			raise Exception(f"bench new-site failed (exit {exit_code}): {output}")
		append_log("Site created successfully")

		append_log("Building assets...")
		exec_in_container(container_id, "bench build", user="frappe", workdir=bench_dir)

		if not bench.ssh_username:
			bench.ssh_username = bench._derive_username(bench.owner)

		ssh_password = secrets.token_urlsafe(12)
		linkuser_args = build_linkuser_args(bench, lab, settings, ssh_password)
		append_log(f"=== Provisioning SSH user '{bench.ssh_username}' ===")
		linkuser_cmd = "bash /opt/benchpress/scripts/linkuser.sh " + " ".join(f"'{a}'" for a in linkuser_args)
		exit_code, output = exec_in_container(container_id, linkuser_cmd, user="root")
		if output:
			append_log(output.strip())
		if exit_code != 0:
			raise Exception(f"linkuser.sh failed (exit {exit_code}): {output}")

		bench.ssh_password = ssh_password

		if getattr(lab, "enable_code_server", 0):
			append_log("=== Provisioning code-server ===")
			cs_user = bench.ssh_username
			cs_home = f"/home/{cs_user}"
			code_server_password = secrets.token_urlsafe(16)
			config_yaml = (
				f"bind-addr: 0.0.0.0:8080\nauth: password\npassword: {code_server_password}\ncert: false\n"
			)
			write_file_to_container(
				container_id,
				config_yaml,
				f"{cs_home}/.config/code-server/config.yaml",
			)
			exec_in_container(
				container_id,
				f"chown -R {cs_user}:{cs_user} {cs_home}/.config && chmod 600 {cs_home}/.config/code-server/config.yaml",
				user="root",
			)
			exec_in_container(container_id, "bash /opt/benchpress/scripts/restart.sh", user="root")
			bench.code_server_password = code_server_password
			bench.code_server_url = f"http://{bench.wg_ip or bench.container_ip or '127.0.0.1'}:8080/"
			append_log(f"code-server ready at {bench.code_server_url}")

		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		append_log("=== Deploy complete ===", "success")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "success")
		frappe.db.commit()
		_notify_owner(
			bench.owner,
			f"Bench deployed: {bench.bench_name} ({bench.site_name})",
			"Bench Instance",
			bench.name,
		)

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
		_notify_owner(bench.owner, f"Bench deploy failed: {bench.bench_name}", "Bench Instance", bench.name)


def _setup_container_vpn(bench, container_id: str, append_log) -> None:
	"""Replace any stale peer, claim a fresh tunnel IP, and configure the container.

	Removing before creating keeps exactly one peer per bench across deploy /
	redeploy; the link is persisted before the container is configured so a
	configure failure (which reloads the bench) cannot orphan the peer.
	"""
	from benchpress.vpn_adapter import configure_container, create_container_peer, remove_bench_peer

	append_log("=== Configuring WireGuard VPN (vpn_management) ===")
	remove_bench_peer(bench)
	peer = create_container_peer(bench)
	bench.wg_ip = peer["assigned_ip"]
	bench.save(ignore_permissions=True)
	frappe.db.commit()
	append_log(f"VPN peer {peer['peer']} registered, claimed IP {peer['assigned_ip']}")
	configure_container(container_id, peer["private_key"], peer["assigned_ip"])
	append_log(f"Container VPN: {peer['assigned_ip']}")


def redeploy_bench(bench_name: str) -> None:
	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_redeploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _redeploy_bench(bench_name: str) -> None:
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		try:
			stop_container(bench.container_id)
		except Exception:
			pass  # best-effort
		try:
			remove_container(bench.container_id)
		except Exception:
			pass  # best-effort

	remove_bench_volume(bench_name)

	if bench.database_server and bench.site_name:
		from benchpress.mariadb_manager import drop_site_database

		try:
			drop_site_database(bench.database_server, bench.site_name)
		except Exception:
			pass  # best-effort

	bench.container_id = None
	bench.container_image = None
	bench.status = "Draft"
	bench.started_at = None
	bench.save(ignore_permissions=True)
	frappe.db.commit()

	_deploy_bench(bench_name)


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

	append_log = _make_log_appender(
		"Build Log", build_log_name, "lab_build_log", {"lab": lab_name, "build_log": build_log_name}
	)

	try:
		_build_lab_with_logs(lab, append_log)

		append_log(f"=== Build complete: {lab.image_tag} ===", "success")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "success")
		frappe.db.commit()
		_notify_owner(lab.owner, f"Lab build complete: {lab.title} ({lab.image_tag})", "Lab", lab_name)

	except Exception as e:
		frappe.db.set_value("Lab", lab_name, "status", "Error")
		frappe.db.commit()

		append_log(f"=== Build failed: {e!s} ===", "error")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "error")
		frappe.db.commit()
		frappe.log_error(
			title=f"Lab image build failed: {lab_name}",
			message=frappe.get_traceback(),
		)
		_notify_owner(lab.owner, f"Lab build failed: {lab.title}", "Lab", lab_name)


def stop_bench(bench_name: str) -> None:
	"""Stop a bench container. VPN stops automatically with the container."""
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		stop_container(bench.container_id)

	bench.status = "Stopped"
	bench.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: intentional commit to persist status before response
