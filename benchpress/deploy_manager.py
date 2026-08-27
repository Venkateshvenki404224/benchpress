# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import re
import secrets
import shlex

import frappe
from frappe import _

from benchpress import addressing, image_cache, ingress, site_names
from benchpress.credits import admission, lease, metering
from benchpress.deploy_pipeline import DeployLogWriter
from benchpress.docker_manager import (
	build_lab_image,
	exec_in_container,
	host_runtimes,
	remove_container,
	resolve_runtime,
	stop_container,
	write_file_to_container,
)
from benchpress.mariadb_manager import (
	create_mariadb_user,
	drop_mariadb_user,
	server_version,
)
from benchpress.notifications import notify_owner


def _assert_runtime_registered(bench) -> None:
	"""Refuse a bench whose runtime the daemon does not have. No fallback to runc.

	A bench that cannot be isolated must not silently run unisolated, so this
	fails the deploy and leaves the choice to an admin.
	"""
	runtime = resolve_runtime(bench)
	registered = host_runtimes()["names"]
	if runtime and runtime not in registered:
		frappe.throw(
			_("Bench runtime '{0}' is not registered with the Docker daemon (it has: {1}).").format(
				runtime, ", ".join(sorted(registered))
			)
		)


def _remove_stale_container(bench) -> None:
	"""Remove any existing container for this bench."""
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

ADOPTED_MARKER = "already exists — adopting it"
GOLDEN_MARKER = "Restored from golden dump"
# What the Deploy Log says when the golden branch ran. `golden_drill` reads runs back by it.
GOLDEN_RESTORED = "restored from the image's golden dump"


