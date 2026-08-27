# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Every address a bench answers on, built in one place.

The port numbers are properties of the bench image, not admin choices, so they are
constants here rather than settings. They lived in `deploy_manager` and again in
`frontend/src/utils/labActions.js`, kept in step by a comment; the SPA now renders
`addresses_for` instead of rebuilding a URL from a number it declared itself.
"""

SITE_HTTP_PORT = 8000
IDE_HTTP_PORT = 8080


def addresses_for(bench: dict) -> dict:
	"""Every address this bench answers on, for the SPA to render."""
	host = _tunnel_host(bench)
	return {
		"public_site": bench.get("public_url") or None,
		"public_ide": bench.get("code_server_url") or None,
		"tunnel_site": tunnel_site_url(bench),
		"tunnel_ide": tunnel_ide_url(bench),
		"host_label": f"{host}:{SITE_HTTP_PORT}" if host else "",
	}


def public_site_url(instance_id: str, base_domain: str | None) -> str | None:
	if not base_domain or base_domain == "localhost":
		return None
	return f"https://{instance_id}.{base_domain}"


def public_ide_url(instance_id: str, base_domain: str | None) -> str | None:
	if not base_domain or base_domain == "localhost":
		return None
	return f"https://ide-{instance_id}.{base_domain}"


def tunnel_site_url(bench: dict) -> str | None:
	host = _tunnel_host(bench)
	return f"http://{host}:{SITE_HTTP_PORT}" if host else None


def tunnel_ide_url(bench: dict) -> str | None:
	host = _tunnel_host(bench)
	return f"http://{host}:{IDE_HTTP_PORT}/" if host else None


def _tunnel_host(bench: dict) -> str | None:
	"""The WireGuard address, or the bridge address on a deployment with no tunnel."""
	return bench.get("wg_ip") or bench.get("container_ip") or None
