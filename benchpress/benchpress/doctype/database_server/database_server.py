# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from benchpress.mariadb_manager import DEFAULT_MARIADB_CONFIG


class DatabaseServer(Document):
	def before_insert(self):
		if not self.mariadb_root_password:
			self.mariadb_root_password = frappe.generate_hash(length=32)
		if not self.container_name:
			self.container_name = "benchpress-mariadb"
		if not self.image_tag:
			self.image_tag = f"mariadb:{self.mariadb_version or '10.6'}"
		if not self.volume_name:
			self.volume_name = "benchpress-mariadb-data"
		if not self.custom_config:
			self.custom_config = DEFAULT_MARIADB_CONFIG

	def get_root_password(self) -> str:
		return self.get_password("mariadb_root_password")

	def get_connection_config(self) -> dict:
		"""Return connection config using Docker DNS name (not IP)."""
		return {
			"db_host": self.container_name,
			"db_port": self.port or 3306,
		}

	def set_error(self, message: str):
		self.status = "Error"
		self.error_message = message
		self.save(ignore_permissions=True)
		frappe.db.commit()

	@frappe.whitelist()
	def setup_mariadb(self):
		frappe.has_permission("Database Server", doc=self.name, throw=True)
		from benchpress.mariadb_manager import setup_database_server

		frappe.enqueue(
			setup_database_server,
			db_server_name=self.name,
			queue="long",
			timeout=600,
		)
		frappe.msgprint("MariaDB setup started.")

	@frappe.whitelist()
	def stop_mariadb(self):
		frappe.has_permission("Database Server", doc=self.name, throw=True)
		from benchpress.mariadb_manager import stop_database_server

		stop_database_server(self.name)

	@frappe.whitelist()
	def start_mariadb(self):
		frappe.has_permission("Database Server", doc=self.name, throw=True)
		from benchpress.mariadb_manager import start_database_server

		start_database_server(self.name)

	@frappe.whitelist()
	def retry_setup(self):
		frappe.has_permission("Database Server", doc=self.name, throw=True)
		self.status = "Pending"
		self.error_message = ""
		self.save(ignore_permissions=True)
		frappe.db.commit()
		self.setup_mariadb()

	@frappe.whitelist()
	def get_logs(self, tail=100):
		frappe.has_permission("Database Server", doc=self.name, throw=True)
		from benchpress.mariadb_manager import get_container_logs

		return get_container_logs(self.name, tail=tail)
