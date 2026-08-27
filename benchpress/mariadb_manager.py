# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64
import hashlib
import io
import os
import secrets
import subprocess
import tarfile
import time
from pathlib import Path

import frappe
from frappe import _

from benchpress.docker_manager import ensure_network, get_client

BACKUP_TIMEOUT = 3600

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
	"""Execute SQL on the MariaDB container, piped in base64 so nothing is shell-interpolated.

	One `docker exec`, not three: a round trip costs over a hundred milliseconds, and site
	creation makes several of these calls inside a step this app measures in seconds. Piping
	also leaves no temp file to clean up on the failure path.
	"""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)

	encoded = base64.b64encode(sql.encode()).decode()
	exit_code, output = container.exec_run(
		cmd=["bash", "-c", f"echo '{encoded}' | base64 -d | mariadb -u root"],
		environment={"MYSQL_PWD": db_server.get_root_password()},
	)
	return exit_code, output.decode("utf-8", errors="replace")


def _script(*statements: str) -> str:
	"""Several statements as one `execute_sql`, so a sequence costs one round trip and not one each."""
	return ";\n".join(statements) + ";\n"


def _native_password_hash(password: str) -> str:
	"""MariaDB's own `mysql_native_password` hash: `*` and SHA1(SHA1(password)) in upper hex.

	Safe to publish, which is the whole point of using it. The server hashes what a client
	sends once more before comparing, so a client presenting this value is refused.
	"""
	return "*" + hashlib.sha1(hashlib.sha1(password.encode()).digest()).hexdigest().upper()


def _write_env_file(root_password: str, version: str = "10.6", mem_limit: str = "1g") -> None:
	"""Write .env file for docker compose in the config directory."""
	env_path = os.path.join(_get_config_dir(), ".env")
	with open(env_path, "w") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
		f.write(f"MARIADB_ROOT_PASSWORD={root_password}\n")
		f.write(f"MARIADB_VERSION={version}\n")
		f.write(f"MARIADB_MEM_LIMIT={mem_limit}\n")


def _write_mariadb_config(custom_config: str | None = None) -> None:
	"""Write MariaDB config to persistent path (not /tmp/)."""
	config_path = os.path.join(_get_config_dir(), "mariadb.cnf")
	with open(config_path, "w") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
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
		client = get_client()
		ensure_network(client)

		# Ensure named volume exists (marked external in compose)
		try:
			client.volumes.get(db_server.volume_name or "benchpress-mariadb-data")
		except Exception:
			client.volumes.create(name=db_server.volume_name or "benchpress-mariadb-data")

		# Remove existing container if any (clean slate for compose)
		try:
			old = client.containers.get(db_server.container_name)
			old.remove(force=True)
		except Exception:
			pass  # best-effort

		exit_code, output = _compose_cmd("up", "-d", "mariadb")
		if exit_code != 0:
			raise Exception(f"docker compose up failed: {output}")

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
	exit_code, output = execute_sql(
		db_server_name,
		_script(
			# The hash, not the plaintext: `execute_sql` puts this script on a `docker exec`
			# command line, and Docker publishes every one of those into its event stream.
			f"CREATE OR REPLACE USER '{user}'@'%' "
			f"IDENTIFIED VIA mysql_native_password USING '{_native_password_hash(password)}'",
			f"CREATE OR REPLACE DATABASE `{user}`",
			f"GRANT ALL ON `{user}`.* TO '{user}'@'%'",
			f"GRANT RELOAD, CREATE USER ON *.* TO '{user}'@'%'",
			f"GRANT ALL ON `{database}`.* TO '{user}'@'%' WITH GRANT OPTION",
			"FLUSH PRIVILEGES",
		),
	)
	if exit_code != 0:
		frappe.throw(_("Failed to create temp user: {0}").format(output))
	return database, user, password


def drop_mariadb_user(db_server_name: str, site_name: str, database: str | None = None) -> None:
	"""Drop temporary limited MariaDB user after bench new-site.
	Follows agent/bench.py:280-290 exactly.
	"""
	database = database or get_database_name(site_name)
	user = f"{database}_limited"
	execute_sql(
		db_server_name,
		_script(
			f"DROP DATABASE IF EXISTS `{user}`",
			f"DROP USER IF EXISTS '{user}'@'%'",
			"FLUSH PRIVILEGES",
		),
	)


