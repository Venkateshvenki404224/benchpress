# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The landing page's contract is that it is *not* a static file.

Two things must hold, and both are easy to break by "just hardcoding it for now": the page has to
render for an anonymous visitor (it is the public launch surface, and the SPA's router sends every
guest to /login), and every commercial number on it has to come from `Credit Pack` / `Instance
Size`, so an operator can retune a price in Desk and see it live without a deploy.

The query test asserts flatness rather than an absolute count — the point is that adding packs or
sizes must not add queries, which is what an accidental per-row `get_doc` would do.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.serve import get_response_content

from benchpress.credits import config
from benchpress.credits.seed import seed_defaults
from benchpress.www import home

PACK = "Landing Test Pack"


def _delete_pack():
	if frappe.db.exists("Credit Pack", PACK):
		frappe.delete_doc("Credit Pack", PACK, force=True, ignore_permissions=True)


class TestLanding(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		seed_defaults()
		frappe.db.commit()  # nosemgrep -- class fixtures must outlive the per-test transaction

	def setUp(self):
		config.clear_size_index()
		self.addCleanup(frappe.set_user, "Administrator")

	def render_as_guest(self) -> str:
		frappe.set_user("Guest")
		return get_response_content("/home")

	def test_page_renders_for_guest(self):
		html = self.render_as_guest()
		self.assertIn("Pick a template.", html)
		self.assertIn("Join the waitlist.", html)

	def test_pricing_is_read_from_the_documents(self):
		"""The Pricing section is commented out in home.html until the pack/rate numbers are
		final (see the block's disabled-for-now note), so nothing here reaches the page yet --
		assert the context assembles it correctly instead. Restore the `html`-based assertions
		below once the section is back."""
		context = home.get_context(frappe._dict())
		self.assertEqual(
			{pack.pack_label for pack in config.active_packs()},
			{pack["pack_label"] for pack in context.packs},
		)
		self.assertEqual(
			{size.size_label for size in config.instance_sizes()},
			{row["label"] for row in context.sizes},
		)

		html = self.render_as_guest()
		for pack in config.active_packs():
			self.assertNotIn(pack.pack_label, html)

	def test_a_price_edited_in_desk_changes_the_page(self):
		"""Same disabled-section caveat as above: a new price now only has to reach the
		context, not the page. Restore the `html`-based assertions once Pricing is back."""
		frappe.set_user("Administrator")
		self.addCleanup(_delete_pack)
		frappe.get_doc(
			{
				"doctype": "Credit Pack",
				"pack_label": PACK,
				"inr_price": 12345,
				"credits": 500,
				"is_active": 1,
				"sort_order": 99,
			}
		).insert(ignore_permissions=True)

		context = home.get_context(frappe._dict())
		self.assertIn(PACK, {pack["pack_label"] for pack in context.packs})

		html = self.render_as_guest()
		self.assertNotIn("₹12,345", html)
		self.assertNotIn(PACK, html)

	def test_an_inactive_pack_is_not_offered(self):
		frappe.set_user("Administrator")
		self.addCleanup(_delete_pack)
		frappe.get_doc(
			{
				"doctype": "Credit Pack",
				"pack_label": PACK,
				"inr_price": 12345,
				"credits": 500,
				"is_active": 0,
				"sort_order": 99,
			}
		).insert(ignore_permissions=True)

		self.assertNotIn(PACK, self.render_as_guest())

	def test_repo_url_is_wired_everywhere(self):
		html = self.render_as_guest()
		# Header, hero, clone command, footer (twice) and the film endcard.
		self.assertGreaterEqual(html.count(home.REPO_URL), 5)
		self.assertNotIn("github.com/benchpress/benchpress", html)

	def test_trademark_disclaimer_sits_beside_the_logo_grid(self):
		html = self.render_as_guest()
		gallery = html.index('id="templates"')
		disclaimer = html.index("trademarks of Frappe Technologies")
		how_it_works = html.index('id="how"')
		self.assertLess(gallery, disclaimer)
		self.assertLess(disclaimer, how_it_works)

	def test_the_page_never_claims_a_public_url(self):
		html = self.render_as_guest()
		self.assertIn("Unreachable", html)
		self.assertIn("Nothing is published to the internet.", html)

	def test_context_cost_does_not_grow_with_the_catalogue(self):
		baseline = _count_queries(self._build_context)

		self.addCleanup(_delete_pack)
		frappe.get_doc(
			{
				"doctype": "Credit Pack",
				"pack_label": PACK,
				"inr_price": 999,
				"credits": 100,
				"is_active": 1,
				"sort_order": 98,
			}
		).insert(ignore_permissions=True)

		grown = _count_queries(self._build_context)
		self.assertEqual(grown, baseline, "another pack cost another query — the read path is per-row")

	def test_context_is_two_queries(self):
		self._build_context()  # warm the doctype meta and Singles caches
		self.assertEqual(_count_queries(self._build_context), 2)

	def _build_context(self):
		config.clear_size_index()
		home.get_context(frappe._dict())


def _count_queries(action) -> int:
	"""Statements sent to MariaDB while `action` runs. Same trick as test_api."""
	count = 0
	original_sql = frappe.db.__class__.sql

	def counting_sql(*args, **kwargs):
		nonlocal count
		count += 1
		return original_sql(*args, **kwargs)

	frappe.db.__class__.sql = counting_sql
	try:
		action()
	finally:
		frappe.db.__class__.sql = original_sql
	return count
