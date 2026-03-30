# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64
import hashlib
import os
import secrets
import subprocess
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


def _get_config_dir() -> str:
	return os.path.join(frappe.get_app_path("benchpress"), "config")


def _get_compose_path() -> str:
	return os.path.join(_get_config_dir(), "docker-compose.yml")


def _ensure_network() -> None:
	"""Create the benchpress Docker network if it does not exist."""
	client = get_client()
	try:
		client.networks.get("benchpress")
	except Exception:
		import docker

		client.networks.create(
			"benchpress",
			driver="bridge",
			ipam=docker.types.IPAMConfig(pool_configs=[docker.types.IPAMPool(subnet="172.30.0.0/24")]),
		)


def _compose_cmd(*args: str) -> tuple[int, str]:
	"""Run docker compose command in the config directory."""
	cmd = ["docker", "compose", "-f", _get_compose_path(), *args]
	result = subprocess.run(cmd, capture_output=True, text=True, cwd=_get_config_dir())
	output = result.stdout + result.stderr
	return result.returncode, output


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


def _write_env_file(root_password: str, version: str = "10.6", mem_limit: str = "1g") -> None:
	"""Write .env file for docker compose in the config directory."""
	env_path = os.path.join(_get_config_dir(), ".env")
	with open(env_path, "w") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		f.write(f"MARIADB_ROOT_PASSWORD={root_password}\n")
		f.write(f"MARIADB_VERSION={version}\n")
		f.write(f"MARIADB_MEM_LIMIT={mem_limit}\n")


def _write_mariadb_config(custom_config: str | None = None) -> None:
	"""Write MariaDB config to persistent path (not /tmp/)."""
	config_path = os.path.join(_get_config_dir(), "mariadb.cnf")
	with open(config_path, "w") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		f.write(custom_config or DEFAULT_MARIADB_CONFIG)


def setup_database_server(db_server_name: str) -> None:
	"""Full setup: write config, bring up MariaDB via docker compose, wait for ready."""
	db_server = frappe.get_doc("Database Server", db_server_name)

	try:
		root_password = db_server.get_root_password()
		version = (db_server.mariadb_version or "10.6").strip()
		mem_limit = db_server.memory_limit or "1g"

		_write_mariadb_config(db_server.custom_config)
		_write_env_file(root_password, version, mem_limit)
		_ensure_network()

		# Ensure named volume exists (marked external in compose)
		client = get_client()
		try:
			client.volumes.get(db_server.volume_name or "benchpress-mariadb-data")
		except Exception:
			client.volumes.create(name=db_server.volume_name or "benchpress-mariadb-data")

		# Remove existing container if any (clean slate for compose)
		try:
			client = get_client()
			old = client.containers.get(db_server.container_name)
			old.remove(force=True)
		except Exception:
			pass

		exit_code, output = _compose_cmd("up", "-d", "mariadb")
		if exit_code != 0:
			raise Exception(f"docker compose up failed: {output}")

		client = get_client()
		container = client.containers.get(db_server.container_name)
		wait_for_mariadb(db_server_name, container=container, root_pw=root_password, timeout=60)

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
	"""Start a stopped MariaDB container via docker compose."""
	db_server = frappe.get_doc("Database Server", db_server_name)

	exit_code, output = _compose_cmd("start", "mariadb")
	if exit_code != 0:
		raise Exception(f"docker compose start failed: {output}")

	client = get_client()
	container = client.containers.get(db_server.container_name)
	db_server.container_id = container.id
	db_server.status = "Active"
	db_server.save(ignore_permissions=True)
	frappe.db.commit()


def stop_database_server(db_server_name: str) -> None:
	"""Stop the MariaDB container via docker compose."""
	_compose_cmd("stop", "mariadb")

	db_server = frappe.get_doc("Database Server", db_server_name)
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


def setup_redis() -> None:
	"""Bring up shared Redis container via docker compose."""
	_ensure_network()
	exit_code, output = _compose_cmd("up", "-d", "redis")
	if exit_code != 0:
		raise Exception(f"docker compose up redis failed: {output}")


def ensure_infrastructure() -> str:
	"""Ensure both MariaDB and Redis shared containers are running.
	Returns the Database Server doc name.
	"""
	setup_redis()
	return ensure_database_server()
