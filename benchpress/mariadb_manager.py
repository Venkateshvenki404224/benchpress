# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64
import hashlib
import secrets
import time
import uuid

import frappe

from benchpress.docker_manager import get_client

DEFAULT_MARIADB_CONFIG = """[mysqld]
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
innodb_buffer_pool_size=536870912
max_connections=500
wait_timeout=28800
"""


def get_database_name(site_name: str) -> str:
	"""Generate DB name from site name using SHA1 hash.
	Follows press agent/bench.py:256-258 pattern.
	"""
	return "_" + hashlib.sha1(site_name.encode()).hexdigest()[:16]


def _random_string(length: int = 16) -> str:
	return secrets.token_urlsafe(length)


def execute_sql(db_server_name: str, sql: str) -> tuple[int, str]:
	"""Execute SQL on MariaDB container via temp file (injection-safe).

	Uses base64 encoding to avoid shell interpolation of SQL content.
	"""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	root_pw = db_server.get_root_password()

	tmp = f"/tmp/_bp_query_{uuid.uuid4().hex}.sql"
	encoded = base64.b64encode(sql.encode()).decode()
	try:
		container.exec_run(cmd=["bash", "-c", f"echo '{encoded}' | base64 -d > {tmp}"])
		exit_code, output = container.exec_run(
			cmd=["bash", "-c", f"mariadb -u root -p'{root_pw}' < {tmp}"],
		)
	finally:
		container.exec_run(cmd=["rm", "-f", tmp])
	return exit_code, output.decode("utf-8", errors="replace")


def setup_database_server(db_server_name: str) -> None:
	"""Full setup: pull image, create container with custom config, start, wait for ready."""
	import tempfile

	db_server = frappe.get_doc("Database Server", db_server_name)

	try:
		client = get_client()
		root_password = db_server.get_root_password()

		# Ensure benchpress network exists
		try:
			client.networks.get("benchpress")
		except Exception:
			import docker

			client.networks.create(
				"benchpress",
				driver="bridge",
				ipam=docker.types.IPAMConfig(pool_configs=[docker.types.IPAMPool(subnet="172.30.0.0/24")]),
			)

		# Write custom config for bind-mount
		custom_config = db_server.custom_config or DEFAULT_MARIADB_CONFIG
		config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False)
		config_file.write(custom_config)
		config_file.close()

		# Remove existing container if any
		try:
			old = client.containers.get(db_server.container_name)
			old.remove(force=True)
		except Exception:
			pass

		container = client.containers.create(
			image=db_server.image_tag,
			name=db_server.container_name,
			labels={"benchpress.managed": "true", "benchpress.role": "mariadb"},
			detach=True,
			environment={"MARIADB_ROOT_PASSWORD": root_password},
			volumes={
				db_server.volume_name: {"bind": "/var/lib/mysql", "mode": "rw"},
				config_file.name: {"bind": "/etc/mysql/conf.d/benchpress.cnf", "mode": "ro"},
			},
			mem_limit=db_server.memory_limit or "1g",
			network="benchpress",
			restart_policy={"Name": "unless-stopped"},
		)

		container.start()
		wait_for_mariadb(db_server_name, container=container, root_pw=root_password, timeout=60)

		# Get container IP (informational only — connections use Docker DNS)
		container.reload()
		networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
		container_ip = networks.get("benchpress", {}).get("IPAddress", "")

		db_server.reload()
		db_server.container_id = container.id
		db_server.container_ip = container_ip
		db_server.status = "Active"
		db_server.created_at = frappe.utils.now()
		db_server.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception as e:
		db_server.reload()
		db_server.set_error(str(e))
		frappe.log_error(
			title=f"MariaDB setup failed: {db_server_name}",
			message=frappe.get_traceback(),
		)
		raise


def start_database_server(db_server_name: str) -> None:
	"""Start a stopped MariaDB container."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	container.start()

	db_server.status = "Active"
	db_server.save(ignore_permissions=True)
	frappe.db.commit()


def stop_database_server(db_server_name: str) -> None:
	"""Stop the MariaDB container."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	container.stop(timeout=30)

	db_server.status = "Stopped"
	db_server.save(ignore_permissions=True)
	frappe.db.commit()