def _cleanup_failed_deploy(bench, container_id, append_log) -> None:
	"""Best-effort teardown of resources created by this failed run.

	Fires only when this run created a container — earlier failures leave the
	previous deploy's container and peer untouched. Never raises: the except
	block must still record Error state.

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


def build_linkuser_args(bench, lab, settings) -> list[str]:
	"""Positional arguments for linkuser.sh, in the order the script reads them.

	Order must match scripts/linkuser.sh:
	USERNAME EMAIL LAB_NAME WG_IP BENCH_NAME BASE_DOMAIN LOGIN_SHELL

	The SSH password is not among them. It travels in the exec environment, which Docker
	does not publish, while it publishes every command line in full.
	"""
	return [
		bench.ssh_username,
		bench.owner,
		lab.title,
		bench.wg_ip or "0.0.0.0",
		bench.bench_name,
		settings.base_domain or "localhost",
		lab.shell or "/bin/bash",
	]


def linkuser_command(script_args: list[str]) -> str:
	"""The linkuser.sh invocation, with every argument shell-quoted.

	Runs as root inside the container, and the arguments carry free text
	(the lab title, the owner's email).
	"""
	return "bash /opt/benchpress/scripts/linkuser.sh " + " ".join(shlex.quote(a) for a in script_args)


# The desk alert on a terminal deploy/build state. Shared with the enforcement sweep and the
# reaper, which announce the same kind of thing about the same documents.
_notify_owner = notify_owner


def create_site_in_container(
	container_id: str,
	db_server,
	site_name: str,
	admin_password: str,
	apps_csv: str,
	database: str | None = None,
	use_golden: bool = True,
) -> tuple[int, str]:
	"""Run setup-site.sh inside a bench container using a temporary MariaDB user.

	`database` overrides the name derived from the site, which the golden build needs so its
	scratch database is one this app is allowed to drop. `use_golden=False` makes the script
	create the site even in an image that carries a golden dump.
	"""
	bench_dir = "/home/frappe/frappe-bench"
	db_name, temp_user, temp_password = create_mariadb_user(db_server.name, site_name, database)
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
				"USE_GOLDEN": "1" if use_golden else "0",
			},
		)
	finally:
		drop_mariadb_user(db_server.name, site_name, db_name)


def _golden_matches_server(tag: str, db_server) -> tuple[bool, str]:
	"""Whether this image's dump may be restored into this server, and why not.

	The dump is the one artefact in the image whose validity depends on something outside it,
	so this is where a golden is refused. Every refusal is a slow deploy, never a failed one.
	"""
	from benchpress import golden

	if not golden.restore_enabled():
		return (
			False,
			"Restoring from a golden dump is turned off in BenchPress Settings — creating the site instead",
		)
	dump = golden.golden_mariadb_version(tag)
	if not dump:
		return False, ""  # the image step already named the missing golden and its remedy
	server = server_version(db_server.name)
	if not _major_version(dump) or not _major_version(server):
		return False, (
			f"Could not compare the golden dump's MariaDB ({dump or 'unknown'}) with this "
			f"server's ({server or 'unknown'}) — creating the site instead"
		)
	if _major_version(dump) != _major_version(server):
		return False, (
			f"Golden dump was taken from MariaDB {_major_version(dump)} and this server is "
			f"{_major_version(server)} — creating the site instead"
		)
	return True, ""


def _major_version(version: str) -> str:
	"""`10.6` out of `10.6.28-MariaDB-ubu2204`, or empty when there is no version in there.

	Major only: a patch bump is the same schema contract, and refusing on one would take every
	golden on the host out of service the next time the server is updated.
	"""
	match = re.match(r"\d+\.\d+", version or "")
	return match[0] if match else ""


def _site_outcome(output: str, site_name: str) -> str:
	"""Which of setup-site.sh's three branches ran. The Deploy Log is where that answer survives."""
	if GOLDEN_MARKER in output:
		return f"Site {site_name} {GOLDEN_RESTORED}"
	if ADOPTED_MARKER in output:
		return "Existing site adopted"
	return "Site created successfully"


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


def _start_code_server(bench, container_id: str, pipeline, settings) -> None:
	"""Configure code-server, launch it, and only then claim it is up.

	Every exec is checked. The config write decides whether code-server can authenticate at
	all, the `chown` decides whether it reads that file, and `restart.sh` is what actually
	launches it — a deploy that reports a `code_server_url` answering nothing is worse than
	one that fails here.

	The address is cleared before the attempt and stored after it, so a failed launch leaves
	the field empty and `LabHeader.showCodeServer` hides the button instead of offering a
	dead link.
	"""
	_forget_code_server_url(bench)
	cs_user = bench.ssh_username
	cs_home = f"/home/{cs_user}"
	code_server_password = secrets.token_urlsafe(16)
	config_yaml = f"bind-addr: 0.0.0.0:8080\nauth: password\npassword: {code_server_password}\ncert: false\n"
	config_path = f"{cs_home}/.config/code-server/config.yaml"

	write_file_to_container(container_id, config_yaml, config_path, mode=0o600)
	# The tar header set the mode, but `linkuser.sh` minted the tenant account and this
	# caller does not know its id, so the ownership fix still runs as its own exec.
	_checked_exec(
		container_id,
		f"chown -R {cs_user}:{cs_user} {cs_home}/.config",
		"Securing the code-server config",
	)
	_checked_exec(container_id, "bash /opt/benchpress/scripts/restart.sh", "restart.sh")

	bench.code_server_password = code_server_password
	bench.code_server_url = (
		addressing.public_ide_url(bench.name, settings.base_domain)
		or f"http://{bench.wg_ip or bench.container_ip or '127.0.0.1'}:8080/"
	)
	pipeline.log(f"code-server ready at {bench.code_server_url}")


def _forget_code_server_url(bench) -> None:
	"""Drop the address a previous deploy proved, in the row as well as in memory.

	The failure path reloads the instance before saving it, so an in-memory clear alone would
	be discarded and a redeploy that broke at this step would keep serving the old link.
	"""
	bench.code_server_url = None
	frappe.db.set_value("Bench Instance", bench.name, "code_server_url", None, update_modified=False)


def _checked_exec(container_id: str, command: str, what: str) -> None:
	"""Run a command in the container as root, raising with its output when it fails."""
	exit_code, output = exec_in_container(container_id, command, user="root")
	if exit_code != 0:
		raise Exception(f"{what} failed (exit {exit_code}): {output}")


def _record_primary_site(bench, lab, admin_password: str) -> None:
	"""Activate the `Bench Site` this deploy was admitted against, which every site list reads.

	Idempotent: a deploy re-runs, so an existing row is refreshed rather than duplicated.

	The owner is pinned to the bench's owner rather than left to the session: `Bench Site` grants
	`BenchPress User` read `if_owner`, so an admin redeploying somebody else's instance would
	take the row over and empty that tenant's Sites tab.
	"""
	site = site_names.claimed(bench)
	site.status = "Active"
	site.admin_password = admin_password
	site.owner = bench.owner
	site.apps_installed = []
	for app in _site_app_names(lab):
		site.append("apps_installed", {"app_name": app})
	site.save(ignore_permissions=True)
	# No commit: the next log line commits, and committing here outlives a test rollback
	# that discards the parent instance.


def _site_app_names(lab) -> list[str]:
	"""The apps this site was created with — frappe first, then the lab's own, in order."""
	extras = [row.app_name for row in (lab.apps or []) if row.app_name and row.app_name.lower() != "frappe"]
	return ["frappe", *extras]


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
	configure_container(container_id, peer["private_key"], peer["assigned_ip"], bench.bridge_network)
	pipeline.log(f"Container VPN: {peer['assigned_ip']}")


def teardown_bench(bench, *, release_admission: bool = True) -> None:
	"""Return an instance to `Draft`: container, volume and site database all gone.

	The one teardown path in the app. A redeploy runs it before building the instance again, and
	the reaper runs it and stops there — which is what makes a reaped instance one click from
	running: the `Lab` it was built from, with its apps, branches, version and size, is untouched.

	Every removal is best-effort. A volume that was already gone, or a database that never
	existed, must not leave the instance stuck describing resources it no longer has.

	`release_admission=False` keeps the concurrency slot, and only `_redeploy_bench` passes it:
	a redeploy is this plus a deploy, and the caller must not lose their own slot in between.
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

	try:
		# Direct, not enqueued: teardown must not leave live routing behind if a job is lost.
		ingress.withdraw(bench.name)
	except Exception:
		pass  # best-effort

	_drop_site_database(bench)
	# Marked, not deleted: a redeploy refreshes them, and the reaper leaves the instance
	# one click from running.
	_deactivate_bench_sites(bench)

	# The container this bench was burning for is gone, so the session ends here. Without
	# this the burning flag would survive the teardown and the fresh container — which
	# `_deploy_bench` bills through the same idempotence guard — would run unmetered.
	metering.on_bench_stopped(bench)

	if release_admission:
		admission.release(bench.name)

	bench.container_id = None
	bench.container_image = None
	bench.status = "Draft"
	bench.started_at = None
	bench.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- the caller may redeploy next, which must see Draft


def _deactivate_bench_sites(bench) -> None:
	"""Mark every `Bench Site` on this instance Inactive, since its data is gone.

	One UPDATE: `set_value` takes the filter itself, so the row names never have to be read.
	"""
	frappe.db.set_value("Bench Site", {"bench": bench.name}, "status", "Inactive", update_modified=False)


def _drop_site_database(bench) -> None:
	if not (bench.database_server and bench.site_name):
		return
	from benchpress.mariadb_manager import drop_site_database

	try:
		drop_site_database(bench.database_server, bench.site_name)
	except Exception:
		pass  # best-effort


def _prepare_lab_image(lab, pipeline, user: str) -> None:
	"""Use this lab's already-built image, or fail immediately — deploy never builds.

	Building is the explicit admin action (`build_lab`) alone; a deploy that finds no image, or
	finds a lab that isn't `Ready` (its spec changed since the last build — see
	`Lab.reset_status_if_spec_changed`), throws right away instead of eating a 10-40 minute build
	inside what the caller expects to be a fast operation.
	"""
	from benchpress.golden import image_has_golden

	tag, hit = image_cache.resolve(lab)
	if not hit or lab.status != "Ready" or lab.image_tag != tag:
		frappe.throw(_("No built image for lab '{0}'. Build it first from the Lab record.").format(lab.title))
	pipeline.log(f"Using built image {tag}")
	if not image_has_golden(tag):
		pipeline.log(
			f"No golden dump in {tag} — this site is built from scratch. "
			"Rebuild the lab, or run Build golden, to make its deploys ~5x faster."
		)


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

	# After the lab is Ready with its tag saved: the golden step appends a layer to that tag,
	# and needs the row that names it.
	_add_golden(lab, log_fn)


def _add_golden(lab, log_fn) -> None:
	"""Bake the golden into the image this build just produced, and record what was baked.

	Never raises, and the `except` is not belt and braces: everything above it has already been
	committed, so letting the row write escape would make `_run_build` mark a finished image as a
	failed build and put the lab's status back.
	"""
	from benchpress import golden

	try:
		manifest = golden.add_golden(lab, log_fn)
		lab.reload()
		# Written either way: this build replaced the image under the same tag, so a manifest left
		# over from the last one would claim a golden that is no longer in there.
		lab.golden_manifest = json.dumps(manifest, indent=2) if manifest else None
		lab.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Golden manifest not recorded: {lab.name}", message=frappe.get_traceback())


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

	A failure puts the lab's status back the way it was found. `Lab` is one admin-authored row
	every tenant reads, and `_build_lab_with_logs` moves it to Building before it starts, so a
	tenant whose deploy had to build would otherwise leave the whole catalog reading Error.
	`build_lab`, the admin's own rebuild, is what records Error there.
	"""
	status_before = lab.status
	append_log, build_log_name = _open_build_log(lab, user)
	try:
		_build_lab_with_logs(lab, append_log)
	except Exception as e:
		frappe.db.set_value("Lab", lab.name, "status", status_before)
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
		# The admin asked for this build, so the catalog is the right place to record that it broke.
		frappe.db.set_value("Lab", lab_name, "status", "Error")
		frappe.db.commit()  # nosemgrep -- the run is over; its verdict must survive the failure
		_notify_owner(lab.owner, f"Lab build failed: {lab.title}", "Lab", lab_name)
		return
	_notify_owner(lab.owner, f"Lab build complete: {lab.title} ({image_tag})", "Lab", lab_name)


