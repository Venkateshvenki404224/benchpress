# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import PurePosixPath

import docker
import frappe
from frappe import _
from frappe.utils import cint, flt

from benchpress import addressing
from benchpress.image_cache import cache_tag, clear_cached_tags
from benchpress.request_cache import local_cache

DEFAULT_MEMORY = "512m"
DEFAULT_PIDS_LIMIT = 500
DEFAULT_STOP_GRACE = 5
DEFAULT_IOPS = 1000
DEFAULT_BPS = 40 * 1024 * 1024

DISK_QUOTA_UNSUPPORTED = "this host enforces no writable-layer quota (overlay2 on xfs required)"

DEFAULT_HEALTH_INTERVAL = 30
DEFAULT_HEALTH_TIMEOUT = 5
DEFAULT_HEALTH_RETRIES = 3
DEFAULT_HEALTH_START_PERIOD = 600

# Docker's healthcheck durations are nanoseconds. Passing seconds gives an interval of a few
# nanoseconds that the daemon clamps, and an inspect then makes the wrong value look right.
NANOSECONDS = 1_000_000_000

# `localhost`, so the probe tests the server and not the bridge. Any Host header resolves:
# `common_site_config.json` names the bench's own site as `default_site`.
BENCH_HEALTH_PROBE = "curl -fsS -m {timeout} http://localhost:{port}/api/method/ping || exit 1"

# Docker's health verdict -> the `container_health` label. `starting` is neither: a bench mid-deploy
# is not healthy and is certainly not unhealthy.
HEALTH_LABELS = {"healthy": "Healthy", "unhealthy": "Unhealthy", "starting": "Unknown"}

# The stamp `create_bench_container` puts on every container and the filter `list_benches` reads
# back. The label is the whole authority for a reconciler's removal, so it has one definition.
MANAGED_LABEL = "benchpress.managed"
BENCH_NAME_LABEL = "benchpress.bench_name"
LAB_LABEL = "benchpress.lab"

# Field value -> the runtime name registered with the Docker daemon. None means
# "pass no runtime", which leaves the daemon's own default-runtime in charge.
CONTAINER_RUNTIMES = {"runc": None, "sysbox": "sysbox-runc"}

HOST_RUNTIMES_ATTRIBUTE = "benchpress_host_runtimes"
PREFLIGHT_IMAGE = "alpine"

# The network every bench predating the bridge family sits on. It keeps receiving
# MariaDB, Redis and Traefik as their primary network; it stops receiving benches.
LEGACY_NETWORK = "benchpress"


def resolve_runtime(bench_doc) -> str | None:
	"""The daemon runtime name for a bench, or None to use the daemon default."""
	return daemon_runtime(getattr(bench_doc, "runtime", None) or "runc")


def daemon_runtime(name: str) -> str | None:
	"""The runtime an allow-listed field value names, or None for the daemon default."""
	if name not in CONTAINER_RUNTIMES:
		frappe.throw(
			_("Unknown container runtime '{0}'. Allowed: {1}.").format(
				name, ", ".join(sorted(CONTAINER_RUNTIMES))
			)
		)
	return CONTAINER_RUNTIMES[name]


LAB_ID_MAX_LENGTH = 64
LAB_ID_RE = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*$")


def validate_lab_id(lab_id: str) -> None:
	"""Reject lab IDs that would produce an invalid Docker image tag."""
	if not lab_id or not LAB_ID_RE.match(lab_id) or len(lab_id) > LAB_ID_MAX_LENGTH:
		frappe.throw(
			_(
				"Lab ID '{0}' is not valid: use only lowercase letters, numbers and single '.', '_' or '-' separators (max {1} characters), e.g. 'crm-lab' or 'dev-v15'."
			).format(lab_id or "", LAB_ID_MAX_LENGTH)
		)


