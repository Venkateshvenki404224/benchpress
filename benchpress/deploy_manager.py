# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import secrets

import frappe
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.synchronization import filelock

from benchpress import image_cache
from benchpress.credits import metering
from benchpress.deploy_pipeline import DeployLogWriter, DeployPipeline
from benchpress.docker_manager import (
	build_lab_image,
	create_bench_container,
	exec_in_container,
	remove_container,
	start_container,
	stop_container,
	wait_for_container_running,
	write_file_to_container,
)
from benchpress.mariadb_manager import (
	create_mariadb_user,
	drop_mariadb_user,
	ensure_infrastructure,
	wait_for_mariadb,
)
from benchpress.notifications import notify_owner


def _remove_stale_container(bench) -> None:
	"""Remove any existing container, preserving the data volume."""
	from benchpress.docker_manager import get_client

	client = get_client()

	if bench.container_id:
		try:
			client.containers.get(bench.container_id).remove(force=True)
		except Exception:
			pass  # best-effort
		bench.container_id = None

	try:
		container = client.containers.get(bench.bench_name)
		container.remove(force=True)
	except Exception:
		pass  # best-effort


NOTHING_TO_ROLL_BACK = "Cleanup: nothing to roll back — no container was created"


def _cleanup_failed_deploy(bench, container_id, append_log) -> None:
	"""Best-effort teardown of resources created by this failed run.

	Fires only when this run created a container — earlier failures leave the
	previous deploy's container and peer untouched. Never touches the data
	volume and never raises: the except block must still record Error state.

	Either way the outcome is written to the log, so the screen reporting the
	failure can state what was rolled back instead of inferring it from silence.
	"""
	if not container_id:
		append_log(NOTHING_TO_ROLL_BACK)
		return
	try:
		remove_container(container_id)
		append_log("Cleanup: removed container created by this run")
	except Exception:
		pass  # best-effort
	try:
		from benchpress.vpn_adapter import remove_bench_peer

		remove_bench_peer(bench)
		append_log("Cleanup: VPN peer removed")
	except Exception:
		pass  # best-effort
	bench.container_id = None
	bench.container_ip = None
	bench.wg_ip = None


def remove_bench_volume(bench_name: str) -> None:
	"""Remove the bench data volume if it exists."""
	from benchpress.docker_manager import get_client

	try:
		get_client().volumes.get(f"benchpress-{bench_name}-data").remove(force=True)
	except Exception:
		pass  # best-effort


def build_linkuser_args(bench, lab, settings, ssh_password: str) -> list[str]:
	"""Positional arguments for linkuser.sh, in the order the script reads them.

	Order must match scripts/linkuser.sh:
	USERNAME EMAIL LAB_NAME WG_IP SSH_PASSWORD BENCH_NAME BASE_DOMAIN LOGIN_SHELL
	"""
	return [
		bench.ssh_username,
		bench.owner,
		lab.title,
		bench.wg_ip or "0.0.0.0",
		ssh_password,
		bench.bench_name,
		settings.base_domain or "localhost",
		lab.shell or "/bin/bash",
	]


# The desk alert on a terminal deploy/build state. Shared with the enforcement sweep and the
# reaper, which announce the same kind of thing about the same documents.
_notify_owner = notify_owner


def create_site_in_container(
	container_id: str, db_server, site_name: str, admin_password: str, apps_csv: str
) -> tuple[int, str]:
	"""Run setup-site.sh inside a bench container using a temporary MariaDB user."""
	bench_dir = "/home/frappe/frappe-bench"  # fixed: the data volume binds at /home/frappe
	db_name, temp_user, temp_password = create_mariadb_user(db_server.name, site_name)
	try:
		return exec_in_container(
			container_id,
			"bash /opt/benchpress/scripts/setup-site.sh",
			user="frappe",
			workdir=bench_dir,
			environment={
				"SITE_NAME": site_name,
				"ADMIN_PASSWORD": admin_password,
				"APPS": apps_csv,
				"DB_HOST": db_server.container_name,
				"DB_NAME": db_name,
				"MARIADB_ROOT_USERNAME": temp_user,
				"MARIADB_ROOT_PASSWORD": temp_password,
			},
		)
	finally:
		drop_mariadb_user(db_server.name, site_name, db_name)


def _log_deploy_skipped(bench_name: str) -> None:
	frappe.get_doc(
		{
			"doctype": "Deploy Log",
			"bench": bench_name,
			"message": "=== Deploy skipped: another deploy is already in progress ===\n",
			"log_type": "warning",
			"timestamp": frappe.utils.now_datetime(),
		}
	).insert(ignore_permissions=True)
	# no manual commit: the job ends right after this, and the worker commits on return


