# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The JSON-LD graph. No network, no database."""

import json
import unittest

import frappe

from benchpress import structured_data as sd

FAQ = [
	frappe._dict({"question": "Do I need Docker?", "answer": "No."}),
	frappe._dict({"question": "", "answer": "orphan"}),
]


def graph(payload: str) -> dict:
	return {node["@type"]: node for node in json.loads(payload)["@graph"]}


class TestSelfHostGraph(unittest.TestCase):
	def test_carries_the_organisation_and_the_page(self):
		nodes = graph(sd.self_host("a description"))
		self.assertEqual(sorted(nodes), ["Organization", "WebPage"])
		self.assertTrue(nodes["WebPage"]["url"].endswith("/self-host"))


class TestServicesGraph(unittest.TestCase):
	def test_carries_the_organisation_and_the_page(self):
		nodes = graph(sd.services("a description"))
		self.assertEqual(sorted(nodes), ["Organization", "WebPage"])
		self.assertTrue(nodes["WebPage"]["url"].endswith("/services"))


class TestComparisonGraph(unittest.TestCase):
	def test_carries_the_page_the_breadcrumbs_and_the_questions(self):
		nodes = graph(sd.comparison("/vs/x", "X", "a description", FAQ))
		self.assertEqual(sorted(nodes), ["BreadcrumbList", "FAQPage", "Organization", "WebPage"])

	def test_the_trail_starts_at_the_site_root(self):
		trail = graph(sd.comparison("/vs/x", "X", "d", FAQ))["BreadcrumbList"]["itemListElement"]
		self.assertEqual([row["position"] for row in trail], [1, 2])
		self.assertEqual(trail[0]["name"], "BenchPress")
		self.assertTrue(trail[1]["item"].endswith("/vs/x"))


class TestLandingGraph(unittest.TestCase):
	def test_carries_the_four_nodes(self):
		nodes = graph(sd.landing("a description", FAQ))
		self.assertEqual(sorted(nodes), ["FAQPage", "Organization", "SoftwareApplication", "WebSite"])

	def test_software_claims_match_the_product(self):
		app = graph(sd.landing("a description", FAQ))["SoftwareApplication"]
		self.assertEqual(app["applicationCategory"], "DeveloperApplication")
		self.assertEqual(app["offers"]["price"], "0")
		self.assertTrue(app["isAccessibleForFree"])
		self.assertIn("agpl", app["license"].lower())
		# Nobody has reviewed it, so there is nothing to claim.
		self.assertNotIn("aggregateRating", app)

	def test_faq_skips_incomplete_rows(self):
		faq = graph(sd.landing("d", FAQ))["FAQPage"]
		self.assertEqual(len(faq["mainEntity"]), 1)
		self.assertEqual(faq["mainEntity"][0]["name"], "Do I need Docker?")

	def test_no_faq_node_when_there_are_no_questions(self):
		self.assertNotIn("FAQPage", graph(sd.landing("d", [])))

	def test_nodes_reference_the_organization_by_id(self):
		nodes = graph(sd.landing("d", FAQ))
		org_id = nodes["Organization"]["@id"]
		self.assertEqual(nodes["WebSite"]["publisher"]["@id"], org_id)
		self.assertEqual(nodes["SoftwareApplication"]["author"]["@id"], org_id)


class TestContactGraph(unittest.TestCase):
	def test_contact_point_only_when_an_address_is_configured(self):
		self.assertNotIn("contactPoint", graph(sd.contact("d", ""))["Organization"])
		org = graph(sd.contact("d", "team@example.com"))["Organization"]
		self.assertEqual(org["contactPoint"]["email"], "team@example.com")


class TestEncoding(unittest.TestCase):
	def test_a_value_cannot_close_the_script_block(self):
		payload = sd.landing("</script><script>alert(1)</script>", [])
		self.assertNotIn("</script>", payload)
		self.assertIn("\\u003c", payload)
		# Still valid JSON, and the text survives intact once parsed.
		app = graph(payload)["SoftwareApplication"]
		self.assertIn("alert(1)", app["description"])

	def test_output_is_valid_json(self):
		self.assertEqual(json.loads(sd.about("d"))["@context"], "https://schema.org")
