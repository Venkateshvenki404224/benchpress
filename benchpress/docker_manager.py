# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import json
import os
import re
import subprocess
import time

import docker
import frappe
from frappe import _
from frappe.utils import cint

from benchpress.image_cache import cache_tag, clear_cached_tags
from benchpress.request_cache import local_cache

DEFAULT_PIDS_LIMIT = 500
DEFAULT_STOP_GRACE = 5
DEFAULT_IOPS = 1000
DEFAULT_BPS = 40 * 1024 * 1024

# Field value -> the runtime name registered with the Docker daemon. None means
# "pass no runtime", which leaves the daemon's own default-runtime in charge.
CONTAINER_RUNTIMES = {"runc": None, "sysbox": "sysbox-runc"}

HOST_RUNTIMES_ATTRIBUTE = "benchpress_host_runtimes"
PREFLIGHT_IMAGE = "alpine"

# The network every bench predating the bridge family sits on. It keeps receiving
# MariaDB, Redis and Traefik as their primary network; it stops receiving benches.
LEGACY_NETWORK = "benchpress"
NETWORK_PREFIX = "benchpress-"
BRIDGE_DEVICE_PREFIX = "bpbr"
DEFAULT_SUBNET_BASE = "10.20"

# Attached to every bench bridge so Docker's embedded DNS answers in both
# directions. The control plane's own db and redis are deliberately absent: a
# tenant bridge that reaches them is a breach, not a convenience.
INFRASTRUCTURE_CONTAINERS = ("benchpress_traefik", "benchpress-mariadb", "benchpress-redis")


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


SITE_LABEL_MAX_LENGTH = 63
SITE_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def resolve_site_name(raw_site_name: str | None) -> str | None:
	"""Normalize a caller-chosen site name and refuse anything unsafe.

	Returns `None` when `raw_site_name` is empty, so the caller falls back to its own
	default. A bare label is required — dots are rejected rather than treated as an
	already-qualified domain, so the resolved name is always exactly
	`<label>.<base_domain>`, never an arbitrary suffix a caller supplied. Whether the name
	is free is not decided here: `api._claim_site_name` claims it against the `Bench Site`
	primary key, which is the only answer that cannot go stale between here and the deploy.
	"""
	if not raw_site_name or not raw_site_name.strip():
		return None
	candidate = raw_site_name.strip().lower()
	if "." in candidate:
		frappe.throw(
			_(
				"Site name '{0}' must be a single label without dots — the domain is added automatically."
			).format(raw_site_name)
		)
	if not SITE_LABEL_RE.match(candidate) or len(candidate) > SITE_LABEL_MAX_LENGTH:
		frappe.throw(
			_(
				"Site name '{0}' is not valid: use lowercase letters, numbers and single '-' "
				"separators, starting and ending with a letter or number (max {1} characters), "
				"e.g. 'acme' or 'acme-labs'."
			).format(raw_site_name, SITE_LABEL_MAX_LENGTH)
		)
	base_domain = frappe.db.get_single_value("BenchPress Settings", "base_domain") or "localhost"
	return f"{candidate}.{base_domain}"


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


def subnet_base() -> str:
	return frappe.get_cached_doc("BenchPress Settings").bench_subnet_base or DEFAULT_SUBNET_BASE


def bench_network_spec(index: int, base: str | None = None) -> dict:
	"""Name, bridge device, subnet and gateway for one bench bridge.

	`index * 16` in the third octet starts every /20 on its own boundary, so a later
	per-node /16 scheme renumbers nothing.
	"""
	base = base or DEFAULT_SUBNET_BASE
	octet = index * 16
	return {
		"name": f"{NETWORK_PREFIX}{index}",
		"device": f"{BRIDGE_DEVICE_PREFIX}{index}",
		"subnet": f"{base}.{octet}.0/20",
		"gateway": f"{base}.{octet}.1",
	}


def bench_network_index(network: str) -> int | None:
	"""The family index a network name encodes, or None if the name is not one of ours."""
	if not network.startswith(NETWORK_PREFIX):
		return None
	suffix = network[len(NETWORK_PREFIX) :]
	return int(suffix) if suffix.isdigit() else None


def ensure_bench_network(index: int, client: docker.DockerClient | None = None) -> str:
	"""Create bench bridge `index` if absent, attach infrastructure, return its name."""
	client = client or get_client()
	spec = bench_network_spec(index, subnet_base())
	try:
		client.networks.get(spec["name"])
	except docker.errors.NotFound:
		client.networks.create(
			spec["name"],
			driver="bridge",
			ipam=docker.types.IPAMConfig(
				pool_configs=[docker.types.IPAMPool(subnet=spec["subnet"], gateway=spec["gateway"])]
			),
			options={
				# Honoured only at create. A network that already exists without it
				# keeps its br-<hex> device forever, and phase 3's per-device
				# proxy_arp sysctl has no stable path to write.
				"com.docker.network.bridge.name": spec["device"],
				"com.docker.network.bridge.enable_icc": "true",
				"com.docker.network.bridge.enable_ip_masquerade": "true",
			},
		)
	attach_infrastructure(spec["name"], client)
	return spec["name"]