def deploy_bench(bench_name: str) -> None:
	"""Deploy a bench, refusing to run concurrently with another deploy of the same bench."""
	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_deploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _deploy_bench(bench_name: str) -> None:
	"""Deploy pipeline — shared MariaDB, site created at runtime via press agent pattern."""
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
	frappe.db.commit()
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
		bench.status = "Deploying"
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		admin_password = secrets.token_urlsafe(10)
		bench.admin_password = admin_password

		pipeline.step("infrastructure")
		db_server_name = ensure_infrastructure()
		db_server = frappe.get_doc("Database Server", db_server_name)
		wait_for_mariadb(db_server_name, timeout=60)
		pipeline.log(f"MariaDB reachable at {db_server.container_name}:{db_server.port or 3306}")

		bench.database_server = db_server_name
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		# One step whichever way it goes: the run either builds the image or
		# adopts a cached one, and the detail line says which.
		pipeline.step("image")
		_prepare_lab_image(lab, pipeline, bench.owner)

		_remove_stale_container(bench)
		pipeline.step("container")
		container_id = create_bench_container(bench, lab)
		created_container_id = container_id
		bench.container_id = container_id
		bench.container_image = lab.image_tag
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		start_container(container_id)
		pipeline.step("container_ip")
		container_ip = wait_for_container_running(container_id, timeout=60)
		bench.container_ip = container_ip
		pipeline.log(f"container_ip {container_ip}")
		bench.save(ignore_permissions=True)
		frappe.db.commit()

		settings = frappe.get_cached_doc("BenchPress Settings")

		_setup_container_vpn(bench, container_id, pipeline)

		bench_dir = "/home/frappe/frappe-bench"  # fixed: the data volume binds at /home/frappe
		site_name = bench.site_name
		config = {
			**db_server.get_connection_config(),
			"redis_cache": "redis://benchpress-redis:6379/0",
			"redis_queue": "redis://benchpress-redis:6379/1",
			"redis_socketio": "redis://benchpress-redis:6379/2",
			"socketio_port": 9000,
			"webserver_port": 8000,
			"default_site": site_name,
		}
		pipeline.step("site_config")
		write_file_to_container(
			container_id, json.dumps(config, indent=2), f"{bench_dir}/sites/common_site_config.json"
		)
		pipeline.log(f"{bench_dir}/sites/common_site_config.json written")

		pipeline.step("site")
		apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name.lower() != "frappe")
		pipeline.log(f"bench new-site {site_name} --install-app {apps_csv or 'frappe'}")
		exit_code, output = create_site_in_container(
			container_id, db_server, site_name, admin_password, apps_csv
		)
		if exit_code != 0:
			raise Exception(f"bench new-site failed (exit {exit_code}): {output}")
		pipeline.log("Site created successfully")

		pipeline.step("assets")
		exec_in_container(container_id, "bench build", user="frappe", workdir=bench_dir)
		pipeline.log("bench build finished")

		if not bench.ssh_username:
			bench.ssh_username = bench._derive_username(bench.owner)

		ssh_password = secrets.token_urlsafe(12)
		linkuser_args = build_linkuser_args(bench, lab, settings, ssh_password)
		pipeline.step("ssh_user")
		pipeline.log(f"linkuser.sh {bench.ssh_username}")
		linkuser_cmd = "bash /opt/benchpress/scripts/linkuser.sh " + " ".join(f"'{a}'" for a in linkuser_args)
		exit_code, output = exec_in_container(container_id, linkuser_cmd, user="root")
		if output:
			pipeline.log(output.strip())
		if exit_code != 0:
			raise Exception(f"linkuser.sh failed (exit {exit_code}): {output}")

		bench.ssh_password = ssh_password

		# Emitted even when the lab has code-server off: a step the run decided
		# to skip is information, and a stepper missing its tenth row is not.
		pipeline.step("code_server")
		if getattr(lab, "enable_code_server", 0):
			cs_user = bench.ssh_username
			cs_home = f"/home/{cs_user}"
			code_server_password = secrets.token_urlsafe(16)
			config_yaml = (
				f"bind-addr: 0.0.0.0:8080\nauth: password\npassword: {code_server_password}\ncert: false\n"
			)
			write_file_to_container(
				container_id,
				config_yaml,
				f"{cs_home}/.config/code-server/config.yaml",
			)
			exec_in_container(
				container_id,
				f"chown -R {cs_user}:{cs_user} {cs_home}/.config && chmod 600 {cs_home}/.config/code-server/config.yaml",
				user="root",
			)
			exec_in_container(container_id, "bash /opt/benchpress/scripts/restart.sh", user="root")
			bench.code_server_password = code_server_password
			bench.code_server_url = f"http://{bench.wg_ip or bench.container_ip or '127.0.0.1'}:8080/"
			pipeline.log(f"code-server ready at {bench.code_server_url}")
		else:
			pipeline.log("Code server is disabled for this lab — skipped")

		bench.status = "Running"
		bench.started_at = frappe.utils.now_datetime()
		bench.save(ignore_permissions=True)
		# Metering starts where the clock does: an instance is billable once it is actually
		# up, so everything above this line is free however long it took to get there.
		metering.on_bench_running(bench)
		frappe.db.commit()
		# The eleventh step and the run's success line are one line: it carries
		# the total elapsed time, and "Deploy complete" is still in its text for
		# everything that reads the marker rather than the metadata.
		pipeline.step("complete", "success")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "success")
		frappe.db.commit()
		_notify_owner(
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
		frappe.db.commit()
		append_log(f"=== Deploy failed: {e!s} ===", "error")
		frappe.db.set_value("Deploy Log", deploy_log_name, "log_type", "error")
		frappe.db.commit()
		frappe.log_error(
			title=f"BenchPress deploy failed: {bench_name}",
			message=frappe.get_traceback(),
		)
		_notify_owner(bench.owner, f"Bench deploy failed: {bench.bench_name}", "Bench Instance", bench.name)


def _setup_container_vpn(bench, container_id: str, pipeline) -> None:
	"""Replace any stale peer, claim a fresh tunnel IP, and configure the container.

	Removing before creating keeps exactly one peer per bench across deploy /
	redeploy; the link is persisted before the container is configured so a
	configure failure (which reloads the bench) cannot orphan the peer.

	This is step 5 of eleven — the brief lists it tenth, the code runs it here.
	"""
	from benchpress.vpn_adapter import configure_container, create_container_peer, remove_bench_peer

	pipeline.step("vpn_peer")
	remove_bench_peer(bench)
	peer = create_container_peer(bench)
	bench.wg_ip = peer["assigned_ip"]
	bench.save(ignore_permissions=True)
	frappe.db.commit()
	pipeline.log(f"VPN peer {peer['peer']} registered, claimed IP {peer['assigned_ip']}")
	configure_container(container_id, peer["private_key"], peer["assigned_ip"])
	pipeline.log(f"Container VPN: {peer['assigned_ip']}")


def redeploy_bench(bench_name: str) -> None:
	try:
		with filelock(f"bench_deploy_{bench_name}", timeout=1):
			_redeploy_bench(bench_name)
	except LockTimeoutError:
		_log_deploy_skipped(bench_name)


def _redeploy_bench(bench_name: str) -> None:
	teardown_bench(frappe.get_doc("Bench Instance", bench_name))
	_deploy_bench(bench_name)


def teardown_bench(bench) -> None:
	"""Return an instance to `Draft`: container, volume and site database all gone.

	The one teardown path in the app. A redeploy runs it before building the instance again, and
	the reaper runs it and stops there — which is what makes a reaped instance one click from
	running: the `Lab` it was built from, with its apps, branches, version and size, is untouched.

	Every removal is best-effort. A volume that was already gone, or a database that never
	existed, must not leave the instance stuck describing resources it no longer has.
	"""
	if bench.container_id:
		try:
			stop_container(bench.container_id)
		except Exception:
			pass  # best-effort
		try:
			remove_container(bench.container_id)
		except Exception:
			pass  # best-effort

	remove_bench_volume(bench.name)
	_drop_site_database(bench)

	# The container this bench was burning for is gone, so the session ends here. Without
	# this the burning flag would survive the teardown and the fresh container — which
	# `_deploy_bench` bills through the same idempotence guard — would run unmetered.
	metering.on_bench_stopped(bench)

	bench.container_id = None
	bench.container_image = None
	bench.status = "Draft"
	bench.started_at = None
	bench.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the caller may redeploy next, which must see Draft


def _drop_site_database(bench) -> None:
	if not (bench.database_server and bench.site_name):
		return
	from benchpress.mariadb_manager import drop_site_database

	try:
		drop_site_database(bench.database_server, bench.site_name)
	except Exception:
		pass  # best-effort


def _prepare_lab_image(lab, pipeline, user: str) -> None:
	"""Adopt the shared image for this lab's spec, or build it if nobody has yet.

	The cache is keyed by the build spec rather than by the lab, so the second user to deploy a
	given template performs no build at all. It also closes a staleness hole in the old
	`status == "Ready"` check: editing a Ready lab's apps changed what should be built but kept
	pointing at the image built from the previous recipe.

	A build started here writes a `Build Log`, as an explicit rebuild does; the deploy log
	keeps the step and a pointer to it.
	"""
	tag, hit = image_cache.resolve(lab)
	if not hit:
		pipeline.log(f"Building lab image for {lab.title} — output goes to the build log")
		image_tag = _run_build(lab, user)
		pipeline.log(f"Lab image ready: {image_tag}")
		return
	pipeline.log(f"Cache hit: reusing shared image {tag} — no build needed")
	_adopt_cached_image(lab, tag)


def _adopt_cached_image(lab, tag: str) -> None:
	"""Point the lab at an image somebody else's build already produced."""
	if lab.image_tag == tag and lab.status == "Ready":
		return
	lab.image_tag = tag
	lab.status = "Ready"
	lab.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the container is created from this tag, so persist it first


def _build_lab_with_logs(lab, log_fn) -> None:
	"""Build image with bench + apps (site created at runtime)."""
	lab.status = "Building"
	lab.save(ignore_permissions=True)
	frappe.db.commit()

	image_tag = build_lab_image(lab, log_fn=log_fn)

	lab.reload()
	lab.image_tag = image_tag
	lab.status = "Ready"
	lab.save(ignore_permissions=True)
	# Charged after the build returns, so a failed build stays free — and reached only when
	# `_prepare_lab_image` found no cached image, so a cache hit is free too.
	metering.on_image_built(lab)
	frappe.db.commit()
	if log_fn:
		log_fn(f"Lab image ready: {image_tag}")


def _open_build_log(lab, user: str) -> tuple[DeployLogWriter, str]:
	"""A fresh `Build Log` for this lab, and the writer that streams it to `user` alone."""
	build_log = frappe.get_doc(
		{
			"doctype": "Build Log",
			"lab": lab.name,
			"message": "=== Build started ===\n",
			"log_type": "info",
			"timestamp": frappe.utils.now_datetime(),
		}
	)
	build_log.insert(ignore_permissions=True)
	frappe.db.commit()

	writer = DeployLogWriter(
		"Build Log",
		build_log.name,
		"lab_build_log",
		{"lab": lab.name, "build_log": build_log.name},
		user,
	)
	return writer, build_log.name


def _run_build(lab, user: str) -> str:
	"""Build the image into its own log, mark that log's outcome, return the tag.

	Re-raises, so a deploy that needed the image fails with it.
	"""
	append_log, build_log_name = _open_build_log(lab, user)
	try:
		_build_lab_with_logs(lab, append_log)
	except Exception as e:
		frappe.db.set_value("Lab", lab.name, "status", "Error")
		append_log(f"=== Build failed: {e!s} ===", "error")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "error")
		frappe.db.commit()  # nosemgrep -- the run's outcome must survive its failure
		frappe.log_error(
			title=f"Lab image build failed: {lab.name}",
			message=frappe.get_traceback(),
		)
		raise

	append_log(f"=== Build complete: {lab.image_tag} ===", "success")
	frappe.db.set_value("Build Log", build_log_name, "log_type", "success")
	frappe.db.commit()  # nosemgrep -- the log records a finished run
	return lab.image_tag


def build_lab(lab_name: str) -> None:
	"""Build a lab image as a background job with realtime log streaming.

	Always builds, even when the shared cache already holds this spec's tag: an explicit build is
	how an admin refreshes a tag whose branch has moved, since the hash covers the branch and not
	the commit. Docker layer caching can still make that a near no-op — `build_lab_image` takes
	`no_cache=True` for a true from-scratch rebuild.
	"""
	lab = frappe.get_doc("Lab", lab_name)
	try:
		image_tag = _run_build(lab, lab.owner)
	except Exception:
		_notify_owner(lab.owner, f"Lab build failed: {lab.title}", "Lab", lab_name)
		return
	_notify_owner(lab.owner, f"Lab build complete: {lab.title} ({image_tag})", "Lab", lab_name)


def stop_bench(bench_name: str) -> None:
	"""Stop a bench container. VPN stops automatically with the container."""
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		stop_container(bench.container_id)

	bench.status = "Stopped"
	metering.on_bench_stopped(bench)
	bench.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- intentional commit to persist status before response