def drop_site_database(db_server_name: str, site_name: str, database: str | None = None) -> None:
	"""Drop site database and user when a bench/site is deleted.

	`database` overrides the name derived from the site, for a caller that chose its own.
	"""
	db_name = database or get_database_name(site_name)
	execute_sql(
		db_server_name,
		_script(
			f"DROP DATABASE IF EXISTS `{db_name}`",
			f"DROP USER IF EXISTS '{db_name}'@'%'",
			"FLUSH PRIVILEGES",
		),
	)


def server_version(db_server_name: str) -> str:
	"""The server's own `SELECT VERSION()`, or empty when it cannot be read.

	Empty rather than a raise: the caller compares this with the version a golden dump was taken
	from, and its safe direction is to create the site instead of restoring into a server it
	could not identify.
	"""
	try:
		exit_code, output = execute_sql(db_server_name, "SELECT VERSION()")
	except Exception:
		return ""
	if exit_code != 0:
		return ""
	# Last line first: the client prints its own deprecation warning into the same stream.
	return next((line.strip() for line in reversed(output.splitlines()) if line[:1].isdigit()), "")


def check_mariadb_health(db_server_name: str) -> bool:
	"""Check if MariaDB is responding."""
	try:
		exit_code, _output = execute_sql(db_server_name, "SELECT 1")
		return exit_code == 0
	except Exception:
		return False  # best-effort


PASSWORD_MISMATCH_MSG = (
	"MariaDB root password mismatch: the data volume was initialized with a "
	"different password than the one in the Database Server doc. Remove the "
	"volume (docker volume rm benchpress-mariadb-data) and re-run setup to "
	"reinitialize, or update the doc password to match the volume."
)


def _detect_password_mismatch(container) -> bool:
	try:
		logs = container.logs(tail=50).decode("utf-8", errors="replace")
		return logs.count("Access denied for user 'root'") >= 3
	except Exception:
		return False  # best-effort


def _resolve_poll_container(db_server_name: str):
	try:
		db_server = frappe.get_doc("Database Server", db_server_name)
		return get_client().containers.get(db_server.container_name)
	except Exception:
		return None  # best-effort


def wait_for_mariadb(
	db_server_name: str = "",
	timeout: int = 60,
	container=None,
	root_pw: str = "",
) -> None:
	direct = bool(container and root_pw)
	poll_container = container if direct else None
	for _attempt in range(timeout // 2):
		if direct:
			exit_code, _output = container.exec_run(
				cmd=["mariadb", "-u", "root", "-e", "SELECT 1"],
				environment={"MYSQL_PWD": root_pw},
			)
			healthy = exit_code == 0
		else:
			healthy = check_mariadb_health(db_server_name)
		if healthy:
			return
		if poll_container is None and db_server_name:
			poll_container = _resolve_poll_container(db_server_name)
		if poll_container and _detect_password_mismatch(poll_container):
			raise Exception(PASSWORD_MISMATCH_MSG)
		time.sleep(2)
	raise Exception(f"MariaDB not ready after {timeout}s")


def get_container_logs(db_server_name: str, tail: int = 100) -> str:
	"""Return recent container logs."""
	db_server = frappe.get_doc("Database Server", db_server_name)
	client = get_client()
	container = client.containers.get(db_server.container_id)
	return container.logs(tail=tail).decode("utf-8", errors="replace")


def enqueue_health_check() -> None:
	"""Convergence cron: hand the health check to `queue-long`."""
	# The enqueuer, never `scheduled_health_check` itself — see the rule above `scheduler_events`
	# in `hooks.py`.
	frappe.enqueue(
		"benchpress.mariadb_manager.scheduled_health_check",
		queue="long",
		job_id="mariadb_health_check",
		deduplicate=True,
	)


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


def _host_backup_dir() -> str:
	return frappe.get_site_path("private", "backups", "mariadb")


def _pull_backup_to_host(container, backup_file: str) -> str:
	"""Copy an in-container dump to the site's private backup dir. Returns host path."""
	# ponytail: whole dump buffered in RAM; stream the tar (mode="r|") if dumps outgrow worker memory.
	stream, _stat = container.get_archive(backup_file)
	buffer = io.BytesIO(b"".join(stream))
	host_dir = _host_backup_dir()
	os.makedirs(host_dir, exist_ok=True)
	host_path = os.path.join(host_dir, os.path.basename(backup_file))
	with tarfile.open(fileobj=buffer) as tar:
		member = tar.extractfile(tar.getmembers()[0])
		# Safe: host_dir is the fixed site backup path, filename passed through basename().
		with open(host_path, "wb") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
			f.write(member.read())
	return host_path


def backup_database_server(db_server_name: str, output_path: str = "/var/lib/mysql/backups") -> str:
	"""Full backup via mariadb-dump, gzipped, pulled to host disk.

	Returns the host path; on pull failure returns the in-container path (dump kept as fallback).
	"""
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
			f"mariadb-dump -u root --all-databases | gzip > {backup_file}",
		],
		environment={"MYSQL_PWD": root_pw},
	)
	if exit_code != 0:
		frappe.throw(_("Backup failed: {0}").format(output.decode()))
	try:
		host_path = _pull_backup_to_host(container, backup_file)
	except Exception:
		frappe.log_error(
			title=f"Backup host copy failed: {db_server_name}",
			message=frappe.get_traceback(),
		)
		return backup_file
	container.exec_run(cmd=["rm", "-f", backup_file])
	return host_path


