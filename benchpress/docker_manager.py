# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os

import docker
import frappe


def get_client() -> docker.DockerClient:
	settings = frappe.get_cached_doc("BenchPress Settings")
	return docker.DockerClient(base_url=settings.docker_socket)


def get_lab_template_dir() -> str:
	app_path = frappe.get_app_path("benchpress")
	return os.path.join(app_path, "lab-templates")


def build_lab_image(lab_doc, site_name: str, admin_password: str, log_fn=None, no_cache: bool = False) -> str:
	"""Build Docker image with bench + apps + site baked in via layered Dockerfile.

	Layer caching means only changed layers rebuild:
	  Layer 1: System deps (apt) — rarely changes
	  Layer 2: Service configs — rarely changes
	  Layer 3: bench init — changes when FRAPPE_BRANCH changes
	  Layer 4: Apps — changes when app list changes
	  Layer 5: Site creation — changes when site name/apps change
	"""
	import json

	template_dir = get_lab_template_dir()
	image_tag = f"benchpress/{lab_doc.lab_id}:latest"
	version_branch = lab_doc.frappe_version

	apps = [{"app_name": a.app_name, "git_url": a.git_url, "branch": a.branch} for a in lab_doc.apps]

	build_args = {
		"FRAPPE_BRANCH": version_branch,
		"APPS_JSON": json.dumps(apps),
		"SITE_NAME": site_name,
		"ADMIN_PASSWORD": admin_password,
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

	return image_tag


def create_bench_container(bench_doc, lab_doc) -> str:
	"""Create a container from a lab image with resource limits.
	Does NOT start the container. Returns the container ID.
	"""
	client = get_client()

	# Ensure benchpress network exists
	try:
		client.networks.get("benchpress")
	except docker.errors.NotFound:
		client.networks.create(
			"benchpress",
			driver="bridge",
			ipam=docker.types.IPAMConfig(pool_configs=[docker.types.IPAMPool(subnet="172.30.0.0/24")]),
		)

	name = bench_doc.bench_name

	labels = {
		"benchpress.managed": "true",
		"benchpress.bench_name": name,
		"benchpress.lab": lab_doc.lab_id,
	}

	container = client.containers.create(
		image=lab_doc.image_tag,
		name=name,
		labels=labels,
		detach=True,
		hostname=name,
		privileged=True,
		cap_add=["NET_ADMIN"],
		volumes={
			f"benchpress-{name}-data": {"bind": "/home/frappe", "mode": "rw"},
		},
		mem_limit=lab_doc.memory_limit or "512m",
		nano_cpus=int((lab_doc.cpu_cores or 1) * 1e9),
		network="benchpress",
	)

	return container.id


def start_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).start()


def stop_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).stop(timeout=30)


def restart_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).restart(timeout=30)


def remove_container(container_id: str) -> None:
	client = get_client()
	client.containers.get(container_id).remove(force=True, v=True)


def exec_in_container(
	container_id: str, command: str, user: str = "frappe", workdir: str = "/home/frappe"
) -> tuple[int, str]:
	client = get_client()
	container = client.containers.get(container_id)
	exit_code, output = container.exec_run(
		cmd=["bash", "-c", command],
		user=user,
		workdir=workdir,
	)
	return exit_code, output.decode("utf-8", errors="replace")


def write_file_to_container(container_id: str, content: str, path: str) -> None:
	"""Write a file into a running container using docker exec."""
	import shlex

	client = get_client()
	container = client.containers.get(container_id)
	escaped = content.replace("'", "'\\''")
	container.exec_run(
		cmd=["bash", "-c", f"mkdir -p $(dirname {path}) && cat > {path} << 'WGEOF'\n{escaped}\nWGEOF"],
		user="root",
	)


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
