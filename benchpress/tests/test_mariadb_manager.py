# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import base64
import hashlib
from unittest.mock import MagicMock, call, patch

import frappe
from frappe.tests import IntegrationTestCase


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

		# First exec_run call should base64-decode the SQL into a temp file
		first_call_args = mock_container.exec_run.call_args_list[0]
		cmd = first_call_args[1].get("cmd") or first_call_args[0][0]
		cmd_str = " ".join(cmd)
		self.assertIn("base64 -d", cmd_str)

	@patch("benchpress.mariadb_manager.get_client")
	@patch("benchpress.mariadb_manager.frappe.get_doc")
	def test_execute_sql_cleans_up_tmp_file_on_error(self, mock_get_doc, mock_get_client):
		from benchpress.mariadb_manager import execute_sql

		mock_get_doc.return_value = self._make_mock_db_server()
		mock_container = MagicMock()
		# Second exec_run (the actual SQL) raises an error
		mock_container.exec_run.side_effect = [
			(0, b""),  # write temp file
			RuntimeError("DB exploded"),  # run SQL
			(0, b""),  # rm -f in finally
		]
		mock_get_client.return_value.containers.get.return_value = mock_container

		with self.assertRaises(RuntimeError):
			execute_sql("db-server-name", "DROP TABLE important")

		# rm -f should still be called (finally block)
		last_call = mock_container.exec_run.call_args_list[-1]
		cmd = last_call[1].get("cmd") or last_call[0][0]
		self.assertIn("rm", cmd)

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
		from benchpress.mariadb_manager import drop_mariadb_user, get_database_name

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
