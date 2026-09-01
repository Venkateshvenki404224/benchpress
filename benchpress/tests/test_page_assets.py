# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The app's own stylesheets and scripts come from the bundler, content-hashed."""

import os
import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route

from benchpress.benchpress.site_content import clear_content_cache

BENCHPRESS_SETTINGS = "BenchPress Settings"

# Every route's own stylesheet and script, on top of the chrome pair every route shares.
PAGE_BUNDLES = {
	"/": ("bp-landing.bundle.css", "bp-landing.bundle.js"),
	"/landing": ("bp-landing.bundle.css", "bp-landing.bundle.js"),
	"/signup": ("bp-signup.bundle.css", "bp-signup.bundle.js"),
	"/login": ("bp-login.bundle.css", "bp-login.bundle.js"),
	"/about": ("bp-pages.bundle.css", None),
	"/contact": ("bp-pages.bundle.css", "bp-contact.bundle.js"),
}

ROUTES = tuple(PAGE_BUNDLES)

CHROME_BUNDLES = ("bp-brand.bundle.css", "bp-site.bundle.js")

# Anchored on the attribute, because `/login` also serialises the whole build manifest into
# `frappe.boot` and every app's bundle path appears there.
HASHED = re.compile(r'(?:href|src)="(/assets/benchpress/dist/(?:css|js)/([\w-]+)\.bundle\.\w+\.(css|js))"')

# What the bundler does not hash keeps a query-string token: the icons and the manifest.
FAVICON_TOKEN = re.compile(r'href="/assets/benchpress/images/logo/favicon\.svg\?v=([^"]+)"')
MANIFEST_TOKEN = re.compile(r'href="/assets/benchpress/manifest\.json\?v=([^"]+)"')

UNHASHED_STYLESHEET = re.compile(r'href="/assets/benchpress/css/[^"]+"')
UNHASHED_SCRIPT = re.compile(r'src="/assets/benchpress/js/[^"]+"')


class TestPageAssets(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		clear_content_cache()
		self.addCleanup(clear_content_cache)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(self.forget_writes)
		# The waitlist page redirects to Frappe's own signup while metering is live.
		self.set_credits(0)

	def forget_writes(self) -> None:
		frappe.db.rollback()
		frappe.clear_document_cache(BENCHPRESS_SETTINGS, BENCHPRESS_SETTINGS)
		clear_content_cache()

	def set_credits(self, value: int) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def render(self, route: str) -> str:
		frappe.set_user("Guest")
		return get_html_for_route(route)

	def hashed_urls(self, route: str) -> dict[str, str]:
		"""The bundle each route links, keyed by its unhashed name."""
		found = {}
		for link in HASHED.finditer(self.render(route)):
			url, name, extension = link.groups()
			found[f"{name}.bundle.{extension}"] = url
		return found

	def test_every_route_links_the_content_hashed_chrome_pair(self):
		for route in ROUTES:
			with self.subTest(route=route):
				found = self.hashed_urls(route)
				for bundle in CHROME_BUNDLES:
					self.assertIn(bundle, found)

	def test_every_route_links_its_own_content_hashed_bundles(self):
		for route, (stylesheet, script) in PAGE_BUNDLES.items():
			with self.subTest(route=route):
				found = self.hashed_urls(route)
				self.assertIn(stylesheet, found)
				if script:
					self.assertIn(script, found)

	def test_no_route_links_a_stylesheet_or_script_the_bundler_never_saw(self):
		for route in ROUTES:
			with self.subTest(route=route):
				html = self.render(route)
				self.assertIsNone(UNHASHED_STYLESHEET.search(html))
				self.assertIsNone(UNHASHED_SCRIPT.search(html))

	def test_every_bundle_a_route_links_exists_on_disk(self):
		for route in ROUTES:
			with self.subTest(route=route):
				for url in self.hashed_urls(route).values():
					path = os.path.join(frappe.local.sites_path, url.lstrip("/"))
					self.assertTrue(os.path.exists(path), f"{route} links a missing {url}")

	def test_one_token_covers_the_assets_the_bundler_does_not_hash(self):
		tokens = set()
		for route in ROUTES:
			with self.subTest(route=route):
				html = self.render(route)
				favicon = FAVICON_TOKEN.search(html)
				manifest = MANIFEST_TOKEN.search(html)
				self.assertIsNotNone(favicon, f"{route} renders no favicon token")
				self.assertIsNotNone(manifest, f"{route} renders no manifest token")
				self.assertEqual(favicon.group(1), manifest.group(1))
				tokens.add(favicon.group(1))
		self.assertEqual(len(tokens), 1, f"the routes disagree on the token: {sorted(tokens)}")