def _get_host_block_devices() -> list[str]:
	try:
		result = subprocess.run(
			["lsblk", "--json", "-d", "-o", "NAME,TYPE"],
			capture_output=True,
			text=True,
			timeout=5,
			check=False,
		)
		if result.returncode != 0:
			frappe.log_error(
				title="lsblk enumeration failed",
				message=f"exit={result.returncode} stderr={result.stderr}",
			)
			return []
		data = json.loads(result.stdout)
		return [f"/dev/{blk['name']}" for blk in data.get("blockdevices", []) if blk.get("type") == "disk"]
	except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
		frappe.log_error(title="lsblk enumeration failed", message=str(e))
		return []


def get_client() -> docker.DockerClient:
	settings = frappe.get_cached_doc("BenchPress Settings")
	return docker.DockerClient(base_url=settings.docker_socket, timeout=600)


def host_runtimes() -> dict:
	"""The daemon's registered runtime names and its default, memoised per job."""
	return local_cache(HOST_RUNTIMES_ATTRIBUTE, _read_host_runtimes)


def _read_host_runtimes() -> dict:
	info = get_client().info()
	return {"names": set(info.get("Runtimes") or {}), "default": info.get("DefaultRuntime") or ""}


def preflight_runtime(name: str) -> dict:
	"""Prove a runtime works by running a throwaway container: {"ok": bool, "detail": str}.

	The only check that answers "does it work" rather than "is it registered" — a
	broken runtime stays listed in `docker info` with its unit active. Reports
	instead of raising because a diagnostics screen is what reads it.
	"""
	runtime = daemon_runtime(name)
	runtime_kwargs = {"runtime": runtime} if runtime else {}
	try:
		get_client().containers.run(PREFLIGHT_IMAGE, "echo ok", remove=True, **runtime_kwargs)
	except Exception as e:
		return {"ok": False, "detail": str(e)}
	return {"ok": True, "detail": f"{runtime or host_runtimes()['default']} ran a container"}


def get_lab_template_dir() -> str:
	app_path = frappe.get_app_path("benchpress")
	return os.path.join(app_path, "lab-templates")


def ensure_network(client: docker.DockerClient | None = None) -> None:
	"""Create the benchpress Docker network if it does not exist."""
	client = client or get_client()
	try:
		client.networks.get(LEGACY_NETWORK)
	except docker.errors.NotFound:
		client.networks.create(
			LEGACY_NETWORK,
			driver="bridge",
			ipam=docker.types.IPAMConfig(pool_configs=[docker.types.IPAMPool(subnet="172.30.0.0/24")]),
		)


def build_lab_image(lab_doc, log_fn=None, no_cache: bool = False) -> str:
	"""Build Docker image with bench + apps (site created at runtime against shared MariaDB).

	The tag is the build spec's content hash, not the lab id, so every lab with the same recipe
	shares one image instead of holding a private copy — see `image_cache`.
	"""
	validate_lab_id(lab_doc.lab_id)
	template_dir = get_lab_template_dir()
	image_tag = cache_tag(lab_doc)
	version_branch = lab_doc.frappe_version

	apps = [{"app_name": a.app_name.lower(), "git_url": a.git_url, "branch": a.branch} for a in lab_doc.apps]

	settings = frappe.get_cached_doc("BenchPress Settings")
	build_args = {
		"FRAPPE_BRANCH": version_branch,
		"APPS_JSON": json.dumps(apps),
		"CODE_SERVER_VERSION": settings.code_server_version or "4.96.4",
	}

	if log_fn:
		log_fn(f"Building image {image_tag} (base: frappe/build:{version_branch}, apps: {len(apps)})...")

	client = get_client()
	api_client = client.api

	stream = api_client.build(
		path=template_dir,
		tag=image_tag,
		buildargs=build_args,
		rm=True,
		decode=True,
		nocache=no_cache,
		network_mode="host",
	)

	for chunk in stream:
		if "stream" in chunk:
			line = chunk["stream"].strip()
			if line and log_fn:
				log_fn(line)
		if "error" in chunk:
			error_msg = chunk["error"].strip()
			if log_fn:
				log_fn(f"ERROR: {error_msg}")
			raise Exception(f"Docker build failed: {error_msg}")

	# The tag exists now, so a resolve later in this same job must not read a stale set.
	clear_cached_tags()
	return image_tag


