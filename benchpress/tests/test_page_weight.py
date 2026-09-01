# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The marketing pages ship none of the framework's website assets."""

import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route

from benchpress.benchpress.site_content import clear_content_cache

BENCHPRESS_SETTINGS = "BenchPress Settings"

MARKETING_ROUTES = ("/", "/landing", "/about", "/contact", "/signup")
# `/` resolves to the desk for a System User, so the signed-in view of the page is `/landing`.
SIGNED_IN_ROUTES = ("/landing", "/about", "/contact", "/signup")
LOGIN_ROUTE = "/login"

STYLESHEET = re.compile(r"website\.bundle\.[\w.]*css")
SCRIPT = re.compile(r"frappe-web\.bundle\.[\w.]*js")
BOOT_PAYLOAD = "frappe.boot ="
BODY_TOKEN = re.compile(r'<body[^>]*\bdata-csrf-token="([^"]*)"')


class TestPageWeight(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		clear_content_cache()
		self.addCleanup(clear_content_cache)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(self.forget_writes)
		# The waitlist page redirects to Frappe's own signup while metering is live.
		self.set_credits_enabled(0)

	def forget_writes(self) -> None:
		frappe.db.rollback()
		frappe.clear_document_cache(BENCHPRESS_SETTINGS, BENCHPRESS_SETTINGS)
		clear_content_cache()

	def set_credits_enabled(self, value: int) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def render(self, route: str, user: str = "Guest") -> str:
		frappe.set_user(user)
		return get_html_for_route(route)

	def test_no_marketing_page_links_the_framework_stylesheet(self):
		for route in MARKETING_ROUTES:
			with self.subTest(route=route):
				self.assertIsNone(STYLESHEET.search(self.render(route)))

	def test_no_marketing_page_loads_the_framework_script_bundle(self):
		for route in MARKETING_ROUTES:
			with self.subTest(route=route):
				self.assertIsNone(SCRIPT.search(self.render(route)))

	def test_no_marketing_page_serialises_the_boot_payload(self):
		for route in MARKETING_ROUTES:
			with self.subTest(route=route):
				self.assertNotIn(BOOT_PAYLOAD, self.render(route))

	def test_every_marketing_page_still_links_the_brand_stylesheet(self):
		for route in MARKETING_ROUTES:
			with self.subTest(route=route):
				self.assertIn("/assets/benchpress/css/brand.css", self.render(route))

	def test_the_login_page_keeps_the_framework_assets(self):
		html = self.render(LOGIN_ROUTE)
		self.assertIsNotNone(STYLESHEET.search(html))
		self.assertIsNotNone(SCRIPT.search(html))

	def test_every_marketing_page_carries_the_request_token_on_the_body(self):
		for route in SIGNED_IN_ROUTES:
			with self.subTest(route=route):
				html = self.render(route, user="Administrator")
				self.assertIsNotNone(BODY_TOKEN.search(html))

