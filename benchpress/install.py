# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe


def after_install():
	site = frappe.local.site

	print("\n" + "=" * 60)
	print("  BenchPress — installed (no host changes made)")
	print("=" * 60 + "\n")

	_print_manual_instructions(site)

	# Create test users in developer mode
	if frappe.conf.get("developer_mode"):
		create_test_users()


def create_test_users():
	"""Create test users for BenchPress Admin and BenchPress User roles.

	Safe to call multiple times — skips if users already exist.
	"""
	test_users = [
		{
			"email": "admin@benchpress.local",
			"first_name": "BP Admin",
			"roles": ["BenchPress Admin"],
		},
		{
			"email": "user@benchpress.local",
			"first_name": "BP User",
			"roles": ["BenchPress User"],
		},
	]

	for user_data in test_users:
		if frappe.db.exists("User", user_data["email"]):
			print(f"  [skip] User {user_data['email']} already exists")
			continue

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": user_data["email"],
				"first_name": user_data["first_name"],
				"enabled": 1,
				"send_welcome_email": 0,
			}
		)
		for role_name in user_data["roles"]:
			user.append("roles", {"role": role_name})
		user.insert(ignore_permissions=True)

		# Set password after insert to bypass strength validation
		from frappe.utils.password import update_password

		update_password(user_data["email"], "admin")
		print(
			f"  [created] {user_data['email']} with roles: {', '.join(user_data['roles'])} (password: admin)"
		)

	frappe.db.commit()  # nosemgrep


def _print_manual_instructions(site: str) -> None:
	print("No changes were made to the host automatically. Configure Docker, WireGuard,")
	print("and host permissions with these explicit steps, run on the host:\n")
	print(f"  1. Check host readiness:   bench benchpress doctor --site {site}")
	print(f"  2. Preview the changes:    bench benchpress setup --site {site} --dry-run")
	print(f"  3. Apply the changes:      bench benchpress setup --site {site}")
	print(f"\nTo revert later (preview):   bench benchpress teardown --site {site} --dry-run\n")
