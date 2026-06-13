# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import subprocess

from benchpress.docker_manager import ensure_network


def _get_config_dir() -> str:
	import frappe

	return os.path.join(frappe.get_app_path("benchpress"), "config")


def _compose_cmd(*args: str) -> tuple[int, str]:
	"""Run docker compose command in the config directory."""
	compose_path = os.path.join(_get_config_dir(), "docker-compose.yml")
	cmd = ["docker", "compose", "-f", compose_path, *args]
	result = subprocess.run(cmd, capture_output=True, text=True, cwd=_get_config_dir())
	output = result.stdout + result.stderr
	return result.returncode, output


def ensure_traefik() -> None:
	"""Bring up the shared Traefik reverse proxy. Idempotent."""
	ensure_network()
	exit_code, output = _compose_cmd("up", "-d", "traefik")
	if exit_code != 0:
		raise Exception(f"docker compose up traefik failed: {output}")


def compute_bench_labels(bench, lab, settings) -> dict[str, str]:
	"""Single source of truth for a bench container's Docker labels.

	Traefik routing labels are added only when a base_domain is configured.
	"""
	labels = {
		"benchpress.managed": "true",
		"benchpress.bench_name": bench.bench_name,
		"benchpress.lab": lab.lab_id,
	}

	if settings.base_domain:
		name = bench.bench_name
		host = f"{name}.{settings.base_domain}"
		labels.update(
			{
				"traefik.enable": "true",
				"traefik.docker.network": "benchpress",
				f"traefik.http.routers.{name}.rule": f"Host(`{host}`)",
				f"traefik.http.routers.{name}.entrypoints": "web",
				f"traefik.http.services.{name}-svc.loadbalancer.server.port": "8000",
				f"traefik.http.routers.{name}.service": f"{name}-svc",
			}
		)

	return labels