def stop_bench(bench_name: str, from_claim: bool = False) -> None:
	"""Stop a bench container, and with it every site the container was serving.

	VPN stops automatically with the container. The sites do not: nothing answers on a stopped
	container, so a row left `Active` is the page telling the user to open an address that has
	gone quiet. This is the one stop path — `api.bench_action("stop")` routes here too — so the
	deactivation cannot be missed by a second caller.

	It is also where an expired lease lands, which is why it starts by confirming the claim
	under a row lock. `from_claim` marks that caller: a user pressing Stop carries no claim and
	always goes ahead, while a queued expiry that has outlived its claim must not.
	"""
	if not lease.confirm_expiry(bench_name, from_claim=from_claim):
		return

	lease.record_stop_started(bench_name)
	bench = frappe.get_doc("Bench Instance", bench_name)
	lease.assert_local(bench)
	expired = bench.lease_state == lease.STOPPING

	try:
		if bench.container_id:
			stop_container(bench.container_id)
	except Exception:
		if expired:
			lease.release(bench_name, failed=True)
			frappe.db.commit()  # nosemgrep -- the retry has to survive the failure that caused it
		raise

	lease.record_stopped(bench, expired)
	bench.status = "Stopped"
	metering.on_bench_stopped(bench)
	# Stopped is free, so it must stop holding a slot too: a caller at their cap who stops
	# everything they own would otherwise never start anything again.
	admission.release(bench.name)
	bench.save(ignore_permissions=True)
	_deactivate_bench_sites(bench)
	if expired:
		lease.announce_expired(bench)
	frappe.db.commit()  # nosemgrep -- intentional commit to persist status before response
	ingress.enqueue_route_sync(bench.name)
