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
from typing import NamedTuple

import frappe
import yaml
from frappe.utils import cint

from benchpress import addressing

# By name rather than `from benchpress.credits import config`: a route mapping is what
# `config` wants to name in this file, and a module bound to that name turns the next such
# local into an F823.
from benchpress.credits.config import size_for_lab, size_index

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

# The two files the convergence pass must never delete, named one by one rather
# than matched by shape. Deleting `dynamic.yml` takes the control plane off the internet;
# deleting the anchor takes every bench's certificate with it. A filename pattern is a
# guess about what future files will look like — a set is a decision about these two.
PROTECTED_ROUTE_FILES = frozenset({CONTROL_PLANE_ROUTE_FILE, WILDCARD_ANCHOR_FILE})

# Traefik's compose service name. queue-long and traefik both sit on frappe_network, so
# this resolves; it is the same TLS endpoint the internet reaches, which is the point —
# checking anything else would prove something else.
TRAEFIK_HOST = "traefik"

# Each service probes the path it serves, verified 200 inside a live bench. Pointing both at
# the site path would eject a working code-server every time gunicorn hiccuped, and pointing
# the site at /healthz would eject nothing, because code-server answers it while Frappe is dead.
SITE_HEALTH_PATH = "/api/method/ping"
IDE_HEALTH_PATH = "/healthz"

DEFAULT_TRAEFIK_HEALTH_INTERVAL = 10
DEFAULT_TRAEFIK_HEALTH_TIMEOUT = 3

# What a browser fetches without rendering a page, split onto their own router so the in-flight
# cap lands on the render path alone — one that also counted a tab's nine assets would 429 the
# tab. `/private/files` is deliberately absent: it needs a permission check, and
# PathPrefix(`/files`) does not match it anyway.
ASSET_PATH_PREFIXES = ("/assets", "/files")

# Traefik's default priority is the rule length, so a long enough base domain would let the
# bare host rule out-rank the longer assets rule and the split would silently do nothing.
# Both are stated rather than left to be derived.
ROUTER_PRIORITY = 100
ASSETS_ROUTER_PRIORITY = 200

# Counted from the right, so 1 is Cloudflare's view of the client. A client-supplied
# X-Forwarded-For arrives to the *left* of the real address, which makes depth 2 spoofable.
CLIENT_IP_DEPTH = 1

# Traefik reads `average: 0` as no limit at all, so an `Instance Size` row nobody seeded would
# publish a route with the brake off. These are the floor under that, not a tier's choice.
DEFAULT_RATE_AVERAGE = 20
DEFAULT_RATE_BURST = 60

# A platform safety clamp rather than a tier's choice, which is why it is a constant here and not
# an `Instance Size` field: 151 shared database connections ÷ 24 is 6.3 simultaneously-saturated
# benches against a host that holds about 6, so an operator who could raise it from Desk could
# exhaust the pool.
INFLIGHT_CEILING = 24


class RateLimits(NamedTuple):
	"""The per-tier request numbers a bench's routers carry. An `inflight` of 0 is no cap at all."""

	average: int
	burst: int
	inflight: int


DEFAULT_RATE_LIMITS = RateLimits(DEFAULT_RATE_AVERAGE, DEFAULT_RATE_BURST, inflight=0)


class TraefikRouteDirectoryMissing(Exception):
	"""Raised when the Traefik route directory is not mounted in this container.

	`queue-long` mounts it read-write and traefik read-only; `backend` and
	`queue-short` mount neither, and both consume `default`. Every caller therefore
	reaches routing through `enqueue_route_sync`, which pins `queue="long"`.
	"""


