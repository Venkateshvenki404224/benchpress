# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import base64
import hashlib
import io
import os
import tarfile
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase


def _sql_sent(container):
	"""The SQL a mocked `execute_sql` piped in, decoded back out of the base64 on its command line."""
	command = " ".join(container.exec_run.call_args_list[0].kwargs["cmd"])
	return base64.b64decode(command.split("'")[1]).decode()


class TestMariadbManager(IntegrationTestCase):
	def test_get_database_name_returns_sha1_prefix(self):
		from benchpress.mariadb_manager import get_database_name

		site = "mysite.localhost"
		name = get_database_name(site)
		expected = "_" + hashlib.sha1(site.encode()).hexdigest()[:16]
		self.assertEqual(name, expected)

	def test_get_database_name_is_deterministic(self):
		from benchpress.mariadb_manager import get_database_name

		self.assertEqual(
			get_database_name("a.localhost"),
			get_database_name("a.localhost"),
		)

	def test_get_database_name_max_17_chars(self):
		from benchpress.mariadb_manager import get_database_name

		# _ + 16 hex = 17 chars
		name = get_database_name("any.site.localhost")
		self.assertEqual(len(name), 17)
		self.assertTrue(name.startswith("_"))

	def test_get_database_name_differs_for_different_sites(self):
		from benchpress.mariadb_manager import get_database_name

		self.assertNotEqual(
			get_database_name("site-a.localhost"),
			get_database_name("site-b.localhost"),
		)

	def _make_mock_db_server(self, container_id="ctr-abc", container_name="benchpress-mariadb"):
		db_server = MagicMock()
		db_server.container_id = container_id
		db_server.container_name = container_name
		db_server.get_root_password.return_value = "rootpw"
		return db_server

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_execute_sql_resolves_the_container_by_name_not_id(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import execute_sql

		mock_get_doc.return_value = self._make_mock_db_server(container_id="stale-id")
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"ok")
		mock_get_client.return_value.containers.get.return_value = mock_container

		execute_sql("db-server-name", "SELECT 1")

		looked_up = mock_get_client.return_value.containers.get.call_args.args[0]
		self.assertEqual(looked_up, "benchpress-mariadb")
		self.assertNotEqual(looked_up, "stale-id")

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_execute_sql_encodes_sql_with_base64(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import execute_sql

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"ok")
		mock_get_client.return_value.containers.get.return_value = mock_container

		execute_sql("db-server-name", "SELECT 1")

		call = mock_container.exec_run.call_args_list[0]
		cmd_str = " ".join(call.kwargs.get("cmd") or call.args[0])
		self.assertIn("base64 -d", cmd_str)
		self.assertNotIn("SELECT 1", cmd_str)

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_execute_sql_is_one_round_trip_and_leaves_no_temp_file(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import execute_sql

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"ok")
		mock_get_client.return_value.containers.get.return_value = mock_container

		execute_sql("db-server-name", "DROP TABLE important")

		self.assertEqual(mock_container.exec_run.call_count, 1)
		call = mock_container.exec_run.call_args_list[0]
		self.assertNotIn("/tmp/", " ".join(call.kwargs.get("cmd") or call.args[0]))

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_execute_sql_passes_password_via_env_not_argv(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import execute_sql

		sentinel = "S3cret!pw"
		db_server = self._make_mock_db_server()
		db_server.get_root_password.return_value = sentinel
		mock_get_doc.return_value = db_server
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"ok")
		mock_get_client.return_value.containers.get.return_value = mock_container

		execute_sql("db-server-name", "SELECT 1")

		sql_call = mock_container.exec_run.call_args_list[0]
		self.assertEqual(sql_call.kwargs.get("environment"), {"MYSQL_PWD": sentinel})
		for call in mock_container.exec_run.call_args_list:
			cmd = call.kwargs.get("cmd") or call.args[0]
			self.assertNotIn(sentinel, " ".join(cmd))

	@patch("benchpress.mariadb_manager._pull_backup_to_host", return_value="/tmp/dump.sql.gz")
	@patch("benchpress.mariadb_manager.frappe.utils.now", return_value="2026-01-01 00:00:00")
	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_backup_passes_password_via_env_not_argv(
		self, mock_get_doc, mock_get_client, mock_now, mock_pull
	):
		from benchpress.mariadb_manager import backup_database_server

		sentinel = "S3cret!pw"
		db_server = self._make_mock_db_server()
		db_server.get_root_password.return_value = sentinel
		mock_get_doc.return_value = db_server
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_get_client.return_value.containers.get.return_value = mock_container

		backup_database_server("db-server-name")

		dump_call = mock_container.exec_run.call_args_list[1]
		self.assertEqual(dump_call.kwargs.get("environment"), {"MYSQL_PWD": sentinel})
		for call in mock_container.exec_run.call_args_list:
			cmd = call.kwargs.get("cmd") or call.args[0]
			self.assertNotIn(sentinel, " ".join(cmd))

	@patch("benchpress.mariadb_manager._random_string")
	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_create_user_sends_the_hash_and_never_the_plaintext(
		self, mock_get_doc, mock_get_client, mock_random
	):
		"""`execute_sql` puts its script on an exec command line, so the plaintext cannot be in it."""
		from benchpress.mariadb_manager import _native_password_hash, create_mariadb_user

		sentinel = "nOtAr3alUs3rPassw0rd"
		mock_random.return_value = sentinel
		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_get_client.return_value.containers.get.return_value = mock_container

		_, _, password = create_mariadb_user("db-server-name", "mysite.localhost")

		self.assertEqual(password, sentinel)
		sql = _sql_sent(mock_container)
		self.assertIn(_native_password_hash(sentinel), sql)
		self.assertNotIn(sentinel, sql)

	def test_the_native_hash_is_not_the_password(self):
		"""The control: a hash that carried the plaintext would pass the test above."""
		from benchpress.mariadb_manager import _native_password_hash

		sentinel = "nOtAr3alUs3rPassw0rd"

		native = _native_password_hash(sentinel)

		self.assertNotIn(sentinel, native)
		self.assertRegex(native, r"^\*[0-9A-F]{40}$")

	def _make_backup_tar(self, name, data):
		buffer = io.BytesIO()
		with tarfile.open(fileobj=buffer, mode="w") as tar:
			info = tarfile.TarInfo(name=name)
			info.size = len(data)
			tar.addfile(info, io.BytesIO(data))
		return buffer.getvalue()

	@patch("benchpress.mariadb_manager.frappe.get_site_path")
	@patch("benchpress.mariadb_manager.frappe.utils.now", return_value="2026-01-01 00:00:00")
	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_backup_pulls_dump_to_host_and_removes_container_file(
		self, mock_get_doc, mock_get_client, mock_now, mock_site_path
	):
		from benchpress.mariadb_manager import backup_database_server

		mock_get_doc.return_value = self._make_mock_db_server()
		dump_name = "all_databases_2026-01-01_00-00-00.sql.gz"
		dump_bytes = b"fake gzip bytes"
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_container.get_archive.return_value = (iter([self._make_backup_tar(dump_name, dump_bytes)]), {})
		mock_get_client.return_value.containers.get.return_value = mock_container

		with tempfile.TemporaryDirectory() as tmp:
			mock_site_path.side_effect = lambda *parts: os.path.join(tmp, *parts)
			host_path = backup_database_server("db-server-name")

			self.assertEqual(host_path, os.path.join(tmp, "private", "backups", "mariadb", dump_name))
			with open(host_path, "rb") as f:
				self.assertEqual(f.read(), dump_bytes)

		rm_cmd = ["rm", "-f", f"/var/lib/mysql/backups/{dump_name}"]
		cmds = [c.kwargs.get("cmd") or c.args[0] for c in mock_container.exec_run.call_args_list]
		self.assertIn(rm_cmd, cmds)

	@patch("benchpress.mariadb_manager.frappe.log_error")
	@patch("benchpress.mariadb_manager.frappe.utils.now", return_value="2026-01-01 00:00:00")
	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_backup_keeps_container_file_when_pull_fails(
		self, mock_get_doc, mock_get_client, mock_now, mock_log_error
	):
		from benchpress.mariadb_manager import backup_database_server

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_container.get_archive.side_effect = RuntimeError("stream broke")
		mock_get_client.return_value.containers.get.return_value = mock_container

		result = backup_database_server("db-server-name")

		self.assertEqual(result, "/var/lib/mysql/backups/all_databases_2026-01-01_00-00-00.sql.gz")
		mock_log_error.assert_called_once()
		for call in mock_container.exec_run.call_args_list:
			cmd = call.kwargs.get("cmd") or call.args[0]
			self.assertNotEqual(cmd[:2], ["rm", "-f"])

	@patch("benchpress.mariadb_manager.frappe.get_site_path")
	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_cleanup_prunes_host_dir_and_still_prunes_container(
		self, mock_get_doc, mock_get_client, mock_site_path
	):
		from benchpress.mariadb_manager import cleanup_old_backups

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_get_client.return_value.containers.get.return_value = mock_container

		with tempfile.TemporaryDirectory() as tmp:
			mock_site_path.side_effect = lambda *parts: os.path.join(tmp, *parts)
			host_dir = os.path.join(tmp, "private", "backups", "mariadb")
			os.makedirs(host_dir)
			for i in range(10):
				path = os.path.join(host_dir, f"all_databases_{i}.sql.gz")
				open(path, "wb").close()
				os.utime(path, (i, i))

			cleanup_old_backups("db-server-name", keep=7)

			survivors = sorted(os.listdir(host_dir))
			self.assertEqual(survivors, [f"all_databases_{i}.sql.gz" for i in range(3, 10)])

		container_cmd = mock_container.exec_run.call_args_list[0].kwargs["cmd"]
		self.assertIn("ls -t /var/lib/mysql/backups/*.sql.gz", container_cmd[2])
		self.assertIn("xargs rm -f", container_cmd[2])

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_restore_pushes_dump_and_passes_password_via_env_not_argv(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import restore_database_server

		sentinel = "S3cret!pw"
		db_server = self._make_mock_db_server()
		db_server.get_root_password.return_value = sentinel
		mock_get_doc.return_value = db_server
		mock_container = MagicMock()
		mock_container.exec_run.return_value = (0, b"")
		mock_get_client.return_value.containers.get.return_value = mock_container

		dump_bytes = b"fake gzip bytes"
		with tempfile.NamedTemporaryFile(suffix=".sql.gz") as f:
			f.write(dump_bytes)
			f.flush()
			dump_name = os.path.basename(f.name)
			restore_database_server("db-server-name", f.name)

		dest, tar_bytes = mock_container.put_archive.call_args.args
		self.assertEqual(dest, "/tmp")
		with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
			self.assertEqual(tar.extractfile(dump_name).read(), dump_bytes)

		restore_call = mock_container.exec_run.call_args_list[0]
		self.assertEqual(restore_call.kwargs.get("environment"), {"MYSQL_PWD": sentinel})
		self.assertIn(f"gunzip -c /tmp/{dump_name} | mariadb -u root", restore_call.kwargs["cmd"][2])
		for call in mock_container.exec_run.call_args_list:
			cmd = call.kwargs.get("cmd") or call.args[0]
			self.assertNotIn(sentinel, " ".join(cmd))

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_restore_throws_on_nonzero_exit_and_cleans_tmp(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import restore_database_server

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		mock_container.exec_run.side_effect = [(1, b"ERROR 1064"), (0, b"")]
		mock_get_client.return_value.containers.get.return_value = mock_container

		with tempfile.NamedTemporaryFile(suffix=".sql.gz") as f:
			f.write(b"x")
			f.flush()
			with self.assertRaises(frappe.ValidationError):
				restore_database_server("db-server-name", f.name)

		last_call = mock_container.exec_run.call_args_list[-1]
		cmd = last_call.kwargs.get("cmd") or last_call.args[0]
		self.assertEqual(cmd[:2], ["rm", "-f"])

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_create_mariadb_user_returns_db_name_user_pass(self, mock_exec):
		from benchpress.mariadb_manager import create_mariadb_user, get_database_name

		mock_exec.return_value = (0, "")
		db_name, user, password = create_mariadb_user("db-server", "site.localhost")

		self.assertEqual(db_name, get_database_name("site.localhost"))
		self.assertEqual(user, f"{db_name}_limited")
		self.assertIsInstance(password, str)
		self.assertGreater(len(password), 8)

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_create_mariadb_user_throws_on_sql_failure(self, mock_exec):
		from benchpress.mariadb_manager import create_mariadb_user

		mock_exec.return_value = (1, "Access denied")
		with self.assertRaises(frappe.ValidationError):
			create_mariadb_user("db-server", "site.localhost")

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_create_mariadb_user_runs_grant_queries(self, mock_exec):
		from benchpress.mariadb_manager import create_mariadb_user

		mock_exec.return_value = (0, "")
		create_mariadb_user("db-server", "site.localhost")

		sqls = [str(c) for c in mock_exec.call_args_list]
		combined = " ".join(sqls)
		self.assertIn("GRANT", combined)
		self.assertIn("FLUSH PRIVILEGES", combined)

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_drop_mariadb_user_runs_drop_queries(self, mock_exec):
		from benchpress.mariadb_manager import drop_mariadb_user

		mock_exec.return_value = (0, "")
		drop_mariadb_user("db-server", "site.localhost")

		sqls = [str(c) for c in mock_exec.call_args_list]
		combined = " ".join(sqls)
		self.assertIn("DROP DATABASE", combined)
		self.assertIn("DROP USER", combined)
		self.assertIn("FLUSH PRIVILEGES", combined)

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_drop_site_database_drops_db_and_user(self, mock_exec):
		from benchpress.mariadb_manager import drop_site_database, get_database_name

		mock_exec.return_value = (0, "")
		drop_site_database("db-server", "mysite.localhost")

		db_name = get_database_name("mysite.localhost")
		sqls = [str(c) for c in mock_exec.call_args_list]
		combined = " ".join(sqls)
		self.assertIn(db_name, combined)
		self.assertIn("DROP DATABASE", combined)
		self.assertIn("DROP USER", combined)

	# --- ensure_database_server -------------------------------------------------------------

	@contextmanager
	def _only_servers(self, *rows):
		"""Make `tabDatabase Server` hold exactly `rows` for the body, then put it back."""
		# `ensure_database_server` commits, and this site's one real server row has to survive a
		# case that needs the table empty — so the whole thing runs inside a savepoint with
		# `commit` neutered, rather than trusting the class rollback.
		database = type(frappe.local.db)
		frappe.db.savepoint("ensure_database_server_test")
		try:
			with patch.object(database, "commit"):
				frappe.db.delete("Database Server")
				yield [
					frappe.get_doc({"doctype": "Database Server", **row}).insert(ignore_permissions=True)
					for row in rows
				]
		finally:
			try:
				frappe.db.rollback(save_point="ensure_database_server_test")
			except Exception:
				# A statement that errored can take the savepoint with it, and a half-undone
				# `delete` here would drop this site's real server row for good.
				frappe.db.rollback()

	@contextmanager
	def _ensuring(self, healthy=True):
		"""Run `ensure_database_server` with every container call mocked. Yields the three mocks."""
		with (
			patch("benchpress.mariadb_manager.setup_database_server") as setup,
			patch("benchpress.mariadb_manager.start_database_server") as start,
			patch("benchpress.mariadb_manager.check_mariadb_health", return_value=healthy) as health,
		):
			yield setup, start, health

	def _server_count(self):
		return frappe.db.count("Database Server")

	def test_a_server_row_in_error_is_the_server_not_a_missing_one(self):
		"""The live failure: `Error` fell outside the status filter, so the deploy tried to insert a
		second row and died on the UNIQUE index over container_name."""
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers(
			{"container_name": DEFAULT_CONTAINER_NAME, "status": "Error", "error_message": "stale"}
		) as (existing,):
			with self._ensuring(healthy=True) as (setup, _start, _health):
				name = ensure_database_server()

			self.assertEqual(name, existing.name)
			self.assertEqual(self._server_count(), 1)
			setup.assert_not_called()
			self.assertEqual(frappe.db.get_value("Database Server", name, "status"), "Active")
			self.assertFalse(frappe.db.get_value("Database Server", name, "error_message"))

	def test_an_error_row_that_answers_is_never_re_created_under_the_running_benches(self):
		"""`setup_database_server` force-removes the container every live bench is connected to, so a
		healthy server costs one status flip and nothing else."""
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Error"}):
			with self._ensuring(healthy=True) as (setup, _start, health):
				ensure_database_server()

			setup.assert_not_called()
			health.assert_called_once()

	def test_an_error_row_that_does_not_answer_is_set_up_again(self):
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Error"}) as (existing,):
			with self._ensuring(healthy=False) as (setup, _start, _health):
				name = ensure_database_server()

			setup.assert_called_once_with(existing.name)
			self.assertEqual(name, existing.name)
			self.assertEqual(self._server_count(), 1)

	def test_a_stopped_row_is_started_not_set_up(self):
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Stopped"}) as (
			existing,
		):
			with self._ensuring() as (setup, start, _health):
				ensure_database_server()

			start.assert_called_once_with(existing.name)
			setup.assert_not_called()

	def test_a_pending_row_is_set_up(self):
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Pending"}) as (
			existing,
		):
			with self._ensuring() as (setup, _start, _health):
				ensure_database_server()

			setup.assert_called_once_with(existing.name)

	def test_an_active_row_costs_no_container_round_trip(self):
		"""The caller's own `wait_for_mariadb` is the proof; a health check here would sit in front
		of every deploy."""
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Active"}) as (
			existing,
		):
			with self._ensuring() as (setup, start, health):
				name = ensure_database_server()

			self.assertEqual(name, existing.name)
			setup.assert_not_called()
			start.assert_not_called()
			health.assert_not_called()

	def test_a_renamed_container_is_still_the_one_server(self):
		"""A self-hoster who renamed it has one server, not a licence to insert a second."""
		from benchpress.mariadb_manager import ensure_database_server

		with self._only_servers({"container_name": "acme-mariadb", "status": "Error"}) as (existing,):
			with self._ensuring(healthy=True) as (setup, _start, _health):
				name = ensure_database_server()

			self.assertEqual(name, existing.name)
			self.assertEqual(self._server_count(), 1)
			setup.assert_not_called()

	def test_an_empty_table_gets_exactly_one_default_server(self):
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, ensure_database_server

		with self._only_servers():
			with self._ensuring() as (setup, _start, _health):
				name = ensure_database_server()

			self.assertEqual(self._server_count(), 1)
			self.assertEqual(
				frappe.db.get_value("Database Server", name, "container_name"), DEFAULT_CONTAINER_NAME
			)
			setup.assert_called_once_with(name)

	def test_a_losing_racer_returns_the_winner_s_row_rather_than_an_integrity_error(self):
		"""Two deploys reaching an empty table at once: raw, the loser's insert reached the deploy
		log as an IntegrityError naming an index rather than a database."""
		from benchpress.mariadb_manager import DEFAULT_CONTAINER_NAME, _create_default_server

		with self._only_servers({"container_name": DEFAULT_CONTAINER_NAME, "status": "Active"}) as (winner,):
			losing_doc = MagicMock()
			losing_doc.insert.side_effect = frappe.DuplicateEntryError("Database Server", "x", None)
			with (
				patch("benchpress.mariadb_manager.frappe.get_doc", return_value=losing_doc),
				patch.object(type(frappe.local.db), "rollback"),
				self._ensuring() as (setup, start, _health),
			):
				name = _create_default_server()

			self.assertEqual(name, winner.name)
			self.assertEqual(self._server_count(), 1)
			setup.assert_not_called()
			start.assert_not_called()