@dataclass(frozen=True)
class CreatedContainer:
	"""A created container, and which of its limits the daemon was really asked to enforce.

	`skipped` maps a knob to why it was dropped, so no deploy log can claim a quota this host
	silently ignores.
	"""

	container_id: str
	applied: dict
	skipped: dict


def _nano_cpus(cpu_cores) -> int:
	"""Clamp to what this host will accept: the seeded Large is undeployable on 2 cores."""
	return int(min(flt(cpu_cores) or 1.0, os.cpu_count() or 1) * 1_000_000_000)


@lru_cache(maxsize=1)
def _disk_quota_supported() -> bool:
	"""True only for overlay2 on xfs. Anywhere else `storage_opt` is accepted and ignored."""
	info = get_client().info()
	status = dict(info.get("DriverStatus") or [])
	backing = str(status.get("Backing Filesystem") or "").lower()
	return (info.get("Driver") or "").lower() == "overlay2" and backing == "xfs"


def _storage_opt(disk_limit: int) -> tuple[dict | None, str]:
	"""The `storage_opt` for a requested quota, or `None` and why it was skipped.

	Probed rather than assumed: off overlay2/xfs the flag is accepted and silently ignored, so
	passing it anyway would report a quota that does not exist.
	"""
	if not disk_limit:
		return None, ""
	if not _disk_quota_supported():
		return None, DISK_QUOTA_UNSUPPORTED
	return {"size": f"{disk_limit}g"}, ""


def _resolve_limits(size, lab_doc) -> dict:
	"""The density knobs for one create: the size's, or the lab's own where no size resolved.

	A site carrying no `Instance Size` row at all has nothing but the lab's hand-typed numbers.
	"""
	source = size if size else lab_doc
	return {
		"mem_limit": source.get("memory_limit") or DEFAULT_MEMORY,
		"nano_cpus": _nano_cpus(source.get("cpu_cores")),
		"pids_limit": cint(source.get("pids_limit")) or DEFAULT_PIDS_LIMIT,
		"iops": cint(source.get("iops_limit")) or DEFAULT_IOPS,
		"bps": cint(source.get("bps_limit")) or DEFAULT_BPS,
		"disk_limit": cint(source.get("disk_limit")),
	}


def bench_healthcheck() -> dict | None:
	"""The Docker healthcheck for a bench container, or None when the switch is off."""
	settings = frappe.get_cached_doc("BenchPress Settings")
	# A Single stores only the fields somebody has written, so an unset Check reads None here. The
	# switch exists to turn a healthcheck off, never to be off because nothing has written it.
	switch = settings.get("enable_bench_healthcheck")
	if switch is not None and not cint(switch):
		return None

	timeout = _health_setting(settings, "bench_health_timeout_seconds", DEFAULT_HEALTH_TIMEOUT)
	interval = _health_setting(settings, "bench_health_interval_seconds", DEFAULT_HEALTH_INTERVAL)
	start_period = _health_setting(settings, "bench_health_start_period_seconds", DEFAULT_HEALTH_START_PERIOD)
	return {
		"Test": ["CMD-SHELL", BENCH_HEALTH_PROBE.format(timeout=timeout, port=addressing.SITE_HTTP_PORT)],
		"Interval": interval * NANOSECONDS,
		"Timeout": timeout * NANOSECONDS,
		"StartPeriod": start_period * NANOSECONDS,
		"Retries": _health_setting(settings, "bench_health_retries", DEFAULT_HEALTH_RETRIES),
	}


def _health_setting(settings, field: str, default: int) -> int:
	"""A healthcheck setting, or its default when the field is unset or zero."""
	# `.get`, not attribute access: a Single field has no row in `tabSingles` until the settings
	# are saved once, and an AttributeError here would take the container create with it.
	return cint(settings.get(field)) or default


