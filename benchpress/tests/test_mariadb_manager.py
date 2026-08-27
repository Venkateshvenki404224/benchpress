# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import base64
import hashlib
import io
import os
import tarfile
import tempfile
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

	def _make_mock_db_server(self, container_id="ctr-abc"):
		db_server = MagicMock()
		db_server.container_id = container_id
		db_server.get_root_password.return_value = "rootpw"
		return db_server

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

	@patch("benchpress.mariadb_manager._get_config_dir")
	def test_write_mariadb_config_writes_custom_config_verbatim(self, mock_config_dir):
		"""Database Server.custom_config flows verbatim into the mounted mariadb.cnf."""
		from benchpress.mariadb_manager import _write_mariadb_config

		with tempfile.TemporaryDirectory() as tmp:
			mock_config_dir.return_value = tmp
			custom = "[mysqld]\nmax_connections=1234\ninnodb_buffer_pool_size=1073741824\n"
			_write_mariadb_config(custom)
			with open(os.path.join(tmp, "mariadb.cnf")) as f:
				written = f.read()
		self.assertEqual(written, custom)

	@patch("benchpress.mariadb_manager._get_config_dir")
	def test_write_mariadb_config_falls_back_to_default(self, mock_config_dir):
		"""An empty custom_config falls back to DEFAULT_MARIADB_CONFIG."""
		from benchpress.mariadb_manager import DEFAULT_MARIADB_CONFIG, _write_mariadb_config

		with tempfile.TemporaryDirectory() as tmp:
			mock_config_dir.return_value = tmp
			_write_mariadb_config(None)
			with open(os.path.join(tmp, "mariadb.cnf")) as f:
				written = f.read()
		self.assertEqual(written, DEFAULT_MARIADB_CONFIG)
