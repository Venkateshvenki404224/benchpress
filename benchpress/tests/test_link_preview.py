# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import contextlib
import re
from html import unescape

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route

from benchpress.benchpress.site_content import (
	ABOUT_SEED,
	OG_TYPE,
	SITE_NAME,
	clear_content_cache,
)

BENCHPRESS_SETTINGS = "BenchPress Settings"

# `/` and `/landing` are one page on two routes, and `/landing` needs no home-page setup.
ROUTES = ("/landing", "/about", "/contact", "/signup", "/login")

SINGLETON_TAGS = ("og:type", "og:title", "og:description", "og:image", "twitter:card", "description")

META = re.compile(r'<meta[^>]*?(?:name|property)="([^"]+)"[^>]*?content="([^"]*)"', re.IGNORECASE)


class TestLinkPreview(IntegrationTestCase):
	def setUp(self):
		clear_content_cache()
		self.addCleanup(clear_content_cache)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(self.clear_request)
		# Written inside the test transaction, so the cleanup drops the cache rather than the value.
		self.addCleanup(frappe.clear_cache, doctype=BENCHPRESS_SETTINGS)
		self.disable_credits()

	def clear_request(self) -> None:
		# `get_html_for_route` plants one; the rest of the suite runs without a request.
		with contextlib.suppress(AttributeError):
			del frappe.local.request

	def disable_credits(self) -> None:
		# With credits on and the waitlist closed, `/signup` redirects instead of rendering.
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", 0)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def tags(self, route: str) -> dict[str, list[str]]:
		frappe.set_user("Guest")
		found: dict[str, list[str]] = {}
		# `/contact` and `/login` read the request method, so the render needs a real one.
		for name, content in META.findall(get_html_for_route(route)):
			found.setdefault(name, []).append(content)
		return found

	def test_every_public_page_emits_one_preview_tag_of_each_kind(self):
		for route in ROUTES:
			with self.subTest(route=route):
				tags = self.tags(route)
				for name in SINGLETON_TAGS:
					self.assertEqual(len(tags.get(name, [])), 1, f"{name} on {route}: {tags.get(name)}")

	def test_the_page_type_and_site_name_are_the_same_on_every_page(self):
		for route in ROUTES:
			with self.subTest(route=route):
				tags = self.tags(route)
				self.assertEqual(tags["og:type"], [OG_TYPE])
				self.assertEqual(tags["og:site_name"], [SITE_NAME])

	def test_the_preview_image_is_an_absolute_url(self):
		for route in ROUTES:
			with self.subTest(route=route):
				self.assertRegex(self.tags(route)["og:image"][0], r"^https?://")

	def test_the_about_page_preview_describes_the_about_page(self):
		tags = self.tags("/about")
		self.assertEqual(tags["og:title"], [ABOUT_SEED["meta_title"]])
		self.assertEqual(unescape(tags["og:description"][0]), ABOUT_SEED["meta_description"])
