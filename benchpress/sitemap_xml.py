# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The root `/sitemap.xml`: the pages this app serves, then the docs leadtype generated."""

import importlib
import re
from pathlib import Path

import frappe
from frappe.utils import get_url
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

from benchpress.docs_assets import CACHE_CONTROL, source_root
from benchpress.public_site import public_site_enabled

ROUTE = "sitemap.xml"
CONTENT_TYPE = "application/xml; charset=utf-8"

APP = "benchpress"
WWW = (APP, "www")

DOCUMENT = (
	'<?xml version="1.0" encoding="UTF-8"?>\n'
	'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'
)

ENTRY = re.compile(r"<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?")


def build() -> str:
	# `get_url("/" + route)`, not `get_url(route)`: the home page's canonical tag names the URL
	# with its trailing slash, and the sitemap has to agree with it.
	entries = [block(get_url(f"/{route}")) for route in app_routes()]
	entries.extend(docs_entries())
	return DOCUMENT.format(body="\n".join(entries))


def block(loc: str, lastmod: str = "") -> str:
	rows = [f"\t\t<loc>{loc}</loc>"]
	if lastmod:
		rows.append(f"\t\t<lastmod>{lastmod}</lastmod>")
	return "\t<url>\n" + "\n".join(rows) + "\n\t</url>"


def app_routes() -> list[str]:
	# Each page declares `sitemap` for itself. Read off the controllers rather than through
	# `router.get_pages()`, which compiles every www template of every installed app and needs
	# a live request to do it.
	#
	# No `lastmod`: the framework's generator stamps today on every page, and a date that is
	# always today is a freshness signal search engines discount.
	folder = Path(frappe.get_app_path(*WWW))
	routes = [
		template.relative_to(folder).with_suffix("").as_posix()
		for template in folder.rglob("*.html")
		if in_sitemap(template)
	]
	return sorted("" if route == "index" else route for route in routes)


def in_sitemap(template: Path) -> bool:
	# Frappe resolves a route's controller by swapping hyphens for underscores, and a page in a
	# subfolder is a module in a subpackage.
	controller = template.with_name(f"{template.stem.replace('-', '_')}.py")
	if not controller.is_file():
		return False
	root = Path(frappe.get_app_path(APP)).parent
	dotted = controller.relative_to(root).with_suffix("").as_posix().replace("/", ".")
	module = importlib.import_module(dotted)
	return bool(getattr(module, "sitemap", 0))


def docs_entries() -> list[str]:
	path = source_root() / ROUTE
	if not path.is_file():
		return []
	return [block(loc, lastmod) for loc, lastmod in ENTRY.findall(path.read_text(encoding="utf-8"))]


class SitemapRenderer(BaseRenderer):
	"""Claims `/sitemap.xml` only where the public site is on; elsewhere the docs sitemap serves."""

	def can_render(self) -> bool:
		return self.path == ROUTE and public_site_enabled()

	def render(self) -> Response:
		response = Response(build())
		response.headers["Content-Type"] = CONTENT_TYPE
		response.headers["Cache-Control"] = CACHE_CONTROL
		return response
