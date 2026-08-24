# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import os
import secrets
import shlex
import socket
import ssl
from pathlib import Path

import frappe
import yaml
from frappe import _
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

# Kept in step with `frontend/src/utils/labActions.js`, which builds the URL from it.
SITE_HTTP_PORT = 8000

ADOPTED_MARKER = "already exists — adopting it"

# Module constant, not inlined, so tests can monkeypatch it to a tmp path.
# Flat, not a subdirectory: Traefik's file provider does not recurse, so this
# must be the exact directory the `directory:` provider in traefik.yml.template
# watches, and the exact host path bind-mounted read-write into queue-long /
# read-only into traefik in docker-compose.prod.yml. dynamic.yml (the
# control-plane router) lives in this same directory.
TRAEFIK_DYNAMIC_DIR = Path("/etc/traefik/dynamic")

# One file, one router, one identity set — the only place in this app that names a
# certificate resolver. Fixed name so it is idempotently overwritten and can never
# collide with an instance file, which is always a 32-character hex id.
WILDCARD_ANCHOR_FILE = "wildcard-anchor.yml"

# The parent repo renders the control plane's own router into this same flat directory.
# It is not this app's to write and not this app's to remove.
CONTROL_PLANE_ROUTE_FILE = "dynamic.yml"

# The two files `reconcile_instance_routes` must never delete, named one by one rather
# than matched by shape. Deleting `dynamic.yml` takes the control plane off the internet;
# deleting the anchor takes every bench's certificate with it. A filename pattern is a
# guess about what future files will look like — a set is a decision about these two.
PROTECTED_ROUTE_FILES = frozenset({CONTROL_PLANE_ROUTE_FILE, WILDCARD_ANCHOR_FILE})

# Traefik's compose service name. queue-long and traefik both sit on frappe_network, so
# this resolves; it is the same TLS endpoint the internet reaches, which is the point —
# checking anything else would prove something else.
TRAEFIK_HOST = "traefik"


def _public_site_url(instance_id: str, base_domain: str | None) -> str | None:
	if not base_domain or base_domain == "localhost":
		return None
	return f"https://{instance_id}.{base_domain}"


def _public_ide_url(instance_id: str, base_domain: str | None) -> str | None:
	if not base_domain or base_domain == "localhost":
		return None
	return f"https://ide-{instance_id}.{base_domain}"


def _wildcard_anchor_config(base_domain: str) -> dict:
	"""The router whose only job is to hold `*.{base_domain}` in Traefik's store.

	`domains` is a fixed list, so the resolver is asked for exactly one identity set no
	matter what arrives. That is the whole safety property: a router that names a
	resolver and *omits* `domains` makes Traefik issue per-SNI on demand, which is how a
	stranger pointing DNS at this host burns the weekly certificate budget.

	The router is inert by construction. Traefik's default priority is the rule length
	and every instance rule is 40+ characters, so `priority: 1` can never win a tie (0 is
	ignored, so 1 is the floor). The backend is a dead address on purpose:
	`*.{base_domain}` is wildcard-resolved, so `tls-anchor.{base_domain}` does answer, and
	pointing it at the control plane would publish an unadvertised way in. A 502 is the
	honest reply for a name that exists only to own a certificate. The service is still
	*defined*, because Traefik drops a router naming an undefined service — and a dropped
	router would take the certificate request with it.
	"""
	return {
		"http": {
			"routers": {
				"benchpress-wildcard-anchor": {
					"rule": f"Host(`tls-anchor.{base_domain}`)",
					"entryPoints": ["websecure"],
					"priority": 1,
					"service": "benchpress-wildcard-anchor",
					"tls": {
						"certResolver": "letsencrypt",
						"domains": [{"main": base_domain, "sans": [f"*.{base_domain}"]}],
					},
				}
			},
			"services": {
				"benchpress-wildcard-anchor": {"loadBalancer": {"servers": [{"url": "http://127.0.0.1:1"}]}}
			},
		}
	}


def _atomic_write(path: Path, text: str) -> None:
	"""Replace `path` in one step, so Traefik never reads a half-written file."""
	# Traefik's file provider parses only .yml, .yaml, .toml and .json, so the temp name is
	# structurally invisible to the watcher rather than merely unlikely to be read.
	tmp = path.with_name(f".{path.name}.tmp")
	tmp.write_text(text)
	os.replace(tmp, path)