def publish(
	instance_id: str,
	base_domain: str,
	ide: bool | None = None,
	limits: RateLimits | None = None,
) -> None:
	"""Write Traefik file-provider routes for this instance's site, and its IDE when it has one.

	`tls: {}` turns TLS on and names no resolver, so these routers serve whatever
	certificate the store already holds for the requested SNI. Deliberate, and the point
	of the whole design: Let's Encrypt allows five certificates per identifier set per
	seven days, so a router that asked for one would cap bench churn at five a week.
	`ensure_anchor` is what puts `*.{base_domain}` in the store, and it is the
	only place in this app that names a resolver.

	The file names the container, never an address, so no lifecycle transition can make
	it stale. The container name *is* `instance_id` — `create_bench_container` names it
	`bench_doc.bench_name` and `BenchInstance.autoname` sets `name = bench_name`.
	"""
	if not base_domain or base_domain == "localhost":
		return

	# What `routable` already resolved for this bench, else the same read for one.
	# Never the caller's own idea of the flag: the */5 pass writes this file without the
	# deploy's context, and two writers that disagree overwrite each other every five minutes.
	if ide is None:
		ide = has_ide(instance_id)
	if limits is None:
		limits = rate_limits(instance_id)

	site = f"site-{instance_id}"
	host = f"Host(`{instance_id}.{base_domain}`)"
	asset_paths = " || ".join(f"PathPrefix(`{prefix}`)" for prefix in ASSET_PATH_PREFIXES)

	middlewares = {
		f"{instance_id}-rl-site": _rate_limit(limits),
		f"{instance_id}-rl-assets": _rate_limit(limits),
	}

	# The render path alone, and only when its tier sets a number. An unseeded row is an operator
	# who has not chosen, so it gets no middleware rather than a default nobody asked for.
	site_middlewares = [f"{instance_id}-rl-site"]
	if limits.inflight:
		# After the rate limit, not before: Traefik runs the chain in order, so a request the
		# rate limit is about to refuse never takes an in-flight slot to be refused in.
		site_middlewares.append(f"{instance_id}-inflight")
		middlewares[f"{instance_id}-inflight"] = _in_flight(limits.inflight)

	# Both routers name the same service: the split is about what a request costs, not where
	# it goes.
	routers = {
		site: _router(host, site, site_middlewares, ROUTER_PRIORITY),
		f"assets-{instance_id}": _router(
			f"{host} && ({asset_paths})",
			site,
			[f"{instance_id}-rl-assets"],
			ASSETS_ROUTER_PRIORITY,
		),
	}
	# Resolved by Docker's embedded DNS: traefik is on the `benchpress` network.
	services = {
		site: {
			"loadBalancer": {
				"servers": [{"url": f"http://{instance_id}:{addressing.SITE_HTTP_PORT}"}],
				"healthCheck": _service_health(SITE_HEALTH_PATH),
			}
		}
	}

	if ide:
		# Never an `inFlightReq` here: code-server holds one upgraded connection for the whole
		# session, so any cap would count sessions and 429 the one after it.
		routers[f"ide-{instance_id}"] = _router(
			f"Host(`ide-{instance_id}.{base_domain}`)",
			f"ide-{instance_id}",
			[f"{instance_id}-rl-ide"],
			ROUTER_PRIORITY,
		)
		middlewares[f"{instance_id}-rl-ide"] = _rate_limit(limits)
		services[f"ide-{instance_id}"] = {
			"loadBalancer": {
				"servers": [{"url": f"http://{instance_id}:{addressing.IDE_HTTP_PORT}"}],
				"healthCheck": _service_health(IDE_HEALTH_PATH),
			}
		}

	_atomic_write(
		TRAEFIK_DYNAMIC_DIR / f"{instance_id}.yml",
		yaml.safe_dump({"http": {"routers": routers, "middlewares": middlewares, "services": services}}),
	)


def _router(rule: str, service: str, middlewares: list[str], priority: int) -> dict:
	"""One router and the chain it carries — see `publish` for why TLS names no resolver."""
	return {
		"rule": rule,
		"entryPoints": ["websecure"],
		"priority": priority,
		"service": service,
		"middlewares": middlewares,
		"tls": {},
	}


def _rate_limit(limits: RateLimits) -> dict:
	"""One `rateLimit` middleware, bucketed on the client address Cloudflare saw."""
	return {
		"rateLimit": {
			"average": limits.average,
			"burst": limits.burst,
			"sourceCriterion": {"ipStrategy": {"depth": CLIENT_IP_DEPTH}},
		}
	}


def _in_flight(amount: int) -> dict:
	"""One `inFlightReq`. No `sourceCriterion`: the router matches one host, so it is the bucket."""
	return {"inFlightReq": {"amount": amount}}


