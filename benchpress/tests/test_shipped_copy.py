# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Every public page renders the copy the app ships, on the routes a visitor reaches it by."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route

from benchpress.benchpress.site_content import (
	ABOUT_SEED,
	LANDING_SEED,
	about_content,
	clear_content_cache,
	landing_content,
	shipped,
)
from benchpress.www.contact import CONTACT_SEED
from benchpress.www.login import LOGIN_SEED
from benchpress.www.self_host import SELF_HOST_SEED
from benchpress.www.services import SERVICES_SEED
from benchpress.www.signup import SIGNUP_SEED

BENCHPRESS_SETTINGS = "BenchPress Settings"

# One distinctive line per route, so a test fails when copy is lost, not when it is reworded.
SHIPPED_COPY = (
	("/", LANDING_SEED["hero_subhead"]),
	("/landing", LANDING_SEED["hero_subhead"]),
	("/about", ABOUT_SEED["situation_eyebrow"]),
	("/self-host", SELF_HOST_SEED["reqs_title"]),
	("/services", SERVICES_SEED["offers_title"]),
	("/contact", CONTACT_SEED["title"]),
	("/signup", SIGNUP_SEED["title"]),
	("/login", LOGIN_SEED["login_panel_title"]),
)


class TestShippedCopy(IntegrationTestCase):
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

	def test_every_route_renders_its_shipped_copy(self):
		for route, copy in SHIPPED_COPY:
			with self.subTest(route=route):
				self.assertIn(copy, self.render(route))

	def test_the_public_site_shows_the_commands_that_actually_run(self):
		# BenchPress installs into a bench you already run. A clone-and-run pair reads well and
		# has never worked, so no public surface may carry one.
		self_host = self.render("/self-host")
		self.assertIn("bench get-app", self_host)
		self.assertIn("apps/benchpress/setup.sh", self_host)
		for route in ("/self-host", "/"):
			with self.subTest(route=route):
				self.assertNotIn("git clone", self.render(route))

	def test_no_page_pays_a_query_for_its_copy(self):
		clear_content_cache()
		with self.assertQueryCount(0):
			landing_content()
			about_content()
			shipped(CONTACT_SEED)
			shipped(SIGNUP_SEED)
