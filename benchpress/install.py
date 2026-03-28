import os
import subprocess

import frappe


def after_install():
	site = frappe.local.site
	bench_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
	script = os.path.join(bench_dir, "apps", "benchpress", "setup.sh")

	print("\n" + "=" * 60)
	print("  BenchPress — Running post-install setup")
	print("=" * 60 + "\n")

	if not os.path.exists(script):
		_print_manual_instructions(site)
		return

	try:
		result = subprocess.run(
			["bash", script, site],
			cwd=bench_dir,
			check=False,
		)
		if result.returncode != 0:
			print(f"\n[!] setup.sh exited with code {result.returncode}")
			_print_manual_instructions(site)
	except Exception as e:
		print(f"\n[!] Could not run setup.sh: {e}")
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

	frappe.db.commit()


def _print_manual_instructions(site: str) -> None:
	print("\nRun the setup script manually to configure Docker, WireGuard, and permissions:")
	print(f"\n  bash apps/benchpress/setup.sh {site}\n")
	print("Or follow the manual steps in: apps/benchpress/docs/wireguard-setup.md\n")
