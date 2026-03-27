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


def _print_manual_instructions(site: str) -> None:
	print("\nRun the setup script manually to configure Docker, WireGuard, and permissions:")
	print(f"\n  bash apps/benchpress/setup.sh {site}\n")
	print("Or follow the manual steps in: apps/benchpress/docs/wireguard-setup.md\n")
