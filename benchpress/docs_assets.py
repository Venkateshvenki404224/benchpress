# Copyright (c) 2026, BenchPress and contributors
# For license information, please see license.txt

"""Serve the pre-built docs-site discovery files verbatim.

Frappe compiles every www/ file as Jinja and converts .md to HTML, which breaks
both the docker examples in llms-full.txt and the sha256 digests in index.json.
"""

import mimetypes
from pathlib import Path

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

# frappe/app.py claims every GET under /.well-known/ for OAuth metadata before
# the website router runs, so Traefik maps that reserved prefix onto this one.
WELL_KNOWN_ROUTE = "well-known/"
WELL_KNOWN_DIR = ".well-known"

# Site-level indexes. These shadow the wiki app's generated /llms.txt and
# /sitemap.xml, which describe the Frappe wiki rather than BenchPress.
TOP_LEVEL_FILES = ("llms.txt", "llms-full.txt", "robots.txt", "sitemap.xml")

# Discovery documents change when the docs are rebuilt, not per request.
CACHE_CONTROL = "public, max-age=3600"

# mimetypes knows neither an extensionless RFC 9727 linkset nor .md, and is
# inconsistent about .xml across platforms.
CONTENT_TYPES = {
	"api-catalog": "application/linkset+json",
	".md": "text/markdown; charset=utf-8",
	".xml": "application/xml; charset=utf-8",
}


def source_root() -> Path:
	"""The committed docs-site tree, which stays the single source of truth."""
	return (Path(frappe.get_app_path("benchpress")).parent / "docs-site").resolve()


def resolve_path(route: str) -> Path | None:
	"""Map a website route onto a docs-site file, or None if it is not one."""
	if route in TOP_LEVEL_FILES:
		return source_root() / route

	if route.startswith(WELL_KNOWN_ROUTE):
		return source_root() / WELL_KNOWN_DIR / route[len(WELL_KNOWN_ROUTE) :]

	return None


def content_type_for(target: Path) -> str:
	if target.name in CONTENT_TYPES:
		return CONTENT_TYPES[target.name]
	if target.suffix in CONTENT_TYPES:
		return CONTENT_TYPES[target.suffix]

	guessed = mimetypes.guess_type(target.name)[0]
	return f"{guessed}; charset=utf-8" if guessed else "application/octet-stream"


class DocsAssetRenderer(BaseRenderer):
	"""Byte-for-byte static file server rooted at the app's docs-site directory."""

	def can_render(self) -> bool:
		candidate = resolve_path(self.path)
		if candidate is None:
			return False

		root = source_root()
		target = candidate.resolve()
		# is_relative_to after resolve(): a traversal in the URL must not reach
		# outside the docs tree.
		if not target.is_relative_to(root) or not target.is_file():
			return False

		self.target = target
		return True

	def render(self) -> Response:
		response = Response(self.target.read_bytes())
		response.headers["Content-Type"] = content_type_for(self.target)
		response.headers["Cache-Control"] = CACHE_CONTROL
		return response