# What the server answers, batch mode's per-result-set header row included.
LIVE_SETTINGS = "\n".join(
	[
		"Variable_name\tValue",
		"innodb_buffer_pool_size\t134217728",
		"key_buffer_size\t16777216",
		"max_connections\t500",
		"Variable_name\tValue",
		"Innodb_buffer_pool_read_requests\t100000",
		"Innodb_buffer_pool_reads\t60",
	]
)
STOCK_SETTINGS = "\n".join(
	[
		"Variable_name\tValue",
		"innodb_buffer_pool_size\t134217728",
		"key_buffer_size\t134217728",
		"max_connections\t151",
		"Variable_name\tValue",
		"Innodb_buffer_pool_read_requests\t0",
		"Innodb_buffer_pool_reads\t0",
	]
)


class TestSharedSettingDrift(IntegrationTestCase):
	def _redis_answering(self, mock_get_client, payload: bytes):
		container = MagicMock()
		container.exec_run.return_value = (0, payload)
		mock_get_client.return_value.containers.get.return_value = container
		return container

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_a_mariadb_on_the_declared_settings_reports_no_drift(self, mock_execute_sql):
		from benchpress.mariadb_manager import mariadb_drift

		mock_execute_sql.return_value = (0, LIVE_SETTINGS)

		drift, hit_rate = mariadb_drift("db-1")

		self.assertEqual(drift, [])
		self.assertEqual(hit_rate, "99.94%")

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_a_stock_mariadb_names_every_setting_that_disagrees(self, mock_execute_sql):
		from benchpress.mariadb_manager import mariadb_drift

		mock_execute_sql.return_value = (0, STOCK_SETTINGS)

		drift, hit_rate = mariadb_drift("db-1")

		self.assertEqual(
			drift,
			[
				"max_connections is 151, declared 500",
				"key_buffer_size is 134217728, declared 16777216",
			],
		)
		self.assertEqual(hit_rate, "no reads yet")

	@patch("benchpress.mariadb_manager.execute_sql")
	def test_the_drift_read_costs_one_round_trip(self, mock_execute_sql):
		"""It runs on the scheduler every five minutes, so both queries go in one exec."""
		from benchpress.mariadb_manager import mariadb_drift

		mock_execute_sql.return_value = (0, LIVE_SETTINGS)
		mariadb_drift("db-1")

		sql = mock_execute_sql.call_args.args[1]
		self.assertEqual(mock_execute_sql.call_count, 1)
		self.assertIn("SHOW GLOBAL VARIABLES", sql)
		self.assertIn("SHOW GLOBAL STATUS", sql)

	@patch("benchpress.mariadb_manager.get_client")
	def test_a_redis_on_the_declared_settings_reports_no_drift(self, mock_get_client):
		from benchpress.mariadb_manager import redis_drift

		self._redis_answering(mock_get_client, b"maxmemory\n268435456\nmaxmemory-policy\nallkeys-lru\n")

		self.assertEqual(redis_drift(), [])

	@patch("benchpress.mariadb_manager.get_client")
	def test_an_unbounded_redis_names_both_settings(self, mock_get_client):
		"""The live fault this spec exists to end: no ceiling and nothing evictable."""
		from benchpress.mariadb_manager import redis_drift

		self._redis_answering(mock_get_client, b"maxmemory\n0\nmaxmemory-policy\nnoeviction\n")

		self.assertEqual(
			redis_drift(),
			[
				"maxmemory is 0, declared 268435456",
				"maxmemory-policy is noeviction, declared allkeys-lru",
			],
		)

	@patch("benchpress.mariadb_manager.redis_drift", side_effect=Exception("redis is gone"))
	@patch("benchpress.mariadb_manager.mariadb_drift", side_effect=Exception("db is gone"))
	def test_a_pair_it_cannot_read_is_a_line_and_not_an_exception(self, _mariadb, _redis):
		from benchpress.mariadb_manager import shared_setting_drift

		lines, hit_rate = shared_setting_drift("db-1")

		self.assertEqual(
			lines,
			["MariaDB settings unreadable: db is gone", "Redis settings unreadable: redis is gone"],
		)
		self.assertEqual(hit_rate, "unreadable")

	@patch("benchpress.mariadb_manager.redis_drift", return_value=["maxmemory is 0, declared 268435456"])
	@patch("benchpress.mariadb_manager.mariadb_drift", return_value=([], "99.94%"))
	def test_both_services_report_under_their_own_name(self, _mariadb, _redis):
		from benchpress.mariadb_manager import shared_setting_drift

		lines, hit_rate = shared_setting_drift("db-1")

		self.assertEqual(lines, ["Redis maxmemory is 0, declared 268435456"])
		self.assertEqual(hit_rate, "99.94%")

	def _health_check_with(self, drift):
		"""scheduled_health_check over one healthy server, with a cache that really remembers."""
		cache = {}
		with (
			patch("benchpress.mariadb_manager.check_mariadb_health", return_value=True),
			patch("benchpress.mariadb_manager.shared_setting_drift", side_effect=drift),
			patch("benchpress.mariadb_manager.frappe") as mock_frappe,
		):
			mock_frappe.get_all.return_value = [frappe._dict(name="db-1")]
			mock_frappe.cache.return_value.get_value.side_effect = cache.get
			mock_frappe.cache.return_value.set_value.side_effect = cache.__setitem__
			from benchpress.mariadb_manager import scheduled_health_check

			returned = [scheduled_health_check() for _ in drift]
		return returned, mock_frappe.log_error

	def test_an_unchanged_drift_is_logged_once_and_not_every_five_minutes(self):
		"""288 copies of one true row a day is the Error Log this check exists to be read in."""
		drifted = (["Redis maxmemory is 0, declared 268435456"], "99.94%")

		returned, log_error = self._health_check_with([drifted, drifted])

		self.assertEqual(returned, [drifted[0], drifted[0]])
		self.assertEqual(log_error.call_count, 1)
		message = log_error.call_args.kwargs["message"]
		self.assertIn("Redis maxmemory is 0, declared 268435456", message)
		self.assertIn("InnoDB buffer pool hit rate 99.94%", message)

	def test_a_drift_that_changes_is_logged_again(self):
		redis_only = (["Redis maxmemory is 0, declared 268435456"], "99.94%")
		both = (["MariaDB max_connections is 151, declared 500", *redis_only[0]], "99.94%")

		_returned, log_error = self._health_check_with([redis_only, both])

		self.assertEqual(log_error.call_count, 2)
		self.assertIn("max_connections is 151", log_error.call_args.kwargs["message"])

	def test_a_pair_that_agrees_logs_nothing(self):
		_returned, log_error = self._health_check_with([([], "99.94%")])

		log_error.assert_not_called()


