import frappe


def execute():
	if not frappe.db.exists("Database Server"):
		doc = frappe.get_doc(
			{
				"doctype": "Database Server",
				"container_name": "benchpress-mariadb",
				"mariadb_version": "10.6",
				"status": "Pending",
			}
		)
		doc.insert(ignore_permissions=True)
