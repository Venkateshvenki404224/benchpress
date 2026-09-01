# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""`/llms.txt` describes the product first, then the docs index leadtype generated."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import llms_txt
from benchpress.benchpress.site_content import ABOUT_SEED, clear_content_cache
from benchpress.public_site import CONFIG_KEY

GENERATED = """# BenchPress

> Press a button. Get a Frappe bench.

## Overview

BenchPress deploys a Frappe bench from a template.

## User Track

- [Quick tour](/docs/user/quick-tour.md): The five screens.
"""


class TestLlmsTxt(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		clear_content_cache()
		self.addCleanup(clear_content_cache)

	def test_it_opens_with_the_title_and_a_one_line_summary(self):
		lines = llms_txt.build().splitlines()
		self.assertEqual(lines[0], "# BenchPress")
		self.assertEqual(lines[2], f"> {llms_txt.SUMMARY}")

	def test_the_product_is_described_before_the_documentation(self):
		body = llms_txt.build()
		self.assertLess(body.index("## What BenchPress is"), body.index("## User Track"))

	def test_it_answers_what_the_product_is_not(self):
		body = llms_txt.build()
		self.assertIn(ABOUT_SEED["contrast_rows"][0]["not_text"], body)

	def test_the_install_block_shows_the_commands_that_run(self):
		block = llms_txt.install_block()
		self.assertIn("bench get-app", block)
		self.assertIn("setup.sh", block)
		# `$ ` is a prompt in a screenshot, not something a reader can paste.
		self.assertNotIn("$ ", block)
		# There is no clone-and-run path: BenchPress installs into an existing bench.
		self.assertNotIn("git clone", block)

	def test_every_link_is_absolute(self):
		for line in llms_txt.build().splitlines():
			if line.startswith("- ["):
				with self.subTest(line=line):
					self.assertIn("](http", line)

	def test_a_generated_site_relative_link_is_given_a_host(self):
		self.assertIn("](http", llms_txt.absolutise("- [Quick tour](/docs/user/quick-tour.md): x"))

	def test_the_generated_summary_section_is_dropped_and_the_rest_kept(self):
		kept = llms_txt.keep_sections(GENERATED)
		self.assertTrue(kept.startswith("## User Track"))
		self.assertNotIn("## Overview", kept)

	def test_a_missing_docs_index_leaves_the_product_half_standing(self):
		with patch.object(llms_txt, "docs_sections", return_value=""):
			self.assertIn("## Requirements", llms_txt.build())

	def test_the_route_is_claimed_only_where_the_public_site_is_on(self):
		for enabled, expected in ((1, True), (0, False)):
			with self.subTest(enabled=enabled), patch.dict(frappe.conf, {CONFIG_KEY: enabled}):
				renderer = llms_txt.LlmsTxtRenderer(llms_txt.ROUTE)
				self.assertEqual(renderer.can_render(), expected)

	def test_another_route_is_never_claimed(self):
		with patch.dict(frappe.conf, {CONFIG_KEY: 1}):
			self.assertFalse(llms_txt.LlmsTxtRenderer("llms-full.txt").can_render())