def cleanup_old_backups(
	db_server_name: str, keep: int = 7, output_path: str = "/var/lib/mysql/backups"
) -> None:
	"""Retain only the last `keep` backups on host disk; container prune catches failed-pull leftovers."""
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
	dumps = sorted(Path(_host_backup_dir()).glob("*.sql.gz"), key=lambda p: p.stat().st_mtime)
	for old in dumps[:-keep]:
		old.unlink()


def restore_database_server(db_server_name: str, backup_file: str) -> None:
	"""DESTRUCTIVE: overwrites ALL databases in the target container with a host-side dump.

	Scratch/recovery use only — never point this at a live tenant DB server.
	Not whitelisted on purpose; run it from `bench console`.
	See docs/database-backup-restore.md for the full runbook.
	"""
	db_server = frappe.get_doc("Database Server", db_server_name)
	container = get_client().containers.get(db_server.container_id)
	root_pw = db_server.get_root_password()

	dump_name = os.path.basename(backup_file)
	buffer = io.BytesIO()
	with tarfile.open(fileobj=buffer, mode="w") as tar:
		tar.add(backup_file, arcname=dump_name)
	container.put_archive("/tmp", buffer.getvalue())
	try:
		exit_code, output = container.exec_run(
			cmd=["bash", "-c", f"gunzip -c /tmp/{dump_name} | mariadb -u root"],
			environment={"MYSQL_PWD": root_pw},
		)
	finally:
		container.exec_run(cmd=["rm", "-f", f"/tmp/{dump_name}"])
	if exit_code != 0:
		frappe.throw(_("Restore failed: {0}").format(output.decode()))


def enqueue_backup() -> None:
	"""Nightly cron: hand the dump to `queue-long`."""
	# The enqueuer, never `scheduled_backup` itself — see the rule above `scheduler_events` in
	# `hooks.py`. The dump is buffered in worker memory, so it gets its own timeout rather than
	# the queue default: this is every tenant's site database in one file.
	frappe.enqueue(
		"benchpress.mariadb_manager.scheduled_backup",
		queue="long",
		timeout=BACKUP_TIMEOUT,
		job_id="mariadb_backup",
		deduplicate=True,
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
	ensure_network()
	exit_code, output = _compose_cmd("up", "-d", "redis")
	if exit_code != 0:
		raise Exception(f"docker compose up redis failed: {output}")


def ensure_infrastructure() -> str:
	"""Ensure both MariaDB and Redis shared containers are running.
	Returns the Database Server doc name.
	"""
	setup_redis()
	return ensure_database_server()
