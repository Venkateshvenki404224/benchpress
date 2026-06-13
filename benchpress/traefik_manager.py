# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import hashlib
import os
import secrets
import subprocess

from benchpress.docker_manager import ensure_network

ACME_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
ACME_PRODUCTION = "https://acme-v02.api.letsencrypt.org/directory"

_ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


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


def _to64(value: int, length: int) -> str:
	out = []
	for _ in range(length):
		out.append(_ITOA64[value & 0x3F])
		value >>= 6
	return "".join(out)


def _apr1_crypt(password: str, salt: str) -> str:
	"""Apache apr1 (salted MD5) hash, matching `openssl passwd -apr1`."""
	pw = password.encode()
	sp = salt.encode()
	ctx = hashlib.md5(pw + b"$apr1$" + sp)
	final = hashlib.md5(pw + sp + pw).digest()
	i = len(pw)
	while i > 0:
		ctx.update(final[: min(i, 16)])
		i -= 16
	i = len(pw)
	while i:
		ctx.update(b"\x00" if i & 1 else pw[:1])
		i >>= 1
	final = ctx.digest()
	for i in range(1000):
		c = hashlib.md5()
		c.update(pw if i & 1 else final)
		if i % 3:
			c.update(sp)
		if i % 7:
			c.update(pw)
		c.update(final if i & 1 else pw)
		final = c.digest()
	rearranged = ""
	for a, b, c in ((0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)):
		rearranged += _to64((final[a] << 16) | (final[b] << 8) | final[c], 4)
	rearranged += _to64(final[11], 2)
	return f"$apr1${salt}${rearranged}"


def make_basicauth_users(user: str, password: str) -> str:
	"""Return an htpasswd `user:hash` entry for a Traefik basicauth middleware.

	The apr1 hash is passed raw into the Docker SDK label dict — do NOT double the
	`$` (that escaping is only needed for docker-compose file interpolation).
	"""
	try:
		from passlib.hash import apr_md5_crypt

		hashed = apr_md5_crypt.hash(password)
	except ImportError:
		salt = "".join(secrets.choice(_ITOA64) for _ in range(8))
		hashed = _apr1_crypt(password, salt)
	return f"{user}:{hashed}"


def _decrypt_public_password(bench) -> str:
	getter = getattr(bench, "get_password", None)
	if callable(getter):
		return getter("public_password", raise_exception=False) or ""
	return bench.get("public_password") or ""


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

		if not bench.is_public:
			user = bench.public_username or "lab"
			users = make_basicauth_users(user, _decrypt_public_password(bench))
			labels[f"traefik.http.middlewares.{name}-auth.basicauth.users"] = users
			labels[f"traefik.http.routers.{name}.middlewares"] = f"{name}-auth"

	return labels
