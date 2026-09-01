# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import escape_html
from frappe.website.serve import get_response_content
from frappe.website.utils import get_home_page

from benchpress.benchpress.site_content import (
	ABOUT_SEED,
	CONSOLE_ROUTE,
	FORUM_REPLIES,
	FORUM_URL,
	LANDING_SEED,
	LOGOUT_METHOD,
	clear_content_cache,
)
from benchpress.credits.seed import seed_defaults
from benchpress.public_site.home import (
	LANDING_PAGE,
	SIGNED_IN_DEFAULT,
	WEBSITE_SETTINGS,
	home_page_for,
)
from benchpress.public_site.seed import claim_home_page, seed_public_site
from benchpress.www import index

BENCHPRESS_SETTINGS = "BenchPress Settings"


def _set_home_page(value, commit: bool = False) -> None:
	frappe.db.set_single_value(WEBSITE_SETTINGS, "home_page", value)
	frappe.cache.delete_value("home_page")
	if commit:
		frappe.db.commit()  # nosemgrep -- must outlive the per-test transaction


class TestLanding(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		seed_public_site()
		cls.switch_at_start = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		cls.home_page_at_start = frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page")
		_set_home_page(LANDING_PAGE, commit=True)

	@classmethod
	def tearDownClass(cls):
		_set_home_page(cls.home_page_at_start, commit=True)
		super().tearDownClass()

	def setUp(self):
		clear_content_cache()
		self.addCleanup(clear_content_cache)
		self.addCleanup(frappe.set_user, "Administrator")

	def disable_credits(self) -> None:
		self.addCleanup(self.set_credits_enabled, self.switch_at_start)
		self.set_credits_enabled(0)

	def set_credits_enabled(self, value) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def render_as_guest(self) -> str:
		frappe.set_user("Guest")
		return get_response_content("/")

	def test_slash_serves_the_landing_page_to_a_guest(self):
		self.disable_credits()
		html = self.render_as_guest()
		self.assertIn(LANDING_SEED["hero_badge_text"], html)
		self.assertIn('id="paths"', html)

	def test_repo_url_is_wired_everywhere(self):
		html = self.render_as_guest()
		self.assertIn(index.REPO_URL, html)
		self.assertNotIn("github.com/benchpress/benchpress", html)

	def test_trademark_disclaimer_sits_under_the_template_gallery(self):
		html = self.render_as_guest()
		marquee = html.index("bp-tmpl__track")
		disclaimer = html.index("trademarks of Frappe Technologies")
		paths = html.index('id="paths"')
		self.assertLess(marquee, disclaimer)
		self.assertLess(disclaimer, paths)

	def test_the_hosted_surfaces_wait_for_metering(self):
		self.disable_credits()
		context = index.get_context(frappe._dict())
		self.assertFalse(context.credits_enabled)
		self.assertFalse(context.waitlist_open)

	def test_the_header_and_footer_reach_the_about_and_contact_pages(self):
		# Both pages existed before anything linked to them, so neither was reachable from `/`.
		html = self.render_as_guest()
		self.assertIn('href="/about"', html)
		self.assertIn('href="/contact"', html)
		self.assertIn("Company", html)

	def test_a_guest_is_offered_a_way_in(self):
		html = self.render_as_guest()
		self.assertIn('href="/login"', html)
		self.assertNotIn("Log out", html)

	def test_a_signed_in_visitor_is_offered_a_way_out(self):
		self.disable_credits()
		frappe.set_user("Administrator")

		html = get_response_content("/landing")

		self.assertIn("Log out", html)
		self.assertIn(f'href="{CONSOLE_ROUTE}"', html)
		self.assertIn(f'action="/api/method/{LOGOUT_METHOD}"', html)

	def test_the_about_teaser_carries_the_numbers_from_the_about_page(self):
		# One home for the stats: the landing teaser reads the About page's own copy, not a copy of it.
		html = self.render_as_guest()
		self.assertIn('id="about"', html)
		self.assertIn(LANDING_SEED["about_title"], html)
		self.assertIn(escape_html(ABOUT_SEED["stats"][0]["value"]), html)

	def test_no_placeholder_quote_is_left_on_the_page(self):
		html = self.render_as_guest()
		self.assertNotIn("Placeholder", html)
		self.assertNotIn("<blockquote", html)

	def test_the_forum_thread_stands_in_for_the_quotes(self):
		html = self.render_as_guest()
		self.assertIn(FORUM_URL, html)
		self.assertIn(f"{FORUM_REPLIES} replies", html)
		self.assertIn(LANDING_SEED["forum_title"], html)

	def test_the_forum_link_sits_between_the_about_teaser_and_the_questions(self):
		html = self.render_as_guest()
		self.assertLess(html.index('id="about"'), html.index(FORUM_URL))
		self.assertLess(html.index(FORUM_URL), html.index(LANDING_SEED["faq_title"]))

	def test_the_landing_page_is_not_where_a_signed_in_user_lands(self):
		# `Website Settings.home_page` is also Frappe's post-login destination, for every user.
		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"), LANDING_PAGE)
		self.assertIsNone(home_page_for("Guest"))
		self.assertEqual(home_page_for("Administrator"), SIGNED_IN_DEFAULT)

		self.assertNotEqual(self.home_page_for_user("Administrator"), LANDING_PAGE)
		self.assertEqual(self.home_page_for_user("Guest"), LANDING_PAGE)

	def test_a_home_page_chosen_in_desk_reaches_a_signed_in_user_too(self):
		# `get_home_page_via_hooks` runs before the Single is read, so an unconditional override
		# would make `Website Settings.home_page` a guests-only setting.
		self.addCleanup(_set_home_page, LANDING_PAGE)
		_set_home_page("about")

		self.assertIsNone(home_page_for("Administrator"))
		self.assertEqual(self.home_page_for_user("Administrator"), "about")
		self.assertEqual(self.home_page_for_user("Guest"), "about")

	def test_the_landing_page_has_a_route_a_signed_in_operator_can_reach(self):
		# `/` and `/index` both resolve through `get_home_page`, which sends a System User to Desk.
		self.disable_credits()
		frappe.set_user("Administrator")

		html = get_response_content("/landing")

		self.assertIn(LANDING_SEED["hero_badge_text"], html)
		self.assertIn('id="paths"', html)

	def home_page_for_user(self, user: str) -> str:
		"""`get_home_page` past its per-user memo."""
		frappe.set_user(user)
		frappe.cache.delete_value("home_page")
		self.addCleanup(frappe.cache.delete_value, "home_page")
		return get_home_page()

	def test_the_seeder_leaves_a_chosen_home_page_alone(self):
		self.addCleanup(_set_home_page, LANDING_PAGE)
		_set_home_page("some-other-page")

		claim_home_page()

		self.assertEqual(frappe.db.get_single_value(WEBSITE_SETTINGS, "home_page"), "some-other-page")
