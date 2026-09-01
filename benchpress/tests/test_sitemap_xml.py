# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""`/sitemap.xml` names the marketing routes as well as the generated docs pages."""

from unittest.mock import patch
from xml.etree import ElementTree

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import sitemap_xml
from benchpress.public_site import CONFIG_KEY

NAMESPACE = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

GENERATED = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://benchpress.cloud/docs/user/quick-tour</loc>
    <lastmod>2026-08-30T14:43:11.000Z</lastmod>
  </url>
</urlset>
"""


def locations(body: str) -> list[str]:
	root = ElementTree.fromstring(body)
	return [node.text for node in root.findall("s:url/s:loc", NAMESPACE)]


class TestSitemapXml(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_it_is_well_formed_xml(self):
		self.assertTrue(locations(sitemap_xml.build()))

	def test_the_marketing_routes_are_named(self):
		found = locations(sitemap_xml.build())
		for route in ("/", "/about", "/self-host", "/services", "/contact"):
			with self.subTest(route=route):
				self.assertIn(frappe.utils.get_url(route), found)

	def test_a_page_in_a_subfolder_is_found(self):
		# `/vs/<slug>` pages live in `www/vs/`, so the walk cannot stop at the top level.
		self.assertIn(frappe.utils.get_url("/vs/frappe-docker"), locations(sitemap_xml.build()))

	def test_the_landing_alias_is_left_out(self):
		# `/landing` renders the same page as `/`, and only `/` is canonical.
		self.assertNotIn(frappe.utils.get_url("/landing"), locations(sitemap_xml.build()))

	def test_the_console_is_left_out(self):
		self.assertNotIn(frappe.utils.get_url("/frontend"), locations(sitemap_xml.build()))

	def test_the_generated_docs_pages_keep_their_place_and_their_date(self):
		body = sitemap_xml.build()
		self.assertIn("/docs/user/quick-tour", body)
		self.assertIn("<lastmod>", body)

	def test_a_generated_entry_is_read_with_its_date(self):
		self.assertEqual(
			sitemap_xml.ENTRY.findall(GENERATED),
			[("https://benchpress.cloud/docs/user/quick-tour", "2026-08-30T14:43:11.000Z")],
		)

	def test_an_entry_without_a_date_emits_no_empty_element(self):
		self.assertNotIn("<lastmod>", sitemap_xml.block("https://example.com/"))

	def test_a_missing_generated_sitemap_still_names_the_marketing_routes(self):
		with patch.object(sitemap_xml, "docs_entries", return_value=[]):
			self.assertIn(frappe.utils.get_url("/about"), locations(sitemap_xml.build()))

	def test_the_route_is_claimed_only_where_the_public_site_is_on(self):
		for enabled, expected in ((1, True), (0, False)):
			with self.subTest(enabled=enabled), patch.dict(frappe.conf, {CONFIG_KEY: enabled}):
				renderer = sitemap_xml.SitemapRenderer(sitemap_xml.ROUTE)
				self.assertEqual(renderer.can_render(), expected)