def create_bench_container(bench_doc, lab_doc, size=None, network: str | None = None) -> CreatedContainer:
	"""Create a container at a resolved `Instance Size`. Does NOT start it.

	`size` is read and never copied, so a size edited in Desk reaches the next deploy without the
	Lab being re-saved. `None` means no size resolved at all.

	`network` overrides the bench's recorded bridge, which is what a roll onto the next
	bridge needs: the row still names the bridge Docker refused.
	"""
	from benchpress import placement  # placement imports this module

	client = get_client()
	network = network or getattr(bench_doc, "bridge_network", None) or LEGACY_NETWORK
	placement.ensure_bench_network_for(network, client)

	name = bench_doc.bench_name

	labels = {
		MANAGED_LABEL: "true",
		BENCH_NAME_LABEL: name,
		LAB_LABEL: lab_doc.lab_id,
	}

	limits = _resolve_limits(size, lab_doc)
	storage_opt, disk_skipped = _storage_opt(limits["disk_limit"])
	iops = limits["iops"]
	bps = limits["bps"]

	runtime = resolve_runtime(bench_doc)
	runtime_kwargs = {"runtime": runtime} if runtime else {}

	healthcheck = bench_healthcheck()

	devices = _get_host_block_devices()
	device_read_iops = [{"Path": dev, "Rate": iops} for dev in devices]
	device_write_iops = [{"Path": dev, "Rate": iops} for dev in devices]
	device_read_bps = [{"Path": dev, "Rate": bps} for dev in devices]
	device_write_bps = [{"Path": dev, "Rate": bps} for dev in devices]

	# Security: lab containers must NOT be privileged. The student has in-container
	# root (sudo for bench/dev work), so privileged=True is a host-escape primitive:
	# in-container root + privileged -> Docker host root -> `docker exec
	# benchpress-mariadb mariadb -u root` reads EVERY tenant's database, defeating
	# the per-site DB isolation (Press-style scoped grants in mariadb_manager).
	# WireGuard (entry.sh `wg-quick up wg0`) needs only NET_ADMIN + /dev/net/tun,
	# NOT full privilege. Defense-in-depth (container-root != host-root) comes from
	# the sysbox runtime, which user-namespaces the container, not from daemon-wide
	# userns-remap.
	container = client.containers.create(
		image=lab_doc.image_tag,
		name=name,
		labels=labels,
		detach=True,
		hostname=name,
		cap_add=["NET_ADMIN"],
		devices=["/dev/net/tun:/dev/net/tun:rwm"],
		# No volume over /home/frappe — a named volume forces a full copy of the bench
		# on every create; the container's own layer is the bench's storage.
		mem_limit=limits["mem_limit"],
		nano_cpus=limits["nano_cpus"],
		pids_limit=limits["pids_limit"],
		device_read_iops=device_read_iops or None,
		device_write_iops=device_write_iops or None,
		device_read_bps=device_read_bps or None,
		device_write_bps=device_write_bps or None,
		network=network,
		**({"healthcheck": healthcheck} if healthcheck else {}),
		**({"storage_opt": storage_opt} if storage_opt else {}),
		**runtime_kwargs,
	)

	applied = {
		"memory": limits["mem_limit"],
		"nano_cpus": limits["nano_cpus"],
		"pids_limit": limits["pids_limit"],
		"iops": iops,
		"bps": bps,
	}
	skipped = {}
	if storage_opt:
		applied["disk"] = storage_opt["size"]
	elif disk_skipped:
		skipped["disk_limit"] = f"{limits['disk_limit']}g — {disk_skipped}"

	return CreatedContainer(container.id, applied, skipped)


def container_runtime(container_id: str) -> str:
	"""The runtime the daemon actually created this container under."""
	return get_client().containers.get(container_id).attrs["HostConfig"]["Runtime"]


def container_network(container_id: str) -> str:
	"""The bench network the daemon actually put this container on."""
	return get_client().containers.get(container_id).attrs["HostConfig"]["NetworkMode"]


def start_bench_container(container_id: str, bench_doc, lab_doc, size=None) -> str:
	"""Start the bench, moving it to the next bridge if this one has no address left.

	Returns the id of the container that is now running — a roll recreates it, so it is
	not always the one passed in.

	Docker allocates the address at start and not at create (measured on 29.7.2), so a
	full bridge refuses here rather than in `create_bench_container`. One retry, never a
	loop: a second refusal means the recorded count disagrees with the daemon, and a loop
	would hide that.
	"""
	from benchpress import placement  # placement imports this module

	try:
		start_container(container_id)
		return container_id
	except docker.errors.APIError as error:
		if not _address_pool_exhausted(error):
			raise

	# Recreated rather than reconnected: the endpoint on the full bridge is fixed at create,
	# and the new container has to take the name the old one is still holding.
	rolled_to = placement.next_network(container_network(container_id))
	remove_container(container_id)
	container_id = create_bench_container(bench_doc, lab_doc, size, rolled_to).container_id
	start_container(container_id)
	return container_id


