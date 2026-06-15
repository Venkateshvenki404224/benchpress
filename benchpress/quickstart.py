# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""TB1 walking-skeleton ``quickstart`` orchestration.

One command, end to end: ensure a hardcoded ERPNext Lab exists, build its image,
deploy a Bench Instance with predictable ``Administrator / admin`` credentials, and
block until the site is up. Everything that is not load-bearing for the wiring is
deliberately hardcoded here and paid back in later tracer bullets (TB2+).
"""

import time

import click
import frappe

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.deploy_manager import build_lab, deploy_bench

# --- Deliberately hardcoded in TB1 (paid back in TB2 via a Settings preset) ---
QUICKSTART_LAB_ID = "erpnext-quickstart"
QUICKSTART_FRAPPE_VERSION = "version-15"
QUICKSTART_ADMIN_PASSWORD = "admin"
QUICKSTART_LAB = {
	"doctype": "Lab",
	"lab_id": QUICKSTART_LAB_ID,
	"title": "ERPNext Quickstart",
	"frappe_version": QUICKSTART_FRAPPE_VERSION,
	"description": "Zero-config ERPNext bench (TB1 walking skeleton).",
	"memory_limit": "4g",
	"cpu_cores": 2,
	"apps": [
		{
			"app_name": "frappe",
			"app_label": "Frappe",
			"git_url": "https://github.com/frappe/frappe",
			"branch": QUICKSTART_FRAPPE_VERSION,
		},
		{
			"app_name": "erpnext",
			"app_label": "ERPNext",
			"git_url": "https://github.com/frappe/erpnext",
			"branch": QUICKSTART_FRAPPE_VERSION,
		},
	],
}


def _echo(message: str, fg: str | None = None) -> None:
	click.echo(click.style(message, fg=fg) if fg else message)


def run_quickstart() -> None:
	"""Drive the full Lab -> image -> bench -> banner slice, blocking throughout."""
	lab = _ensure_lab()
	_ensure_image(lab)
	bench = _deploy(lab)
	_start_web_server(bench)
	_print_banner(bench)


def _ensure_lab():
	"""Create the hardcoded ERPNext Lab if it does not already exist."""
	if frappe.db.exists("Lab", QUICKSTART_LAB_ID):
		_echo(f"==> Lab '{QUICKSTART_LAB_ID}' already exists.")
	else:
		_echo(f"==> Creating Lab '{QUICKSTART_LAB_ID}'...")
		frappe.get_doc(QUICKSTART_LAB).insert(ignore_permissions=True)
		frappe.db.commit()
	return frappe.get_doc("Lab", QUICKSTART_LAB_ID)


def _ensure_image(lab) -> None:
	"""Build the lab image (blocking) unless a cached one is already Ready."""
	if lab.status == "Ready" and lab.image_tag:
		_echo(f"==> Using cached image: {lab.image_tag}")
		return

	_echo("==> Building ERPNext image (this can take several minutes)...")
	build_lab(lab.name)
	lab.reload()
	if lab.status != "Ready" or not lab.image_tag:
		frappe.throw(f"Image build failed; inspect the Build Log for lab '{lab.name}'.")
	_echo(f"==> Image ready: {lab.image_tag}")


def _deploy(lab):
	"""Create (or reuse) the Bench Instance with preset creds and deploy inline."""
	bench_name = get_instance_id(frappe.session.user, lab.name)

	if frappe.db.exists("Bench Instance", bench_name):
		_echo(f"==> Reusing existing Bench Instance '{bench_name}'.")
		bench = frappe.get_doc("Bench Instance", bench_name)
	else:
		_echo("==> Creating Bench Instance...")
		bench = frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Draft",
			}
		)
		for app in lab.apps:
			bench.append(
				"apps",
				{
					"app_name": app.app_name,
					"app_label": app.app_label,
					"git_url": app.git_url,
					"branch": app.branch,
				},
			)
		bench.insert(ignore_permissions=True)

	# Override the random password deploy_bench would otherwise generate, so
	# beginners get predictable Administrator / admin credentials.
	bench.admin_password = QUICKSTART_ADMIN_PASSWORD
	bench.save(ignore_permissions=True)
	frappe.db.commit()

	# Run the deploy INLINE (the API enqueues to the "long" queue; a CLI must
	# block until the site is actually up).
	_echo("==> Deploying bench (blocks until the site is up)...")
	deploy_bench(bench.name)

	bench.reload()
	if bench.status != "Running":
		frappe.throw(f"Deploy did not reach Running (status={bench.status}); inspect the Deploy Log.")
	return bench


def _start_web_server(bench) -> None:
	"""Start the Frappe dev web server inside the container so the banner URL is live.

	``entry.sh`` starts Redis/SSH/code-server but not the web server, so nothing
	listens on :8000 after a deploy. TB1 starts it here (reusing ``exec_in_container``)
	rather than touching the Docker template; a later tracer bullet should move this
	into the container entrypoint so it survives restarts.
	"""
	from benchpress.docker_manager import exec_in_container

	user = bench.ssh_username or "frappe"
	bench_dir = f"/home/{user}/frappe-bench"

	_echo("==> Starting web server on :8000...")
	exec_in_container(
		bench.container_id,
		"screen -d -m -S web bench serve --port 8000",
		user=user,
		workdir=bench_dir,
	)

	# Block until the port actually accepts connections, so the printed URL works.
	for _ in range(15):
		exit_code, _output = exec_in_container(
			bench.container_id,
			"ss -ltn 2>/dev/null | grep -q ':8000 '",
			user="root",
			workdir="/",
		)
		if exit_code == 0:
			return
		time.sleep(2)
	frappe.throw("Web server did not start listening on :8000; inspect the container.")


def _print_banner(bench) -> None:
	"""Print the success banner: web URL, credentials, SSH details, bench name."""
	host = bench.wg_ip or bench.container_ip or "127.0.0.1"
	web_url = f"http://{host}:8000/"
	ssh_password = bench.get_password("ssh_password", raise_exception=False) or "(see Bench Instance)"

	line = "=" * 64
	_echo("")
	_echo(line, fg="green")
	_echo("  BenchPress quickstart complete - your ERPNext site is up!", fg="green")
	_echo(line, fg="green")
	_echo(f"  Web URL   : {web_url}")
	_echo("  Login     : Administrator")
	_echo(f"  Password  : {QUICKSTART_ADMIN_PASSWORD}")
	_echo("")
	_echo(f"  SSH       : ssh {bench.ssh_username}@{host}")
	_echo(f"  SSH pass  : {ssh_password}")
	_echo(f"  Bench     : {bench.name}")
	_echo(line, fg="green")
	_echo("")