def ensure_bench_network_for(network: str, client: docker.DockerClient | None = None) -> str:
	"""Ensure the network a bench row names, whether legacy or one of the family."""
	client = client or get_client()
	if network == LEGACY_NETWORK:
		ensure_network(client)
		return network
	index = bench_network_index(network)
	if index is None:
		frappe.throw(_("'{0}' is not a BenchPress bench network.").format(network))
	return ensure_bench_network(index, client)


def attach_infrastructure(network: str, client: docker.DockerClient | None = None) -> list[str]:
	"""Connect the three infrastructure containers to `network`; returns those now on it.

	Only INFRASTRUCTURE_CONTAINERS is ever attachable. The tuple is a security
	boundary: an attachment reaches `Network.connect`, and putting the control
	plane's own database on a network tenants share is a breach.
	"""
	client = client or get_client()
	net = client.networks.get(network)
	present = {c.get("Name") for c in net.attrs.get("Containers", {}).values()}
	attached = []
	for name in INFRASTRUCTURE_CONTAINERS:
		if name in present:
			attached.append(name)
			continue
		try:
			net.connect(name)
			attached.append(name)
		except docker.errors.NotFound:
			continue  # a dev checkout has no Traefik
		except docker.errors.APIError as e:
			frappe.logger("benchpress").warning(f"could not attach {name} to {network}: {e}")
	return attached


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


def create_bench_container(bench_doc, lab_doc) -> str:
	"""Create a container from a lab image with resource limits.
	Does NOT start the container. Returns the container ID.
	"""
	client = get_client()
	network = getattr(bench_doc, "bridge_network", None) or LEGACY_NETWORK
	ensure_bench_network_for(network, client)

	name = bench_doc.bench_name

	labels = {
		"benchpress.managed": "true",
		"benchpress.bench_name": name,
		"benchpress.lab": lab_doc.lab_id,
	}

	pids_limit = int(getattr(lab_doc, "pids_limit", None) or DEFAULT_PIDS_LIMIT)
	iops = int(getattr(lab_doc, "iops_limit", None) or DEFAULT_IOPS)
	bps = int(getattr(lab_doc, "bps_limit", None) or DEFAULT_BPS)

	runtime = resolve_runtime(bench_doc)
	runtime_kwargs = {"runtime": runtime} if runtime else {}

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
		mem_limit=lab_doc.memory_limit or "512m",
		nano_cpus=int((lab_doc.cpu_cores or 1) * 1e9),
		pids_limit=pids_limit,
		device_read_iops=device_read_iops or None,
		device_write_iops=device_write_iops or None,
		device_read_bps=device_read_bps or None,
		device_write_bps=device_write_bps or None,
		network=network,
		**runtime_kwargs,
	)

	return container.id


def container_runtime(container_id: str) -> str:
	"""The runtime the daemon actually created this container under."""
	return get_client().containers.get(container_id).attrs["HostConfig"]["Runtime"]


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


def write_file_to_container(container_id: str, content: str, path: str) -> None:
	"""Write a file into a running container using docker exec, raising when it did not land.

	The exec result used to be discarded, which made a failed write invisible: every caller
	writes a file something later depends on — `common_site_config.json`, `wg0.conf`, the
	code-server config — so a silent failure surfaced as a site that cannot find redis, a
	tunnel serving the wrong key, or an IDE that never starts, long after the deploy said
	it was fine.
	"""
	client = get_client()
	container = client.containers.get(container_id)
	escaped = content.replace("'", "'\\''")
	exit_code, output = container.exec_run(
		cmd=["bash", "-c", f"mkdir -p $(dirname {path}) && cat > {path} << 'WGEOF'\n{escaped}\nWGEOF"],
		user="root",
	)
	if exit_code != 0:
		raise Exception(f"Writing {path} failed (exit {exit_code}): {_decoded(output)}")


def _decoded(output) -> str:
	"""Docker's exec output as text, whether it came back as bytes or not at all."""
	if isinstance(output, bytes):
		return output.decode("utf-8", errors="replace")
	return "" if output is None else str(output)


def container_is_gone(container_id: str) -> bool:
	"""True only when Docker positively reports the container does not exist.

	A daemon error is not "gone": callers stop benches on this answer.
	"""
	try:
		get_client().containers.get(container_id)
		return False
	except docker.errors.NotFound:
		return True
	except Exception:
		return False


def get_container_health(container_id: str) -> str:
	"""Return a coarse health label for a bench container.

	A "running" container is Healthy; any other known Docker state (exited,
	paused, dead, restarting) is Unhealthy; a missing container or inspect
	failure is Unknown. This deliberately mirrors the actual container state so
	a bench whose DB status drifts from reality is flagged.
	"""
	client = get_client()
	try:
		container = client.containers.get(container_id)
		return "Healthy" if container.status == "running" else "Unhealthy"
	except docker.errors.NotFound:
		return "Unknown"
	except Exception:
		frappe.log_error(
			title=f"Failed to get health for container {container_id}",
			message=frappe.get_traceback(),
		)
		return "Unknown"


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