def _address_pool_exhausted(error: docker.errors.APIError) -> bool:
	"""True when the daemon refused because the network has no free address.

	Matched as text: the daemon answers 500 for this, the same status as every other start
	failure. `tests/test_docker_manager.py` pins the wording this host really emits, so a
	daemon upgrade that reworded it fails a test rather than a deploy.
	"""
	return "no available ipv4 addresses" in str(error).lower()


def get_container_ip(container_id: str, network: str | None = None) -> str:
	"""The container's bridge IP on `network`, defaulting to the legacy bench network."""
	client = get_client()
	container = client.containers.get(container_id)
	networks = container.attrs["NetworkSettings"]["Networks"]
	network = network or LEGACY_NETWORK
	if network in networks:
		return networks[network]["IPAddress"]
	return container.attrs["NetworkSettings"]["IPAddress"]


def start_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).start()


def wait_for_container_running(container_id: str, network: str | None = None, timeout: int = 60) -> str:
	"""Poll until the container reports status "running" and has an IP on `network`.
	Returns the container IP. Mirrors wait_for_mariadb.
	"""
	client = get_client()
	container = client.containers.get(container_id)
	network = network or LEGACY_NETWORK
	for _attempt in range(timeout // 2):
		container.reload()
		if container.status == "running":
			networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
			ip = networks.get(network, {}).get("IPAddress", "") or container.attrs.get(
				"NetworkSettings", {}
			).get("IPAddress", "")
			if ip:
				return ip
		time.sleep(2)
	raise Exception(f"Container {container_id[:12]} not running with an IP after {timeout}s")


def stop_grace_seconds() -> int:
	"""How long a container gets to exit on SIGTERM before Docker kills it.

	Measured on this image: PID 1 is `tail`, which installs no handler, so the kernel discards
	the signal and every stop waits the grace period out in full and then SIGKILLs — exit 137,
	eighteen trials out of eighteen. The grace period is therefore the drain rate, and today it
	buys nothing. Configurable rather than constant so an image that does handle SIGTERM can
	have its shutdown back.
	"""
	return cint(frappe.get_cached_doc("BenchPress Settings").stop_grace_seconds) or DEFAULT_STOP_GRACE


def stop_container(container_id: str) -> None:
	"""Stop a container; one that no longer exists is already stopped, not an error."""
	client = get_client()
	try:
		client.containers.get(container_id).stop(timeout=stop_grace_seconds())
	except docker.errors.NotFound:
		pass


def restart_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).restart(timeout=30)


def remove_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).remove(force=True)


def exec_in_container(
	container_id: str,
	command: str,
	user: str = "frappe",
	workdir: str = "/home/frappe",
	environment: dict | None = None,
) -> tuple[int, str]:
	client = get_client()
	container = client.containers.get(container_id)
	exit_code, output = container.exec_run(
		cmd=["bash", "-c", command],
		user=user,
		workdir=workdir,
		environment=environment,
	)
	return exit_code, _decoded(output)


# The exec environment, not its command line: Docker publishes every exec command into its
# event stream in full and untruncated, and does not publish the environment at all.
FILE_CONTENT_VAR = "BENCHPRESS_FILE_CONTENT"