def _ensure_wildcard_anchor(base_domain: str | None) -> bool:
	"""Put the bench-zone wildcard in Traefik's certificate store, once.

	Returns True when the file was written. Rewrites only on a real change: Traefik
	reloads on mtime, and a deploy has no business making it reload to say nothing.

	Never deleted at teardown — it has to outlive every bench, because it is what keeps
	the certificate renewing.
	"""
	if not base_domain or base_domain == "localhost":
		return False

	wanted = yaml.safe_dump(_wildcard_anchor_config(base_domain))
	path = TRAEFIK_DYNAMIC_DIR / WILDCARD_ANCHOR_FILE
	if path.exists() and path.read_text() == wanted:
		return False

	TRAEFIK_DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
	_atomic_write(path, wanted)
	return True


def _write_instance_route(instance_id: str, base_domain: str) -> None:
	"""Write Traefik file-provider routes for this instance's site and its code-server IDE.

	`tls: {}` turns TLS on and names no resolver, so these routers serve whatever
	certificate the store already holds for the requested SNI. Deliberate, and the point
	of the whole design: Let's Encrypt allows five certificates per identifier set per
	seven days, so a router that asked for one would cap bench churn at five a week.
	`_ensure_wildcard_anchor` is what puts `*.{base_domain}` in the store, and it is the
	only place in this app that names a resolver.

	The file is a pure function of `(instance_id, base_domain)`: it names the container,
	never an address, so no lifecycle transition can make it stale. The container name
	*is* `instance_id` — `create_bench_container` names it `bench_doc.bench_name` and
	`BenchInstance.autoname` sets `name = bench_name`.
	"""
	if not base_domain or base_domain == "localhost":
		return

	TRAEFIK_DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
	config = {
		"http": {
			"routers": {
				f"site-{instance_id}": {
					"rule": f"Host(`{instance_id}.{base_domain}`)",
					"entryPoints": ["websecure"],
					"service": f"site-{instance_id}",
					"tls": {},
				},
				f"ide-{instance_id}": {
					"rule": f"Host(`ide-{instance_id}.{base_domain}`)",
					"entryPoints": ["websecure"],
					"service": f"ide-{instance_id}",
					"tls": {},
				},
			},
			# Resolved by Docker's embedded DNS: traefik is on the `benchpress` network.
			"services": {
				f"site-{instance_id}": {
					"loadBalancer": {"servers": [{"url": f"http://{instance_id}:{SITE_HTTP_PORT}"}]}
				},
				f"ide-{instance_id}": {"loadBalancer": {"servers": [{"url": f"http://{instance_id}:8080"}]}},
			},
		}
	}
	_atomic_write(TRAEFIK_DYNAMIC_DIR / f"{instance_id}.yml", yaml.safe_dump(config))


def _delete_instance_route(instance_id: str) -> None:
	"""Remove this instance's Traefik route file, if any.

	The route names the container, so a file left behind after teardown resolves to
	nothing and 502s rather than reaching another tenant. Still deleted at teardown:
	a hostname that answers at all outlives the bench it was issued for.
	"""
	(TRAEFIK_DYNAMIC_DIR / f"{instance_id}.yml").unlink(missing_ok=True)


def reconcile_instance_routes() -> dict:
	"""Make the Traefik route directory agree with the database.

	The Bench Instance table is the truth and the directory follows it. Containers are not
	inspected — an orphaned container is a real problem, but it is todo item 8's, and a
	pass that quietly took on two jobs would be harder to trust with either. Returns counts
	rather than a bare success: a reaper that reports "issued" instead of "converged" is how
	a directory drifts for weeks without anyone noticing.

	Deleting is the load-bearing half. Routes name containers, so a file left behind is a
	502 rather than another tenant's site — but it is still a public hostname answering
	for a bench that no longer exists, and only this pass removes one nothing deleted.

	Must run on `queue-long`: it is the only container that mounts the route directory
	read-write. That is also what keeps this from racing a deploy — both are `long` jobs
	on a single worker, so a bench part-way through `_deploy_bench` is never read here
	between its container IP being known and its status reaching `Running`.

	Run it by hand with:
	    bench --site frontend execute benchpress.deploy_manager.reconcile_instance_routes
	"""
	base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
	anchored = _ensure_wildcard_anchor(base_domain)
	if not base_domain or base_domain == "localhost":
		# A dev checkout has no route directory and must stay byte-for-byte unaffected —
		# skipped silently, exactly as the writers skip it.
		return {"anchored": anchored, "written": 0, "deleted": 0, "kept": 0}

	routable = _routable_instance_ips()
	for instance_id in routable:
		_write_instance_route(instance_id, base_domain)

	deleted = kept = 0
	for path in sorted(TRAEFIK_DYNAMIC_DIR.glob("*.yml")):
		if path.name in PROTECTED_ROUTE_FILES:
			kept += 1
			continue
		if path.stem in routable:
			continue
		_delete_instance_route(path.stem)
		deleted += 1

	return {"anchored": anchored, "written": len(routable), "deleted": deleted, "kept": kept}


