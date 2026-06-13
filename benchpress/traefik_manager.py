# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import subprocess

from benchpress.docker_manager import ensure_network

ACME_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
ACME_PRODUCTION = "https://acme-v02.api.letsencrypt.org/directory"


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


def _render_traefik_config(settings) -> str:
	"""Render the Traefik static config. Traefik does not expand environment
	variables in its static config file, so the ACME email and CA server are
	written in directly. le_use_staging selects the staging CA (the default) to
	avoid burning the Let's Encrypt production rate limit during testing."""
	ca_server = ACME_STAGING if settings.le_use_staging else ACME_PRODUCTION
	email = settings.acme_email or ""
	return f"""entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    network: benchpress
    exposedByDefault: false

certificatesResolvers:
  letsencrypt:
    acme:
      email: "{email}"
      storage: /etc/traefik/acme/acme.json
      caServer: "{ca_server}"
      tlsChallenge: {{}}

api:
  dashboard: true
  insecure: true
"""


def _write_traefik_config(settings) -> bool:
	"""Write config/traefik.yml from Settings. Returns True if the file changed."""
	config = _render_traefik_config(settings)
	config_path = os.path.join(_get_config_dir(), "traefik.yml")
	existing = ""
	if os.path.exists(config_path):
		with open(config_path) as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
			existing = f.read()
	if existing == config:
		return False
	with open(config_path, "w") as f:  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal  # fmt: skip
		f.write(config)
	return True


def ensure_traefik() -> None:
	"""Bring up the shared Traefik reverse proxy. Idempotent."""
	import frappe

	ensure_network()
	settings = frappe.get_cached_doc("BenchPress Settings")
	recreate = _write_traefik_config(settings)
	args = ["up", "-d"]
	if recreate:
		args.append("--force-recreate")
	args.append("traefik")
	exit_code, output = _compose_cmd(*args)
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
				f"traefik.http.routers.{name}.entrypoints": "websecure",
				f"traefik.http.routers.{name}.tls": "true",
				f"traefik.http.routers.{name}.tls.certresolver": "letsencrypt",
				f"traefik.http.services.{name}-svc.loadbalancer.server.port": "8000",
				f"traefik.http.routers.{name}.service": f"{name}-svc",
			}
		)

	return labels
