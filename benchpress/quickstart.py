# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""TB2 ``quickstart`` orchestration — config-driven and idempotent.

One command, end to end: ensure the default ERPNext Lab exists, build its image,
deploy a Bench Instance with the preset ``Administrator / <default_admin_password>``
credentials, and block until the site is up. The presets (which Lab, which admin
password) live in **BenchPress Settings** so they are editable from Desk; the
hardcoded Lab below is only the create-if-missing seed for a fresh install.

Re-running is idempotent: an already-Running default bench reprints its access
banner instead of redeploying.
"""

import time

import click
import frappe
from frappe import _

from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.deploy_manager import build_lab, deploy_bench
from benchpress.platform import resolve_access_url

# Seed for the default Lab, created on first run when Settings.default_lab is unset.
# The *live* preset is BenchPress Settings.default_lab — this dict only bootstraps a
# fresh install so there is something to point that field at.
QUICKSTART_LAB_ID = "erpnext-quickstart"
QUICKSTART_FRAPPE_VERSION = "version-15"
QUICKSTART_LAB = {
	"doctype": "Lab",
	"lab_id": QUICKSTART_LAB_ID,
	"title": "ERPNext Quickstart",
	"frappe_version": QUICKSTART_FRAPPE_VERSION,
	"description": "Zero-config ERPNext bench (BenchPress quickstart default).",
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

DEFAULT_ADMIN_PASSWORD = "admin"


def _echo(message: str, fg: str | None = None) -> None:
	click.echo(click.style(message, fg=fg) if fg else message)


def run_quickstart() -> None:
	"""Drive the full Lab -> image -> bench -> banner slice, blocking throughout.

	Idempotent: if the default bench is already Running, reprint its banner and stop.
	"""
	settings = frappe.get_cached_doc("BenchPress Settings")
	lab = _ensure_lab(settings)

	bench_name = get_instance_id(frappe.session.user, lab.name)
	if frappe.db.exists("Bench Instance", bench_name):
		bench = frappe.get_doc("Bench Instance", bench_name)
		if bench.status == "Running":
			_echo(f"==> Default bench '{bench_name}' is already running; reprinting access details.")
			_print_banner(bench)
			return

	_ensure_image(lab)
	bench = _deploy(lab, settings)
	_start_web_server(bench)
	_print_banner(bench)


def _ensure_lab(settings):
	"""Resolve the default Lab from Settings, seeding it on a fresh install.

	Uses ``BenchPress Settings.default_lab`` when set; otherwise creates the hardcoded
	ERPNext seed Lab and records it back into Settings so subsequent runs (and Desk)
	share the same source of truth.
	"""
	if settings.default_lab and frappe.db.exists("Lab", settings.default_lab):
		_echo(f"==> Using default Lab '{settings.default_lab}' from BenchPress Settings.")
		return frappe.get_doc("Lab", settings.default_lab)

	if frappe.db.exists("Lab", QUICKSTART_LAB_ID):
		_echo(f"==> Lab '{QUICKSTART_LAB_ID}' already exists.")
		lab = frappe.get_doc("Lab", QUICKSTART_LAB_ID)
	else:
		_echo(f"==> Creating default Lab '{QUICKSTART_LAB_ID}'...")
		lab = frappe.get_doc(QUICKSTART_LAB).insert(ignore_permissions=True)

	frappe.db.set_single_value("BenchPress Settings", "default_lab", lab.name)
	# CLI one-shot: nothing else commits before frappe.destroy(), so persist the seed here.
	frappe.db.commit()  # nosemgrep
	return lab


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


def _deploy(lab, settings):
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

	# Override the random password deploy_bench would otherwise generate, so beginners
	# get predictable Administrator credentials sourced from Settings.
	bench.admin_password = settings.default_admin_password or DEFAULT_ADMIN_PASSWORD
	bench.save(ignore_permissions=True)
	# Persist the bench before the inline deploy_bench; the CLI commits nothing else.
	frappe.db.commit()  # nosemgrep

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
	for _attempt in range(15):
		exit_code, _output = exec_in_container(
			bench.container_id,
			"ss -ltn 2>/dev/null | grep -q ':8000 '",
			user="root",
			workdir="/",
		)
		if exit_code == 0:
			return
		time.sleep(2)
	frappe.throw(_("Web server did not start listening on :8000; inspect the container."))


def _print_banner(bench) -> None:
	"""Print the success banner: web URL, credentials, SSH details, bench name."""
	host = resolve_access_url(bench)
	web_url = f"http://{host}:8000/"
	admin_password = bench.get_password("admin_password", raise_exception=False) or DEFAULT_ADMIN_PASSWORD
	ssh_password = bench.get_password("ssh_password", raise_exception=False) or "(see Bench Instance)"

	line = "=" * 64
	_echo("")
	_echo(line, fg="green")
	_echo("  BenchPress quickstart complete - your ERPNext site is up!", fg="green")
	_echo(line, fg="green")
	_echo(f"  Web URL   : {web_url}")
	_echo("  Login     : Administrator")
	_echo(f"  Password  : {admin_password}")
	_echo("")
	_echo(f"  SSH       : ssh {bench.ssh_username}@{host}")
	_echo(f"  SSH pass  : {ssh_password}")
	_echo(f"  Bench     : {bench.name}")
	_echo(line, fg="green")
	_echo("")