def _routable_instance_ips() -> dict[str, str]:
	"""Every bench that should own a route file, mapped to the address it should point at.

	`Running` and nothing else. A `Stopped`, `Draft` or `Error` bench has no container
	answering, and its recorded `container_ip` is a freed address Docker is free to hand
	to somebody else's bench — which is the misroute, not a dead link. A row with no IP
	at all is dropped for the same reason a route to nowhere is worse than no route.
	"""
	instance = frappe.qb.DocType("Bench Instance")
	rows = (
		frappe.qb.from_(instance)
		.select(instance.name, instance.container_ip)
		.where(instance.status == "Running")
	).run(as_dict=True)
	return {row.name: row.container_ip for row in rows if row.container_ip}


def _log_certificate_state(instance_id: str, base_domain: str | None, pipeline) -> None:
	"""State in the deploy log which certificate this bench's URL will be served on.

	The instance routers name no resolver, so they serve whatever the store already holds.
	That reliance is otherwise invisible: if the store were ever wrong the first evidence
	would be a user meeting Cloudflare's 526, which names neither TLS nor a certificate.

	Only the site hostname is checked. The IDE hostname is one label under the same
	`base_domain` and so is covered by the same wildcard — a second handshake would only
	re-prove the first one.
	"""
	if not base_domain or base_domain == "localhost":
		return

	hostname = f"{instance_id}.{base_domain}"
	error = _certificate_error(hostname)
	if error:
		pipeline.log(f"WARNING: {error} — the public URL will fail in a browser")
		return

	pipeline.log(f"TLS ready for {hostname} on the *.{base_domain} wildcard")


def _certificate_error(hostname: str, timeout: int = 5) -> str | None:
	"""Return why `hostname`'s certificate is unusable, or None when it is fine.

	Verifies the way a browser does — full chain and hostname match — against the same TLS
	endpoint the internet reaches. The store is matched by SNI independently of routing, so
	this does not race Traefik's file watcher and needs no Traefik API, which this
	deployment deliberately does not expose.

	Reports rather than raises. A certificate problem must not fail a deploy whose container
	is up and whose site exists; the owner can still work over the VPN, and the log is where
	an operator looks.
	"""
	context = ssl.create_default_context()
	try:
		with socket.create_connection((TRAEFIK_HOST, 443), timeout=timeout) as raw:
			with context.wrap_socket(raw, server_hostname=hostname):
				return None
	except ssl.SSLCertVerificationError as exc:
		# `verify_message` is set by the C module on a real handshake failure but is absent
		# on an exception built any other way, and a bare attribute read there would raise
		# out of the handler — the one thing this function must never do.
		return f"certificate does not cover {hostname} ({getattr(exc, 'verify_message', None) or exc})"
	except OSError as exc:
		# Timeout, refused connection and DNS failure all mean "could not check", not
		# "certificate is bad". A dev checkout has no Traefik at all, so this is its
		# normal path — the two causes call for different actions and must stay apart.
		return f"could not reach Traefik to check {hostname} ({exc})"


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
	container_id: str, db_server, site_name: str, admin_password: str, apps_csv: str
) -> tuple[int, str]:
	"""Run setup-site.sh inside a bench container using a temporary MariaDB user."""
	bench_dir = "/home/frappe/frappe-bench"
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

		# First step of the deploy, so this runs minutes ahead of the image build —
		# headroom a fresh install needs, because DNS-01 has to finish issuing before
		# the bench route goes live.
		settings = frappe.get_cached_doc("BenchPress Settings")
		if _ensure_wildcard_anchor(settings.base_domain):
			pipeline.log(f"Traefik wildcard anchor written for *.{settings.base_domain}")

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

		bench.public_url = _public_site_url(bench.name, settings.base_domain)
		_write_instance_route(bench.name, settings.base_domain)
		_log_certificate_state(bench.name, settings.base_domain, pipeline)

		_setup_container_vpn(bench, container_id, pipeline)

		bench_dir = "/home/frappe/frappe-bench"
		site_name = bench.site_name
		config = {
			**db_server.get_connection_config(),
			"redis_cache": "redis://benchpress-redis:6379/0",
			"redis_queue": "redis://benchpress-redis:6379/1",
			"redis_socketio": "redis://benchpress-redis:6379/2",
			"socketio_port": 9000,
			"webserver_port": SITE_HTTP_PORT,
			"default_site": site_name,
		}
		pipeline.step("site_config")
		write_file_to_container(
			container_id, json.dumps(config, indent=2), f"{bench_dir}/sites/common_site_config.json"
		)
		pipeline.log(f"{bench_dir}/sites/common_site_config.json written")

		pipeline.step("site")
		# Drop the leftover of an interrupted run; `bench new-site` refuses to overwrite it.
		_drop_site_database(bench)
		apps_csv = ",".join(a.app_name for a in lab.apps if a.app_name.lower() != "frappe")
		pipeline.log(f"Site {site_name} with {apps_csv or 'frappe'}")
		exit_code, output = create_site_in_container(
			container_id, db_server, site_name, admin_password, apps_csv
		)
		if exit_code != 0:
			raise Exception(f"Site setup failed (exit {exit_code}): {output}")
		pipeline.log("Existing site adopted" if ADOPTED_MARKER in output else "Site created successfully")
		_record_primary_site(bench, lab, admin_password)

		pipeline.step("assets")
		# Deploy never builds; rebuilding the lab image is how a stale bundle is refreshed.
		pipeline.log("Assets ship in the image — bundled at build time")

		if not bench.ssh_username:
			bench.ssh_username = bench._derive_username(bench.owner)

		ssh_password = secrets.token_urlsafe(12)
		linkuser_args = build_linkuser_args(bench, lab, settings, ssh_password)
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
		exit_code, output = exec_in_container(container_id, linkuser_cmd, user="root")
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
		pipeline.log(f"Site served on port {SITE_HTTP_PORT}")

		if getattr(lab, "enable_code_server", 0):
			_start_code_server(bench, container_id, pipeline, settings)
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