LIVE_SHOW_DATABASES = (
	"Database\n"
	"_0f466d815af80ea5\n"
	"_30097bd7739c8788_limited\n"
	"backups\n"
	"information_schema\n"
	"mysql\n"
	"performance_schema\n"
	"sys\n"
)


class TestListSiteDatabases(IntegrationTestCase):
	def _listed(self, exit_code, output):
		from benchpress.mariadb_manager import list_site_databases

		with patch("benchpress.mariadb_manager.execute_sql", return_value=(exit_code, output)):
			return list_site_databases("db-server-name")

	def test_the_server_s_own_schemas_are_not_a_site_s(self):
		listed = self._listed(0, LIVE_SHOW_DATABASES)

		self.assertEqual(listed, ["_0f466d815af80ea5", "_30097bd7739c8788_limited"])

	def test_the_backup_directory_is_not_a_schema(self):
		"""`backup_database_server` writes into the data directory, and the server lists every
		directory there — so a reconciler that reported it could never reach zero."""
		self.assertNotIn("backups", self._listed(0, LIVE_SHOW_DATABASES))

	def test_the_column_header_is_not_a_schema(self):
		self.assertNotIn("Database", self._listed(0, LIVE_SHOW_DATABASES))

	def test_a_client_warning_in_the_same_stream_is_not_a_schema(self):
		output = "mariadb: Deprecated program name.\n" + LIVE_SHOW_DATABASES

		self.assertNotIn("mariadb: Deprecated program name.", self._listed(0, output))

	def test_a_failed_read_reports_nothing_rather_than_everything(self):
		"""An empty list read as "every database is an orphan" is the reason this is a read only."""
		self.assertEqual(self._listed(1, "ERROR 1045: Access denied"), [])

	def test_it_only_reads(self):
		from benchpress.mariadb_manager import list_site_databases

		with patch("benchpress.mariadb_manager.execute_sql", return_value=(0, LIVE_SHOW_DATABASES)) as sql:
			list_site_databases("db-server-name")

		self.assertEqual(sql.call_args.args[1], "SHOW DATABASES")
