# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The bench lifecycle transitions, and the side effects each one must not forget."""

import json
import secrets
import shlex
from pathlib import Path

import frappe
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.synchronization import filelock

from benchpress import addressing, ingress, placement
from benchpress.credits import admission, lease, metering
from benchpress.deploy_pipeline import DeployLogWriter, DeployPipeline
from benchpress.docker_manager import (
	container_network,
	container_runtime,
	create_bench_container,
	exec_in_container,
	restart_container,
	start_bench_container,
	start_container,
	wait_for_container_running,
	write_file_to_container,
)
from benchpress.mariadb_manager import ensure_infrastructure, wait_for_mariadb
from benchpress.notifications import notify_owner


def running(bench, *, action: str = "start") -> None:
	"""Bring a bench to Running, with the four side effects a start must not forget.

	`action` is "start" or "restart"; a restart keeps the `started_at` it already has.
	"""
	if action == "restart":
		restart_container(bench.container_id)
	else:
		start_container(bench.container_id)
		bench.started_at = frappe.utils.now_datetime()

	bench.status = "Running"
	# Before the save, so the deadline and the status it belongs to are written together. A
	# restart does not interrupt the window the user already bought: this only buys one for a
	# bench that had none.
	metering.on_bench_running(bench)
	bench.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the route job re-reads `status`, so it must not start before this
	# After the commit, because the job re-reads `status`.
	ingress.enqueue_route_sync(bench.name)