def ensure_database_server() -> str:
	"""Get or create the default Database Server. Returns doc name.
	Idempotent — safe to call multiple times.
	"""
	servers = frappe.get_all(
		"Database Server",
		filters={"status": ["in", ["Active", "Pending", "Stopped"]]},
		fields=["name", "status"],
		order_by="creation asc",
		limit=1,
	)

	if servers:
		server = servers[0]
		if server.status == "Stopped":
			start_database_server(server.name)
		elif server.status == "Pending":
			setup_database_server(server.name)
		return server.name

	# No server exists — create one with defaults
	doc = frappe.get_doc(
		{
			"doctype": "Database Server",
			"container_name": "benchpress-mariadb",
			"mariadb_version": "10.6",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	setup_database_server(doc.name)
	return doc.name


def create_mariadb_user(
	db_server_name: str, site_name: str, database: str | None = None
) -> tuple[str, str, str]:
	"""Create a temporary limited MariaDB user for bench new-site.
	Follows agent/bench.py:263-278 exactly.

	Returns (database, temp_user, temp_password).
	"""
	database = database or get_database_name(site_name)
	user = f"{database}_limited"
	password = _random_string(16)
	queries = [
		f"CREATE OR REPLACE USER '{user}'@'%' IDENTIFIED BY '{password}'",
		f"CREATE OR REPLACE DATABASE `{user}`",
		f"GRANT ALL ON `{user}`.* TO '{user}'@'%'",
		f"GRANT RELOAD, CREATE USER ON *.* TO '{user}'@'%'",
		f"GRANT ALL ON `{database}`.* TO '{user}'@'%' WITH GRANT OPTION",
		"FLUSH PRIVILEGES",
	]
	for query in queries:
		exit_code, output = execute_sql(db_server_name, query)
		if exit_code != 0:
			frappe.throw(f"Failed to create temp user: {output}")
	return database, user, password


def drop_mariadb_user(db_server_name: str, site_name: str, database: str | None = None) -> None:
	"""Drop temporary limited MariaDB user after bench new-site.
	Follows agent/bench.py:280-290 exactly.
	"""
	database = database or get_database_name(site_name)
	user = f"{database}_limited"
	queries = [
		f"DROP DATABASE IF EXISTS `{user}`",
		f"DROP USER IF EXISTS '{user}'@'%'",
		"FLUSH PRIVILEGES",
	]
	for query in queries:
		execute_sql(db_server_name, query)


def drop_site_database(db_server_name: str, site_name: str) -> None:
	"""Drop site database and user when a bench/site is deleted."""
	db_name = get_database_name(site_name)
	queries = [
		f"DROP DATABASE IF EXISTS `{db_name}`",
		f"DROP USER IF EXISTS '{db_name}'@'%'",
		"FLUSH PRIVILEGES",
	]
	for query in queries:
		execute_sql(db_server_name, query)


def check_mariadb_health(db_server_name: str) -> bool:
	"""Check if MariaDB is responding."""
	try:
		exit_code, _ = execute_sql(db_server_name, "SELECT 1")
		return exit_code == 0
	except Exception:
		return False


def wait_for_mariadb(
	db_server_name: str = "",
	timeout: int = 60,
	container=None,
	root_pw: str = "",
) -> None:
	"""Poll until MariaDB is ready. Raise on timeout."""
	if container and root_pw:
		for _ in range(timeout // 2):
			exit_code, _ = container.exec_run(
				cmd=["mariadb", "-u", "root", f"-p{root_pw}", "-e", "SELECT 1"],
			)
			if exit_code == 0:
				return
			time.sleep(2)
		raise Exception(f"MariaDB not ready after {timeout}s")

	for _ in range(timeout // 2):
		if check_mariadb_health(db_server_name):
			return
		time.sleep(2)
	raise Exception(f"MariaDB not ready after {timeout}s")


def get_container_logs(db_server_name: str, tail: int = 100) -> str:
	"""Return recent container logs."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	return container.logs(tail=tail).decode("utf-8", errors="replace")


def scheduled_health_check():
	"""Cron job — check all active DB servers, attempt restart if down."""
	servers = frappe.get_all(
		"Database Server",
		filters={"status": ["in", ["Active", "Error"]]},
		fields=["name"],
	)
	for s in servers:
		try:
			if not check_mariadb_health(s.name):
				start_database_server(s.name)
				if not check_mariadb_health(s.name):
					db = frappe.get_doc("Database Server", s.name)
					db.set_error("Health check failed after restart attempt")
					frappe.publish_realtime("mariadb_health_failure", {"server": s.name})
		except Exception:
			frappe.log_error(
				title=f"MariaDB health check failed: {s.name}",
				message=frappe.get_traceback(),
			)


def backup_database_server(db_server_name: str, output_path: str = "/var/lib/mysql/backups") -> str:
	"""Full backup via mariadb-dump, gzipped. Returns backup filename."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	root_pw = db_server.get_root_password()

	timestamp = frappe.utils.now().replace(" ", "_").replace(":", "-")
	backup_file = f"{output_path}/all_databases_{timestamp}.sql.gz"

	container.exec_run(cmd=["mkdir", "-p", output_path])
	exit_code, output = container.exec_run(
		cmd=[
			"bash",
			"-c",
			f"mariadb-dump -u root -p'{root_pw}' --all-databases | gzip > {backup_file}",
		],
	)
	if exit_code != 0:
		frappe.throw(f"Backup failed: {output.decode()}")
	return backup_file


def cleanup_old_backups(
	db_server_name: str, keep: int = 7, output_path: str = "/var/lib/mysql/backups"
) -> None:
	"""Retain only the last `keep` backups."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	container.exec_run(
		cmd=[
			"bash",
			"-c",
			f"ls -t {output_path}/*.sql.gz 2>/dev/null | tail -n +{keep + 1} | xargs rm -f",
		],
	)


def scheduled_backup():
	"""Cron job — nightly backup with 7-day retention."""
	servers = frappe.get_all("Database Server", filters={"status": "Active"}, fields=["name"])
	for s in servers:
		try:
			backup_database_server(s.name)
			cleanup_old_backups(s.name, keep=7)
		except Exception:
			frappe.log_error(
				title=f"MariaDB backup failed: {s.name}",
				message=frappe.get_traceback(),
			)