def _start_code_server(bench, container_id: str, pipeline, settings) -> None:
	"""Configure code-server, launch it, and only then claim it is up.

	Every exec is checked. The config write decides whether code-server can authenticate at
	all, the `chown`/`chmod` decides whether it reads that file or leaks the password to every
	account in the container, and `restart.sh` is what actually launches it — a deploy that
	reports a `code_server_url` answering nothing is worse than one that fails here.

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

	write_file_to_container(container_id, config_yaml, config_path)
	_checked_exec(
		container_id,
		f"chown -R {cs_user}:{cs_user} {cs_home}/.config && chmod 600 {config_path}",
		"Securing the code-server config",
	)
	_checked_exec(container_id, "bash /opt/benchpress/scripts/restart.sh", "restart.sh")

	bench.code_server_password = code_server_password
	bench.code_server_url = (
		_public_ide_url(bench.name, settings.base_domain)
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
	"""Record the deploy's site as a `Bench Site`, which is what every site list reads.

	Idempotent: a deploy re-runs, so an existing row is refreshed rather than duplicated.

	The owner is pinned to the bench's owner rather than left to the session: `Bench Site` grants
	`BenchPress User` read `if_owner`, so an admin redeploying somebody else's instance would
	take the row over and empty that tenant's Sites tab.
	"""
	existing = frappe.db.get_value("Bench Site", {"bench": bench.name, "site_name": bench.site_name})
	site = frappe.get_doc("Bench Site", existing) if existing else frappe.new_doc("Bench Site")
	site.bench = bench.name
	site.site_name = bench.site_name
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

	try:
		_delete_instance_route(bench.name)
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
	tag, hit = image_cache.resolve(lab)
	if not hit or lab.status != "Ready" or lab.image_tag != tag:
		frappe.throw(_("No built image for lab '{0}'. Build it first from the Lab record.").format(lab.title))
	pipeline.log(f"Using built image {tag}")


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


def stop_bench(bench_name: str) -> None:
	"""Stop a bench container, and with it every site the container was serving.

	VPN stops automatically with the container. The sites do not: nothing answers on a stopped
	container, so a row left `Active` is the page telling the user to open an address that has
	gone quiet. This is the one stop path — `api.bench_action("stop")` routes here too — so the
	deactivation cannot be missed by a second caller.
	"""
	bench = frappe.get_doc("Bench Instance", bench_name)

	if bench.container_id:
		stop_container(bench.container_id)

	bench.status = "Stopped"
	metering.on_bench_stopped(bench)
	bench.save(ignore_permissions=True)
	_deactivate_bench_sites(bench)
	frappe.db.commit()  # nosemgrep -- intentional commit to persist status before response