def deploy_bench(bench_name: str) -> None:
	"""Deploy a bench, refusing to run concurrently with another deploy of the same bench."""
	from benchpress.deploy_manager import _log_deploy_skipped

	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_deploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _deploy_bench(bench_name: str) -> None:
	"""Deploy pipeline — shared MariaDB, site created at runtime via press agent pattern."""
	# Permanent, not a step on the way to a module-scope import: image building and site
	# creation are the remainder `deploy_manager` keeps, and importing them at module scope
	# would make a cycle the moment anything there needs a transition.
	from benchpress.deploy_manager import (
		_assert_runtime_registered,
		_cleanup_failed_deploy,
		_drop_site_database,
		_golden_matches_server,
		_prepare_lab_image,
		_record_primary_site,
		_remove_stale_container,
		_setup_container_vpn,
		_site_outcome,
		_start_code_server,
		build_linkuser_args,
		create_site_in_container,
		linkuser_command,
	)

	bench = frappe.get_doc("Bench Instance", bench_name)
	lab = frappe.get_doc("Lab", bench.lab)

	deploy_log = frappe.get_doc(
		{
			"doctype": "Deploy Log",
			"bench": bench_name,
			"message": "=== Deploy started ===\n",
			"log_type": "info",
			"timestamp": frappe.utils.now_datetime(),
		}
	)
	deploy_log.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the SPA opens the log by name, so the row has to exist before the run continues
	deploy_log_name = deploy_log.name

	# Scoped to the bench's owner: a deploy log is that user's, and nobody
	# else's socket has any business receiving it.
	append_log = DeployLogWriter(
		"Deploy Log",
		deploy_log_name,
		"bench_deploy_log",
		{"bench": bench_name, "deploy_log": deploy_log_name},
		bench.owner,
	)
	pipeline = DeployPipeline(append_log)

	created_container_id = None
	try:
		if bench.status == "Draft":
			# Not the value `validate` defaulted: a bench can sit in Draft for days, and the
			# bridge with room then is not the bridge with room now.
			placement.record_bridge_network(bench, placement.pick_network())
		bench.status = "Deploying"
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- `Deploying` has to be visible while the minutes below run

		admin_password = secrets.token_urlsafe(10)
		bench.admin_password = admin_password

		pipeline.step("infrastructure")
		db_server_name = ensure_infrastructure()
		db_server = frappe.get_doc("Database Server", db_server_name)
		wait_for_mariadb(db_server_name, timeout=60)
		pipeline.log(f"MariaDB reachable at {db_server.container_name}:{db_server.port or 3306}")

		# First step of the deploy, so this runs minutes ahead of the image build —
		# headroom a fresh install needs, because DNS-01 has to finish issuing before
		# the bench route goes live.
		settings = frappe.get_cached_doc("BenchPress Settings")
		if ingress.ensure_anchor(settings.base_domain):
			pipeline.log(f"Traefik wildcard anchor written for *.{settings.base_domain}")

		bench.database_server = db_server_name
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the server the rest of the run uses, published before it is used

		# Ahead of the image step on purpose: the build is where the minutes go,
		# and a bench the host cannot isolate has no business paying for one.
		_assert_runtime_registered(bench)

		# One step whichever way it goes: the run either builds the image or
		# adopts a cached one, and the detail line says which.
		pipeline.step("image")
		_prepare_lab_image(lab, pipeline, bench.owner)

		# Both halves of the previous deploy go together, and before the new container
		# exists: the site database is the other thing a redeploy replaces, and dropping a
		# few hundred tables is teardown, not part of creating the site that follows.
		_remove_stale_container(bench)
		_drop_site_database(bench)
		pipeline.step("container")
		container_id = create_bench_container(bench, lab)
		created_container_id = container_id
		# Read back rather than assumed: the stored log answers what a bench was
		# isolated by long after the run.
		pipeline.log(f"container runtime {container_runtime(container_id)}")

		container_id = created_container_id = start_bench_container(container_id, bench, lab)
		placement.record_bridge_network(bench, container_network(container_id))
		pipeline.log(f"bench bridge {bench.bridge_network}")

		bench.container_id = container_id
		bench.node = lease.local_node()
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the container id, so a crash after this point leaves something to clean up

		pipeline.step("container_ip")
		container_ip = wait_for_container_running(container_id, bench.bridge_network, timeout=60)
		bench.container_ip = container_ip
		pipeline.log(f"container_ip {container_ip}")
		bench.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep -- the address the route file is written from

		bench.public_url = addressing.public_site_url(bench.name, settings.base_domain)
		ingress.publish(bench.name, settings.base_domain)
		ingress.log_certificate_state(bench.name, settings.base_domain, pipeline)

		_setup_container_vpn(bench, container_id, pipeline)

		bench_dir = "/home/frappe/frappe-bench"
		site_name = bench.site_name
		config = {
			**db_server.get_connection_config(),
			"redis_cache": "redis://benchpress-redis:6379/0",
			"redis_queue": "redis://benchpress-redis:6379/1",
			"redis_socketio": "redis://benchpress-redis:6379/2",
			"socketio_port": 9000,
			"webserver_port": addressing.SITE_HTTP_PORT,
			"default_site": site_name,
			"developer_mode": 1,
		}
		pipeline.step("site_config")
		write_file_to_container(
			container_id, json.dumps(config, indent=2), f"{bench_dir}/sites/common_site_config.json"
		)
		pipeline.log(f"{bench_dir}/sites/common_site_config.json written")

		pipeline.step("site")
		apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name.lower() != "frappe")
		pipeline.log(f"Site {site_name} with {apps_csv or 'frappe'}")
		use_golden, refusal = _golden_matches_server(lab.image_tag, db_server)
		if refusal:
			pipeline.log(refusal)
		exit_code, output = create_site_in_container(
			container_id, db_server, site_name, admin_password, apps_csv, use_golden=use_golden
		)
		if exit_code != 0:
			raise Exception(f"Site setup failed (exit {exit_code}): {output}")
		pipeline.log(_site_outcome(output, site_name))
		_record_primary_site(bench, lab, admin_password)

		pipeline.step("assets")
		# Deploy never builds; rebuilding the lab image is how a stale bundle is refreshed.
		pipeline.log("Assets ship in the image — bundled at build time")

		if not bench.ssh_username:
			bench.ssh_username = bench._derive_username(bench.owner)

		ssh_password = secrets.token_urlsafe(12)
		linkuser_args = build_linkuser_args(bench, lab, settings)
		pipeline.step("ssh_user")
		pipeline.log(f"linkuser.sh {bench.ssh_username}")
		# The app's copy of linkuser.sh is authoritative over the one baked into the image.
		linkuser_script = (
			Path(frappe.get_app_path("benchpress")) / "lab-templates" / "scripts" / "linkuser.sh"
		)
		write_file_to_container(
			container_id, linkuser_script.read_text(), "/opt/benchpress/scripts/linkuser.sh"
		)
		linkuser_cmd = linkuser_command(linkuser_args)
		exit_code, output = exec_in_container(
			container_id, linkuser_cmd, user="root", environment={"SSH_PASSWORD": ssh_password}
		)
		if output:
			pipeline.log(output.strip())
		if exit_code != 0:
			raise Exception(f"linkuser.sh failed (exit {exit_code}): {output}")

		bench.ssh_password = ssh_password

		# Emitted even when the lab has code-server off: a step the run decided
		# to skip is information, and a stepper missing its tenth row is not.
		pipeline.step("code_server")

		# After linkuser.sh, not after site creation: that renames the bench user, and
		# `usermod --login` refuses to rename a user owning a running process. The account is
		# named here rather than derived inside the container from a path the tenant owns.
		exit_code, output = exec_in_container(
			container_id,
			f"bash /opt/benchpress/scripts/serve.sh {shlex.quote(bench.ssh_username)}",
			user="root",
		)
		if exit_code != 0:
			raise Exception(f"serve.sh failed (exit {exit_code}): {output}")
		pipeline.log(f"Site served on port {addressing.SITE_HTTP_PORT}")

		if getattr(lab, "enable_code_server", 0):
			_start_code_server(bench, container_id, pipeline, settings)
		else:
			pipeline.log("Code server is disabled for this lab — skipped")

		# Everything above this line is free however long it took, because a deploy that never
		# gets here never reaches `Running`.
		running(bench)
		# The eleventh step and the run's success line are one line: it carries
		# the total elapsed time, and "Deploy complete" is still in its text for
		# everything that reads the marker rather than the metadata.
		pipeline.step("complete", "success")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "success")
		frappe.db.commit()  # nosemgrep -- the success marker, read by everything watching the run
		notify_owner(
			bench.owner,
			f"Bench deployed: {bench.bench_name} ({bench.site_name})",
			"Bench Instance",
			bench.name,
		)

	except Exception as e:
		bench.reload()
		_cleanup_failed_deploy(bench, created_container_id, append_log)
		bench.status = "Error"
		bench.save(ignore_permissions=True)
		# Settle whatever did run and charge nothing further: a failed deploy is free, and a
		# failed *re*deploy of an instance that was already burning must not keep burning.
		metering.on_bench_stopped(bench)
		# Beside the settle, not behind it: `on_bench_stopped` is free on a bench that never
		# held a lease, which is every deploy that fails before Running.
		admission.release(bench.name)
		frappe.db.commit()  # nosemgrep -- the failure state, before the log lines that explain it
		append_log(f"=== Deploy failed: {e!s} ===", "error")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "error")
		frappe.db.commit()  # nosemgrep -- the log's own outcome, so a watcher sees why the run stopped
		frappe.log_error(
			title=f"BenchPress deploy failed: {bench_name}",
			message=frappe.get_traceback(),
		)
		notify_owner(bench.owner, f"Bench deploy failed: {bench.bench_name}", "Bench Instance", bench.name)


def redeploy_bench(bench_name: str) -> None:
	from benchpress.deploy_manager import _log_deploy_skipped

	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_redeploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _redeploy_bench(bench_name: str) -> None:
	from benchpress.deploy_manager import teardown_bench

	# The slot is held across the whole redeploy: releasing between the two halves would hand it
	# to somebody else and leave this caller one over their limit when their own deploy lands.
	teardown_bench(frappe.get_doc("Bench Instance", bench_name), release_admission=False)
	_deploy_bench(bench_name)