def write_file_to_container(container_id: str, content: str, path: str, *, mode: int | None = None) -> None:
	"""Write a file into a running container, raising when it did not land.

	The content travels in the exec environment. As a heredoc it was part of the command
	line, so every file this ever wrote was published to anything reading Docker events —
	a bench's WireGuard private key and its code-server password among them.

	`mode` is applied only when given, so a file that already exists keeps the mode it had.

	Not `put_archive`, which emits no event at all: sysbox re-mounts the container root over
	Docker's own snapshot, so an upload lands in the snapshot and stays invisible inside.
	"""
	container = get_client().containers.get(container_id)
	directory = PurePosixPath(path).parent
	command = f'mkdir -p {directory} && printf %s "${FILE_CONTENT_VAR}" > {path}'
	if mode is not None:
		command += f" && chmod {mode:o} {path}"
	exit_code, output = container.exec_run(
		cmd=["bash", "-c", command],
		user="root",
		environment={FILE_CONTENT_VAR: content},
	)
	if exit_code != 0:
		raise Exception(f"Writing {path} failed (exit {exit_code}): {_decoded(output)}")


def _decoded(output) -> str:
	"""Docker's exec output as text, whether it came back as bytes or not at all."""
	if isinstance(output, bytes):
		return output.decode("utf-8", errors="replace")
	return "" if output is None else str(output)


def container_is_down(container_id: str) -> bool:
	"""True only when Docker positively reports the container absent or not running.

	A daemon error is not "down": callers stop benches on this answer.
	"""
	try:
		return get_client().containers.get(container_id).status != "running"
	except docker.errors.NotFound:
		return True
	except Exception:
		return False


def get_container_health(container_id: str) -> str:
	"""Docker's health verdict for one container, or Unknown when it cannot be read.

	Unknown rather than a raise on a missing container, because callers stop benches on this.
	"""
	try:
		container = get_client().containers.get(container_id)
	except docker.errors.NotFound:
		return "Unknown"
	except Exception:
		frappe.log_error(
			title=f"Failed to get health for container {container_id}",
			message=frappe.get_traceback(),
		)
		return "Unknown"
	return _health_verdict(container)


def _health_verdict(container) -> str:
	"""The health of a container already inspected, so a fleet read costs no second call."""
	# Run state first: the daemon keeps the last verdict on a container that has exited, and a
	# verdict from while it ran is not a statement about a container that is no longer running.
	if container.status != "running":
		return "Unhealthy"
	health = (container.attrs.get("State") or {}).get("Health") or {}
	# No `Health` at all is a container created before the healthcheck existed, and it keeps
	# answering what it always did rather than turning Unknown overnight.
	return HEALTH_LABELS.get(health.get("Status"), "Healthy")


def _created_at(container) -> datetime | None:
	"""When the daemon created this container, in UTC. None when it did not say."""
	try:
		created = datetime.fromisoformat(container.attrs["Created"])
	except (KeyError, TypeError, ValueError):
		return None
	return created if created.tzinfo else created.replace(tzinfo=UTC)


def list_benches() -> list[dict]:
	"""Every container this app manages, in one call, with status, health and age.

	Stopped ones included: an orphan that exited still holds its writable layer.
	"""
	found = get_client().containers.list(all=True, filters={"label": f"{MANAGED_LABEL}=true"})
	return [
		{
			"id": container.id,
			"name": container.name,
			"bench_name": container.labels.get(BENCH_NAME_LABEL, ""),
			"status": container.status,
			"health": _health_verdict(container),
			"created": _created_at(container),
		}
		for container in found
	]


def get_container_stats(container_id: str) -> dict:
	"""Returns dict with cpu_percent, memory_percent, and memory_usage_mb."""
	client = get_client()
	try:
		container = client.containers.get(container_id)
		stats = container.stats(stream=False)

		cpu_delta = (
			stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
		)
		system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
		num_cpus = stats["cpu_stats"]["online_cpus"]
		cpu_percent = (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0

		mem_usage = stats["memory_stats"]["usage"]
		mem_limit = stats["memory_stats"]["limit"]
		mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

		return {
			"cpu_percent": round(cpu_percent, 1),
			"memory_percent": round(mem_percent, 1),
			"memory_usage_mb": round(mem_usage / (1024 * 1024), 1),
		}
	except Exception:
		frappe.log_error(
			title=f"Failed to get stats for container {container_id}",
			message=frappe.get_traceback(),
		)
		return {"cpu_percent": 0, "memory_percent": 0, "memory_usage_mb": 0}