def _service_health(path: str) -> dict:
	"""Traefik's own probe of one service — the only thing that can eject a server from routing.

	Docker's verdict cannot: Traefik reads the file provider and has no socket to hear it on.
	"""
	settings = frappe.get_cached_doc("BenchPress Settings")
	# `.get`, not attribute access, and `or` on the value: a Single holds only what has been
	# written, so an untouched field reads None and a settings save materialises it as zero.
	interval = cint(settings.get("traefik_health_interval_seconds")) or DEFAULT_TRAEFIK_HEALTH_INTERVAL
	timeout = cint(settings.get("traefik_health_timeout_seconds")) or DEFAULT_TRAEFIK_HEALTH_TIMEOUT
	# No `hostname` key, deliberately: the probe goes to the server URL, so the Host header is
	# the container name, and any Host resolves to the bench's own site through `default_site`.
	return {"path": path, "interval": f"{interval}s", "timeout": f"{timeout}s"}


def has_ide(instance_id: str) -> bool:
	"""Whether this bench runs code-server — the one-bench case of `routable`."""
	rows = _fleet_rows(names=[instance_id])
	return _ide_for(rows[0]) if rows else False


def lab_has_ide(lab_doc) -> bool:
	"""Whether a bench of this Lab would run code-server, before one exists to ask about."""
	return _ide_for(lab_doc)


def rate_limits(instance_id: str) -> RateLimits:
	"""This bench's tier request numbers — the one-bench case of `routable`."""
	rows = _fleet_rows(names=[instance_id])
	return _limits_for(rows[0]) if rows else DEFAULT_RATE_LIMITS


def _ide_for(row) -> bool:
	"""The one rule: the Lab asks for an IDE and the size it resolves to includes one.

	`row` is a joined fleet row or a Lab document, so every caller answers from one rule.
	"""
	if not cint(row.get("enable_code_server")):
		return False
	size = _size_for(row)
	if not size:
		return True
	return bool(cint(size.include_code_server))


def _limits_for(row) -> RateLimits:
	"""The request numbers this bench's tier sets, each falling back on its own — see `RateLimits`."""
	size = _size_for(row) or {}
	return RateLimits(
		average=cint(size.get("rate_average")) or DEFAULT_RATE_AVERAGE,
		burst=cint(size.get("rate_burst")) or DEFAULT_RATE_BURST,
		# No floor under this one, unlike the two above: an unseeded 0 has to stay 0 so the bench
		# publishes no cap. The clamp is what an admin-editable field cannot be trusted without.
		inflight=min(cint(size.get("inflight_limit")), INFLIGHT_CEILING),
	)


def _size_for(row):
	"""The `Instance Size` a bench's routers answer from — the one it deployed at, else its Lab's.

	That is the order billing prices at, so re-pointing a Lab leaves a running bench alone.
	"""
	return size_index()["by_name"].get(row.get("bench_size")) or size_for_lab(row)


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


def directory_mounted() -> bool:
	"""Whether the route directory is mounted here — asked instead of the path being handed out."""
	return TRAEFIK_DYNAMIC_DIR.is_dir()


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


def routable() -> dict[str, tuple[bool, RateLimits]]:
	"""Every bench that should own a route file, mapped to its IDE flag and its tier's rate limits.

	`Running` with an IP only: a freed `container_ip` may already belong to another tenant.
	"""
	return {
		row.name: (_ide_for(row), _limits_for(row))
		for row in _fleet_rows(status="Running")
		if row.container_ip
	}


def _fleet_rows(names: list[str] | None = None, status: str | None = None) -> list[dict]:
	"""Bench rows beside the Lab fields the IDE flag resolves from, in one query per read.

	One join rather than a read per bench: the */5 pass resolves the whole fleet here, and at
	300 benches a per-bench read would be 300 queries a pass.
	"""
	instance = frappe.qb.DocType("Bench Instance")
	lab = frappe.qb.DocType("Lab")
	query = (
		frappe.qb.from_(instance)
		.left_join(lab)
		.on(instance.lab == lab.name)
		.select(
			instance.name,
			instance.container_ip,
			instance.instance_size.as_("bench_size"),
			lab.enable_code_server,
			lab.instance_size,
			lab.memory_limit,
			lab.cpu_cores,
		)
	)
	if names is not None:
		query = query.where(instance.name.isin(names))
	if status is not None:
		query = query.where(instance.status == status)
	return query.run(as_dict=True)
