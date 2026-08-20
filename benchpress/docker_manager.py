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

from benchpress.image_cache import cache_tag, clear_cached_tags

DEFAULT_PIDS_LIMIT = 500
DEFAULT_IOPS = 1000
DEFAULT_BPS = 40 * 1024 * 1024

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


def resolve_site_name(raw_site_name: str | None, *, exclude_bench: str | None = None) -> str | None:
	"""Normalize a caller-chosen site name and refuse anything unsafe or already taken.

	Returns `None` when `raw_site_name` is empty, so the caller falls back to its own
	default. A bare label is required — dots are rejected rather than treated as an
	already-qualified domain, so the resolved name is always exactly
	`<label>.<base_domain>`, never an arbitrary suffix a caller supplied. The resolved
	name becomes a MariaDB db/user name and an on-disk site folder, both unique
	server-wide, so the collision check is global — `exclude_bench` exists only so a
	redeploy can recheck its own name without colliding with itself.
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
	resolved = f"{candidate}.{base_domain}"
	_assert_site_name_available(resolved, exclude_bench)
	return resolved


def _assert_site_name_available(site_name: str, exclude_bench: str | None) -> None:
	filters = {"site_name": site_name, "status": ("!=", "Inactive")}
	if exclude_bench:
		filters["bench"] = ("!=", exclude_bench)
	if frappe.db.exists("Bench Site", filters):
		frappe.throw(_("Site name '{0}' is already in use. Choose a different name.").format(site_name))


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


def get_lab_template_dir() -> str:
	app_path = frappe.get_app_path("benchpress")
	return os.path.join(app_path, "lab-templates")


def ensure_network(client: docker.DockerClient | None = None) -> None:
	"""Create the benchpress Docker network if it does not exist."""
	client = client or get_client()
	try:
		client.networks.get("benchpress")
	except docker.errors.NotFound:
		client.networks.create(
			"benchpress",
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


def create_bench_container(bench_doc, lab_doc) -> str:
	"""Create a container from a lab image with resource limits.
	Does NOT start the container. Returns the container ID.
	"""
	client = get_client()
	ensure_network(client)

	name = bench_doc.bench_name

	labels = {
		"benchpress.managed": "true",
		"benchpress.bench_name": name,
		"benchpress.lab": lab_doc.lab_id,
	}

	pids_limit = int(getattr(lab_doc, "pids_limit", None) or DEFAULT_PIDS_LIMIT)
	iops = int(getattr(lab_doc, "iops_limit", None) or DEFAULT_IOPS)
	bps = int(getattr(lab_doc, "bps_limit", None) or DEFAULT_BPS)

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
	# NOT full privilege. For defense-in-depth (container-root != host-root), enable
	# Docker daemon userns-remap on the host (see docs/wireguard-setup.md).
	container = client.containers.create(
		image=lab_doc.image_tag,
		name=name,
		labels=labels,
		detach=True,
		hostname=name,
		cap_add=["NET_ADMIN"],
		devices=["/dev/net/tun:/dev/net/tun:rwm"],
		# No volume over /home/frappe: the bench lives in the image and the container's
		# own copy-on-write layer. A named volume here forced Docker to copy the whole
		# multi-GB bench on every create (~2-17 min per deploy) for zero persistence —
		# teardown always removed the volume with the container anyway.
		mem_limit=lab_doc.memory_limit or "512m",
		nano_cpus=int((lab_doc.cpu_cores or 1) * 1e9),
		pids_limit=pids_limit,
		device_read_iops=device_read_iops or None,
		device_write_iops=device_write_iops or None,
		device_read_bps=device_read_bps or None,
		device_write_bps=device_write_bps or None,
		network="benchpress",
	)

	return container.id


def get_container_ip(container_id: str) -> str:
	"""The container's bridge IP on the benchpress network."""
	client = get_client()
	container = client.containers.get(container_id)
	networks = container.attrs["NetworkSettings"]["Networks"]
	if "benchpress" in networks:
		return networks["benchpress"]["IPAddress"]
	return container.attrs["NetworkSettings"]["IPAddress"]


def start_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).start()


def wait_for_container_running(container_id: str, timeout: int = 60) -> str:
	"""Poll until the container reports status "running" and has an IP on the
	benchpress network. Returns the container IP. Mirrors wait_for_mariadb.
	"""
	client = get_client()
	container = client.containers.get(container_id)
	for _attempt in range(timeout // 2):
		container.reload()
		if container.status == "running":
			networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
			ip = networks.get("benchpress", {}).get("IPAddress", "") or container.attrs.get(
				"NetworkSettings", {}
			).get("IPAddress", "")
			if ip:
				return ip
		time.sleep(2)
	raise Exception(f"Container {container_id[:12]} not running with an IP after {timeout}s")


def stop_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).stop(timeout=30)


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
