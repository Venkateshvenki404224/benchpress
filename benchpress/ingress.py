# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The public front door for a bench: every write to the Traefik route directory.

The directory path and the set of files that must never be deleted live here and
nowhere else, so a caller that wants to know what is published asks `published()`
rather than learning the path.
"""

import os
import socket
import ssl
from pathlib import Path

import frappe
import yaml

from benchpress import addressing

# Module constant, not inlined, so tests can monkeypatch it to a tmp path.
# Flat, not a subdirectory: Traefik's file provider does not recurse, so this must be the
# exact directory the `directory:` provider in traefik.yml.template watches. dynamic.yml
# (the control-plane router) lives in this same directory.
TRAEFIK_DYNAMIC_DIR = Path("/etc/traefik/dynamic")

# One file, one router, one identity set — the only place in this app that names a
# certificate resolver. Fixed name so it is idempotently overwritten and can never
# collide with an instance file, which is always a 32-character hex id.
WILDCARD_ANCHOR_FILE = "wildcard-anchor.yml"

# The parent repo renders the control plane's own router into this same flat directory.
# It is not this app's to write and not this app's to remove.
CONTROL_PLANE_ROUTE_FILE = "dynamic.yml"

# The two files `reconcile` must never delete, named one by one rather
# than matched by shape. Deleting `dynamic.yml` takes the control plane off the internet;
# deleting the anchor takes every bench's certificate with it. A filename pattern is a
# guess about what future files will look like — a set is a decision about these two.
PROTECTED_ROUTE_FILES = frozenset({CONTROL_PLANE_ROUTE_FILE, WILDCARD_ANCHOR_FILE})

# Traefik's compose service name. queue-long and traefik both sit on frappe_network, so
# this resolves; it is the same TLS endpoint the internet reaches, which is the point —
# checking anything else would prove something else.
TRAEFIK_HOST = "traefik"


class TraefikRouteDirectoryMissing(Exception):
	"""Raised when the Traefik route directory is not mounted in this container.

	`queue-long` mounts it read-write and traefik read-only; `backend` and
	`queue-short` mount neither, and both consume `default`. Every caller therefore
	reaches routing through `enqueue_route_sync`, which pins `queue="long"`.
	"""


def publish(instance_id: str, base_domain: str) -> None:
	"""Write Traefik file-provider routes for this instance's site and its code-server IDE.

	`tls: {}` turns TLS on and names no resolver, so these routers serve whatever
	certificate the store already holds for the requested SNI. Deliberate, and the point
	of the whole design: Let's Encrypt allows five certificates per identifier set per
	seven days, so a router that asked for one would cap bench churn at five a week.
	`ensure_anchor` is what puts `*.{base_domain}` in the store, and it is the
	only place in this app that names a resolver.

	The file is a pure function of `(instance_id, base_domain)`: it names the container,
	never an address, so no lifecycle transition can make it stale. The container name
	*is* `instance_id` — `create_bench_container` names it `bench_doc.bench_name` and
	`BenchInstance.autoname` sets `name = bench_name`.
	"""
	if not base_domain or base_domain == "localhost":
		return

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
					"loadBalancer": {
						"servers": [{"url": f"http://{instance_id}:{addressing.SITE_HTTP_PORT}"}]
					}
				},
				f"ide-{instance_id}": {
					"loadBalancer": {"servers": [{"url": f"http://{instance_id}:{addressing.IDE_HTTP_PORT}"}]}
				},
			},
		}
	}
	_atomic_write(TRAEFIK_DYNAMIC_DIR / f"{instance_id}.yml", yaml.safe_dump(config))


def withdraw(instance_id: str) -> None:
	"""Remove this instance's Traefik route file, if any.

	The route names the container, so a file left behind after teardown resolves to
	nothing and 502s rather than reaching another tenant. Still deleted at teardown:
	a hostname that answers at all outlives the bench it was issued for.
	"""
	(TRAEFIK_DYNAMIC_DIR / f"{instance_id}.yml").unlink(missing_ok=True)


def published() -> set[str]:
	"""The instance ids that own a route file."""
	return {path.stem for path in TRAEFIK_DYNAMIC_DIR.glob("*.yml") if path.name not in PROTECTED_ROUTE_FILES}


def protected_present() -> int:
	"""How many protected files the directory holds, for the reconcile report."""
	return sum(1 for name in PROTECTED_ROUTE_FILES if (TRAEFIK_DYNAMIC_DIR / name).exists())


def ensure_anchor(base_domain: str | None) -> bool:
	"""Put the bench-zone wildcard in Traefik's certificate store, once; True when written.

	Never deleted at teardown — it has to outlive every bench, because it is what keeps
	the certificate renewing.
	"""
	if not base_domain or base_domain == "localhost":
		return False

	wanted = yaml.safe_dump(_wildcard_anchor_config(base_domain))
	return _atomic_write(TRAEFIK_DYNAMIC_DIR / WILDCARD_ANCHOR_FILE, wanted)


def log_certificate_state(instance_id: str, base_domain: str | None, pipeline) -> None:
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


def _atomic_write(path: Path, text: str) -> bool:
	"""Replace `path` in one step if the content differs; returns True when it wrote.

	Traefik reloads on mtime, so an unchanged file is left alone — otherwise the
	convergence cron would make the proxy reload every five minutes to say nothing.

	Raises `TraefikRouteDirectoryMissing` rather than creating the directory: a bind mount
	that is absent is a container that cannot reach Traefik, and creating it would turn
	that into a file nobody reads.
	"""
	if not path.parent.is_dir():
		raise TraefikRouteDirectoryMissing(
			f"{path.parent} is not mounted in this container. It is a bind mount of "
			"config/traefik/generated/dynamic, read-write only in queue-long, so the fix is "
			"to reach routing through enqueue_route_sync — never to create the directory."
		)

	if path.exists() and path.read_text() == text:
		return False

	# Traefik's file provider parses only .yml, .yaml, .toml and .json, so the temp name is
	# structurally invisible to the watcher rather than merely unlikely to be read.
	tmp = path.with_name(f".{path.name}.tmp")
	tmp.write_text(text)
	os.replace(tmp, path)
	return True


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


def sync_instance_route(bench_name: str) -> str:
	"""Make this bench's route file agree with its status; returns `written`, `deleted` or `skipped`.

	The one decision point for whether a bench should own a route at all, so a lifecycle
	transition has one thing to remember rather than a write call in the start path and a
	delete call in the stop path. A bench that no longer exists reads as no status, which
	deletes — the same answer as `Stopped`, and the reason this does not raise.

	Reach it through `enqueue_route_sync`, never directly from a web request.
	"""
	base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
	if not base_domain or base_domain == "localhost":
		return "skipped"

	if frappe.db.get_value("Bench Instance", bench_name, "status") == "Running":
		publish(bench_name, base_domain)
		return "written"

	withdraw(bench_name)
	return "deleted"


def enqueue_route_sync(bench_name: str) -> None:
	"""Hand the route write to `queue-long` — see `TraefikRouteDirectoryMissing`."""
	frappe.enqueue(
		"benchpress.ingress.sync_instance_route",
		bench_name=bench_name,
		queue="long",
		job_id=f"route_sync:{bench_name}",
		deduplicate=True,
		enqueue_after_commit=True,  # the job re-reads `status`, so it must not start before the commit
	)


def enqueue_route_reconcile() -> None:
	"""Convergence cron: hand the whole-directory pass to `queue-long`."""
	# Scheduled jobs land on `default`, which `queue-short` also consumes — so the cron entry
	# is this enqueuer and never the pass itself. See `TraefikRouteDirectoryMissing`.
	frappe.enqueue(
		"benchpress.ingress.reconcile",
		queue="long",
		job_id="route_reconcile",
		deduplicate=True,
	)


def reconcile() -> dict:
	"""Make the Traefik route directory agree with the database.

	The Bench Instance table is the truth and the directory follows it. Containers are not
	inspected — an orphaned container is a real problem, but it is todo item 8's, and a
	pass that quietly took on two jobs would be harder to trust with either. Returns counts
	rather than a bare success: a reaper that reports "issued" instead of "converged" is how
	a directory drifts for weeks without anyone noticing.

	Deleting is the load-bearing half. Routes name containers, so a file left behind is a
	502 rather than another tenant's site — but it is still a public hostname answering
	for a bench that no longer exists, and only this pass removes one nothing deleted.

	Running on `queue-long` is also what keeps this from racing a deploy — both are `long`
	jobs on a single worker, so a bench part-way through `_deploy_bench` is never read here
	between its container being created and its status reaching `Running`.

	Run it by hand with:
	    bench --site frontend execute benchpress.ingress.reconcile
	"""
	# Lazy: deploy_manager imports this module, and item 17 moves this function to placement.
	from benchpress.deploy_manager import _reconcile_bridge_attachments

	# Ahead of the base_domain guard because this half is about container networking rather
	# than routing: a bench that cannot reach MariaDB is broken on a dev checkout too.
	attached = _reconcile_bridge_attachments()

	base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
	anchored = ensure_anchor(base_domain)
	if not base_domain or base_domain == "localhost":
		# A dev checkout has no route directory and must stay byte-for-byte unaffected —
		# skipped silently, exactly as the writers skip it.
		return {"anchored": anchored, "written": 0, "deleted": 0, "kept": 0, **attached}

	routable = _routable_instance_ips()
	for instance_id in routable:
		publish(instance_id, base_domain)

	stale = published() - routable.keys()
	for instance_id in stale:
		withdraw(instance_id)

	return {
		"anchored": anchored,
		"written": len(routable),
		"deleted": len(stale),
		"kept": protected_present(),
		**attached,
	}


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
