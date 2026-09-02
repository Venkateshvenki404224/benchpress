# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The public site is served to guests, so these tests guard cheapness and completeness."""

# Two failure modes matter here. The first is a section that ships with nothing in it, because the
# page renders whatever the constant holds and nothing fills a gap. The second is cost: `/` is the
# hottest page on the deployment, and it must reach the database zero times.

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.site_content import (
	ABOUT_SEED,
	CONSOLE_ROUTE,
	LANDING_SEED,
	LOGIN_ROUTE,
	SELF_HOST_ROUTE,
	SELFHOST_CTA_LABEL,
	WAITLIST_CTA_LABEL,
	WAITLIST_ROUTE,
	WITH_COLUMN,
	WITHOUT_COLUMN,
	about_content,
	chrome_content,
	clear_content_cache,
	landing_content,
)
from benchpress.credits.config import BENCHPRESS_SETTINGS, SIGNUP_ROUTE
from benchpress.credits.config import SETTINGS as CREDIT_SETTINGS

# Nothing on the page renders these, so they are allowed to be empty.
OPTIONAL_LANDING_KEYS = {"og_image"}
OPTIONAL_ABOUT_KEYS = {"og_image"}


class TestSiteContent(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	def setUp(self):
		super().setUp()
		clear_content_cache()
		self.addCleanup(clear_content_cache)

	# ------------------------------------------------------------------ completeness

	def test_every_landing_key_ships_with_a_value(self):
		settings = landing_content()["settings"]
		for fieldname in LANDING_SEED:
			if fieldname in OPTIONAL_LANDING_KEYS:
				continue
			self.assertTrue(settings.get(fieldname), f"{fieldname} ships with nothing in it")

	def test_every_about_key_ships_with_a_value(self):
		settings = about_content()["settings"]
		for fieldname in ABOUT_SEED:
			if fieldname in OPTIONAL_ABOUT_KEYS:
				continue
			self.assertTrue(settings.get(fieldname), f"{fieldname} ships with nothing in it")

	def test_every_landing_section_ships_with_rows(self):
		content = landing_content()
		self.assertEqual(len(content["phases"]), 4)
		self.assertEqual(sum(len(phase["steps"]) for phase in content["phases"]), 11)
		self.assertEqual(len(content["footer_columns"]), 3)
		self.assertEqual(len(content["hosted_points"]), 3)
		self.assertEqual(len(content["self_points"]), 3)

	# ------------------------------------------------------------------ shaping

	def test_steps_group_under_their_phase_in_step_order(self):
		phases = {phase["phase_key"]: phase for phase in landing_content()["phases"]}
		self.assertEqual([step.step_number for step in phases["site"]["steps"]], [5, 6, 7, 8])
		self.assertEqual(phases["request"]["nodes"], ["device", "control"])
		self.assertEqual(phases["site"]["chips"], [])

	def test_default_phase_falls_back_to_the_first_phase(self):
		with patch.dict(LANDING_SEED, {"pipeline_default_phase": "no-such-phase"}):
			self.assertEqual(landing_content()["default_phase"], "request")

	def test_footer_links_group_by_heading_in_first_seen_order(self):
		columns = landing_content()["footer_columns"]
		self.assertEqual([column["heading"] for column in columns], ["Product", "Developers", "Company"])
		self.assertEqual(columns[0]["links"][0], {"label": "Self-host it", "url": SELF_HOST_ROUTE})

	def test_about_days_split_by_column_preserving_order(self):
		content = about_content()
		self.assertEqual(len(content["days_without"]), 5)
		self.assertEqual(len(content["days_with"]), 5)
		self.assertEqual(content["days_without"][0].time_label, "09:00")
		self.assertEqual(content["days_with"][-1].time_label, "Later")
		self.assertTrue(all(row.column == WITHOUT_COLUMN for row in content["days_without"]))
		self.assertTrue(all(row.column == WITH_COLUMN for row in content["days_with"]))

	def test_service_cards_expose_the_reserved_meta_key(self):
		# `meta` cannot be a column: Frappe's Document swallows it. The template still reads it.
		card = landing_content()["settings"].service_cards[0]
		self.assertEqual(card.meta, "Hosted · monthly")
		self.assertEqual(card.meta_label, card.meta)

	def test_chrome_is_shared_by_every_page(self):
		chrome = chrome_content()
		self.assertEqual(next(item.label for item in chrome["nav_items"]), "Self-host")
		self.assertTrue(chrome["footer_trademark"])

	def test_the_chrome_names_the_about_and_contact_pages(self):
		# The header carries pages only and `/contact` is not one of the five, so the footer is
		# where it has to be reachable from.
		self.assertIn("/about", [item.anchor for item in chrome_content()["nav_items"]])

		columns = {column["heading"] for column in chrome_content()["footer_columns"]}
		self.assertIn("Company", columns)
		self.assertIn("/contact", [link["url"] for link in self.footer_links()])

	def test_the_chrome_carries_the_session_state_the_header_renders(self):
		chrome = chrome_content()
		self.assertTrue(chrome["is_signed_in"])  # tests run as Administrator
		self.assertEqual(chrome["login_route"], LOGIN_ROUTE)
		self.assertEqual(chrome["console_route"], CONSOLE_ROUTE)

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertFalse(chrome_content()["is_signed_in"])
		self.assertEqual(chrome_content()["csrf_token"], "")

	def test_the_header_button_is_always_self_host(self):
		"""1.1 inverted the hierarchy: the one button is the goal, whatever the hosted switches say."""
		for credits, waitlist in ((1, 1), (1, 0), (0, 1), (0, 0)):
			with self.subTest(credits=credits, waitlist=waitlist):
				self.set_switches(credits=credits, waitlist=waitlist)
				self.assertEqual(self.cta(), (SELFHOST_CTA_LABEL, SELF_HOST_ROUTE))

	def test_the_hosted_door_is_a_plain_link_that_follows_the_switches(self):
		self.set_switches(credits=1, waitlist=1)
		self.assertEqual(self.hosted_link(), (WAITLIST_CTA_LABEL, WAITLIST_ROUTE))
		self.assertEqual(chrome_content()["signup_route"], WAITLIST_ROUTE)

		self.set_switches(credits=1, waitlist=0)
		self.assertEqual(self.hosted_link(), ("Start free", SIGNUP_ROUTE))
		self.assertEqual(chrome_content()["signup_route"], SIGNUP_ROUTE)

		# No hosted product at all: the header may not offer an account that cannot exist.
		self.set_switches(credits=0, waitlist=1)
		self.assertIsNone(self.hosted_link())

	def cta(self) -> tuple[str, str]:
		"""The one primary button in the shared header, as `(label, url)`."""
		rows = [row for row in chrome_content()["nav_items"] if row.is_cta]
		self.assertEqual(len(rows), 1, "the header carries exactly one primary button")
		return rows[0].label, rows[0].anchor

	def hosted_link(self) -> tuple[str, str] | None:
		"""The secondary door, which is a plain row and never the button."""
		rows = [row for row in chrome_content()["nav_items"] if row.anchor in (WAITLIST_ROUTE, SIGNUP_ROUTE)]
		if not rows:
			return None
		self.assertEqual(len(rows), 1, "one hosted door, or none")
		self.assertFalse(rows[0].is_cta, "the hosted door is a link, never the button")
		return rows[0].label, rows[0].anchor

	def footer_links(self) -> list:
		return [link for column in chrome_content()["footer_columns"] for link in column["links"]]

	def set_switches(self, credits: int, waitlist: int) -> None:
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", credits)
		frappe.db.set_single_value(CREDIT_SETTINGS, "waitlist_open", waitlist)
		self.forget_switches()
		self.addCleanup(self.forget_switches)

	def forget_switches(self) -> None:
		frappe.clear_document_cache(BENCHPRESS_SETTINGS, BENCHPRESS_SETTINGS)
		frappe.clear_document_cache(CREDIT_SETTINGS, CREDIT_SETTINGS)

	# ------------------------------------------------------------------ cost

	def test_building_a_page_touches_no_database(self):
		clear_content_cache()
		with self.assertQueryCount(0):
			landing_content()
			about_content()

	def test_content_is_assembled_once_per_request(self):
		self.assertIs(landing_content(), landing_content())
		first = about_content()
		clear_content_cache()
		self.assertIsNot(about_content(), first)

	def test_reads_never_hand_out_the_shipped_rows_themselves(self):
		rows = landing_content()["settings"].hero_assurances
		self.assertTrue(all(isinstance(row, dict) for row in rows))
		self.assertIsNot(rows[0], LANDING_SEED["hero_assurances"][0])
