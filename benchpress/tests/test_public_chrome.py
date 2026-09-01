# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""One header and one footer, on every route a visitor can reach."""

import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route
from frappe.website.serve import get_response

from benchpress.benchpress.site_content import clear_content_cache

BENCHPRESS_SETTINGS = "BenchPress Settings"

ROUTES = ("/", "/landing", "/signup", "/login", "/about", "/contact")

HEADER = re.compile(r'<header class="bp-header".*?</header>', re.S)
FOOTER = re.compile(r'<footer class="bp-footer".*?</footer>', re.S)
FOOTER_HREF = re.compile(r'<a class="bp-footer__link" href="([^"]+)"')

CACHE_BUST = re.compile(r"\?v=[\w.]+")


class TestPublicChrome(IntegrationTestCase):
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

	def chrome(self, pattern: re.Pattern, route: str) -> str:
		found = pattern.search(self.render(route))
		self.assertIsNotNone(found, f"{route} renders no {pattern.pattern[:14]}")
		return CACHE_BUST.sub("", found.group(0))

	def test_every_route_renders_the_same_header(self):
		first = self.chrome(HEADER, ROUTES[0])
		for route in ROUTES[1:]:
			with self.subTest(route=route):
				self.assertEqual(self.chrome(HEADER, route), first)

	def test_every_route_renders_the_same_footer(self):
		first = self.chrome(FOOTER, ROUTES[0])
		for route in ROUTES[1:]:
			with self.subTest(route=route):
				self.assertEqual(self.chrome(FOOTER, route), first)

	def test_the_footer_carries_its_link_columns_everywhere(self):
		for route in ROUTES:
			with self.subTest(route=route):
				footer = self.chrome(FOOTER, route)
				self.assertIn("Company", footer)
				self.assertIn('href="/about"', footer)
				self.assertIn('href="/contact"', footer)

	def test_every_footer_link_resolves(self):
		for href in FOOTER_HREF.findall(self.chrome(FOOTER, "/")):
			if not href.startswith("/"):
				continue
			route, _, fragment = href.partition("#")
			with self.subTest(href=href):
				frappe.set_user("Guest")
				response = get_response(route or "/")
				self.assertEqual(response.status_code, 200)
				if fragment:
					self.assertIn(f'id="{fragment}"', frappe.safe_decode(response.get_data()))
