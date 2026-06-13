import frappe


def execute():
	"""Default existing installs to the Let's Encrypt staging CA.

	le_use_staging is a new Check field; Frappe applies its default only when a
	doc is created, so a BenchPress Settings singleton that predates the field
	reads as 0 (production). Backfill the safe staging default so HTTPS testing
	does not hit the Let's Encrypt production rate limit.
	"""
	if not frappe.db.get_single_value("BenchPress Settings", "le_use_staging"):
		frappe.db.set_single_value("BenchPress Settings", "le_use_staging", 1)
