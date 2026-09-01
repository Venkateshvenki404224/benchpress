# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import subprocess

import frappe

from benchpress.credits.seed import seed_defaults
from benchpress.indexes import ensure_indexes
from benchpress.lab_templates import seed_lab_templates
from benchpress.public_site import CONFIG_KEY
from benchpress.public_site.seed import seed_public_site
from benchpress.vpn_access import grant_vpn_access


def after_install():
	site = frappe.local.site
	bench_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
	script = os.path.join(bench_dir, "apps", "benchpress", "setup.sh")

	print("\n" + "=" * 60)
	print("  BenchPress — Running post-install setup")
	print("=" * 60 + "\n")

	# Fresh installs mark every patch as executed without running it, so everything the seeders
	# below would have done has to be done here as well.
	grant_vpn_access()
	seed_defaults()
	seed_lab_templates()
	seed_public_site()
	ensure_indexes()

	# setup.sh requires host-level access (docker group, sysctl, sudoers).
	# Skip it when running inside a container.
	if os.path.exists("/.dockerenv"):
		print("[!] Running inside Docker — skipping host setup script.")
		_print_manual_instructions(site)
	elif not os.path.exists(script):
		_print_manual_instructions(site)
	else:
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

	if frappe.conf.get("developer_mode"):
		create_test_users()


def create_test_users():
	"""Create the two role test users. Skips any that already exist."""
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

		# After insert, so the strength validation on the field is not applied to it.
		from frappe.utils.password import update_password

		update_password(user_data["email"], "admin")
		print(
			f"  [created] {user_data['email']} with roles: {', '.join(user_data['roles'])} (password: admin)"
		)

	frappe.db.commit()  # nosemgrep


def before_tests() -> None:
	"""Prepare the test site: an outgoing mail account, and the public site switched on."""
	frappe.conf[CONFIG_KEY] = 1
	if frappe.db.exists("Email Account", {"default_outgoing": 1}):
		return
	frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": "BenchPress Tests",
			"email_id": "tests@benchpress.invalid",
			"smtp_server": "localhost",
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"no_smtp_authentication": 1,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the test runner reads this from a new connection


def _print_manual_instructions(site: str) -> None:
	print("\nRun the setup script manually to configure Docker and permissions:")
	print(f"\n  bash apps/benchpress/setup.sh {site}\n")
	print("VPN (tunnels, peers, IPs) is managed by the vpn_management app.\n")
