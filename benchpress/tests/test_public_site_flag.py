# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Without the site-config key an install serves no marketing page and opens no guest endpoint."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.fixtures import sync_fixtures
from frappe.website.serve import get_response

from benchpress import contact, emails, signup, waitlist
from benchpress.benchpress.site_content import LANDING_SEED, clear_content_cache
from benchpress.public_site import CONFIG_KEY
from benchpress.public_site.home import LANDING_PAGE, SIGNED_IN_DEFAULT, WEBSITE_SETTINGS, home_page_for
from benchpress.public_site.seed import seed_public_site
from benchpress.tests.guest_request import as_request

EMAIL_TEMPLATE = "Email Template"
PUBLIC_ROUTES = ("/landing", "/about", "/contact", "/signup")
EMAIL = "gate@example.com"


@contextmanager
def public_site(enabled: bool):
	with patch.dict(frappe.conf, {CONFIG_KEY: 1 if enabled else 0}):
		yield


def _set_home_page(value) -> None:
	frappe.db.set_single_value(WEBSITE_SETTINGS, "home_page", value)
	frappe.cache.delete_value("home_page")


class TestPublicSiteFlag(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Frappe caches the rendered 404 page, and a cache hit skips the module that stamps the
		# status, so a second not-found would answer 200.
		frappe.local.no_cache = True
		self.addCleanup(setattr, frappe.local, "no_cache", False)
		frappe.cache.delete_keys("rl:")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		clear_content_cache()
		self.addCleanup(clear_content_cache)
		self.addCleanup(frappe.set_user, "Administrator")

	def render_as_guest(self, route: str):
		frappe.set_user("Guest")
		return get_response(route)

	def test_the_public_routes_are_not_found_without_the_key(self):
		with public_site(False):
			for route in PUBLIC_ROUTES:
				with self.subTest(route=route):
					self.assertEqual(self.render_as_guest(route).status_code, 404)

	def test_the_landing_page_is_not_found_without_the_key(self):
		self.addCleanup(_set_home_page, frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"))
		_set_home_page(LANDING_PAGE)

		with public_site(False):
			self.assertEqual(self.render_as_guest("/").status_code, 404)

	def test_the_public_routes_serve_the_shipped_copy_with_the_key(self):
		with public_site(True):
			response = self.render_as_guest("/landing")

		self.assertEqual(response.status_code, 200)
		self.assertIn(LANDING_SEED["hero_badge_text"], str(response.data, "utf-8"))

	def test_the_seeder_leaves_the_home_page_alone_without_the_key(self):
		self.addCleanup(_set_home_page, frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"))
		_set_home_page("")

		with public_site(False):
			seed_public_site()

		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"), "")

	def test_the_seeder_creates_no_mail_templates_without_the_key(self):
		name = self.drop_a_mail_template()

		with public_site(False):
			seed_public_site()

		self.assertFalse(frappe.db.exists(EMAIL_TEMPLATE, name))

	def test_migrating_creates_no_mail_templates_without_the_key(self):
		name = self.drop_a_mail_template()

		with public_site(False):
			sync_fixtures("benchpress")

		self.assertFalse(frappe.db.exists(EMAIL_TEMPLATE, name))

	def drop_a_mail_template(self) -> str:
		name = emails.seed_rows()[0]["name"]
		if frappe.db.exists(EMAIL_TEMPLATE, name):
			frappe.delete_doc(EMAIL_TEMPLATE, name, force=True, ignore_permissions=True)
		return name

	def test_the_home_page_hook_is_silent_without_the_key(self):
		self.addCleanup(_set_home_page, frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"))
		_set_home_page(LANDING_PAGE)

		with public_site(True):
			self.assertEqual(home_page_for("Administrator"), SIGNED_IN_DEFAULT)
		with public_site(False):
			self.assertIsNone(home_page_for("Administrator"))

	def test_the_guest_endpoints_refuse_without_the_key(self):
		calls = (
			("waitlist", lambda: waitlist.join(EMAIL)),
			("contact", lambda: contact.submit("Ravi", EMAIL, "hello")),
			("signup", lambda: signup.sign_up(EMAIL, "Ravi")),
		)
		with public_site(False), as_request():
			for label, call in calls:
				with self.subTest(endpoint=label):
					self.assertRaises(frappe.PageDoesNotExistError, call)

		self.assertFalse(frappe.db.exists("Waitlist Entry", {"email": EMAIL}))
		self.assertFalse(frappe.db.exists("Contact Message", {"email": EMAIL}))
		self.assertFalse(frappe.db.exists("User", EMAIL))
