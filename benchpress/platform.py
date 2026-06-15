# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Platform-level helpers for resolving how a user reaches a deployed bench.

Centralizing the host-resolution rule here means later tracer bullets (TB3 adds a
WSL2 localhost-forwarding branch) change one function instead of every call site.
"""


def resolve_access_url(bench) -> str:
	"""Return the host a user reaches ``bench`` at.

	Prefers the WireGuard peer IP, falls back to the container's bridge IP, then to
	loopback. Callers format their own scheme/port around this (``http://<host>:8000/``,
	``ssh user@<host>``, ...). This is intentionally just the host today; TB3 will add
	the WSL2 branch that returns a localhost-forwarded address.
	"""
	return bench.wg_ip or bench.container_ip or "127.0.0.1"
