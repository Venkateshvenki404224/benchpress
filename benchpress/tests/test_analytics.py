# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The analytics gate and the GitHub traffic collector. No network, no container."""

import unittest
from unittest.mock import patch

import frappe

from benchpress import analytics, github_traffic


class TestAnalyticsGate(unittest.TestCase):
	def test_tracker_is_empty_without_config(self):
		with patch.dict(frappe.conf, {}, clear=False):
			frappe.conf.pop(analytics.SCRIPT_KEY, None)
			frappe.conf.pop(analytics.DOMAIN_KEY, None)
			self.assertEqual(analytics.tracker(), {})

	def test_tracker_is_empty_when_only_one_key_is_set(self):
		with patch.dict(frappe.conf, {analytics.SCRIPT_KEY: "https://u.example/s.js"}):
			frappe.conf.pop(analytics.DOMAIN_KEY, None)
			self.assertEqual(analytics.tracker(), {})

	def test_tracker_reads_both_keys(self):
		values = {analytics.SCRIPT_KEY: "https://u.example/s.js", analytics.DOMAIN_KEY: "abc-123"}
		with patch.dict(frappe.conf, values):
			self.assertEqual(
				analytics.tracker(), {"script": "https://u.example/s.js", "website_id": "abc-123"}
			)

	def test_blank_strings_do_not_count_as_configured(self):
		with patch.dict(frappe.conf, {analytics.SCRIPT_KEY: "  ", analytics.DOMAIN_KEY: "  "}):
			self.assertEqual(analytics.tracker(), {})


class TestGitHubTrafficParsing(unittest.TestCase):
	def test_snapshot_does_nothing_without_config(self):
		with patch.dict(frappe.conf, {}, clear=False):
			frappe.conf.pop(github_traffic.REPO_KEY, None)
			frappe.conf.pop(github_traffic.TOKEN_KEY, None)
			self.assertEqual(github_traffic.snapshot_traffic(), [])

	def test_by_day_keys_on_the_date_part_of_the_timestamp(self):
		client = github_traffic.GitHubTraffic("owner/repo", "token")
		payload = {
			"clones": [
				{"timestamp": "2026-08-20T00:00:00Z", "count": 9, "uniques": 4},
				{"timestamp": "2026-08-21T00:00:00Z", "count": 2, "uniques": 2},
			]
		}
		with patch.object(client, "get", return_value=payload):
			self.assertEqual(sorted(client.by_day("/traffic/clones", "clones")), ["2026-08-20", "2026-08-21"])

	def test_by_day_skips_rows_with_no_timestamp(self):
		client = github_traffic.GitHubTraffic("owner/repo", "token")
		with patch.object(client, "get", return_value={"clones": [{"count": 1}]}):
			self.assertEqual(client.by_day("/traffic/clones", "clones"), {})

	def test_by_day_is_empty_when_the_key_is_absent(self):
		client = github_traffic.GitHubTraffic("owner/repo", "token")
		with patch.object(client, "get", return_value={}):
			self.assertEqual(client.by_day("/traffic/views", "views"), {})

	def test_top_referrer_reads_the_first_row(self):
		self.assertEqual(
			github_traffic.top_referrer([{"referrer": "news.ycombinator.com"}]), "news.ycombinator.com"
		)

	def test_top_referrer_is_blank_when_there_are_none(self):
		self.assertEqual(github_traffic.top_referrer([]), "")
		self.assertEqual(github_traffic.top_referrer(None), "")


class TestGitHubTrafficRows(unittest.TestCase):
	REPO = "owner/test-repo"

	def tearDown(self):
		# Every row this class writes is removed here; nothing survives the run.
		for name in frappe.get_all(github_traffic.DOCTYPE, filters={"repository": self.REPO}, pluck="name"):
			frappe.delete_doc(github_traffic.DOCTYPE, name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def test_write_snapshots_creates_one_row_per_day(self):
		client = self.client()
		names = client.write_snapshots()

		self.assertEqual(len(names), 2)
		rows = frappe.get_all(
			github_traffic.DOCTYPE,
			filters={"repository": self.REPO},
			fields=["snapshot_date", "clone_uniques", "view_uniques"],
			order_by="snapshot_date asc",
		)
		self.assertEqual([str(row.snapshot_date) for row in rows], ["2026-08-20", "2026-08-21"])
		self.assertEqual([row.clone_uniques for row in rows], [4, 2])
		self.assertEqual([row.view_uniques for row in rows], [11, 0])

	def test_write_snapshots_is_idempotent(self):
		self.client().write_snapshots()
		self.client().write_snapshots()

		self.assertEqual(frappe.db.count(github_traffic.DOCTYPE, {"repository": self.REPO}), 2)

	def test_duplicate_rows_are_refused(self):
		doc = frappe.get_doc(
			{
				"doctype": github_traffic.DOCTYPE,
				"repository": self.REPO,
				"snapshot_date": "2026-08-20",
			}
		).insert(ignore_permissions=True)
		self.assertTrue(doc.name)

		duplicate = frappe.get_doc(
			{
				"doctype": github_traffic.DOCTYPE,
				"repository": self.REPO,
				"snapshot_date": "2026-08-20",
			}
		)
		self.assertRaises(frappe.ValidationError, duplicate.insert, ignore_permissions=True)

	def client(self) -> github_traffic.GitHubTraffic:
		client = github_traffic.GitHubTraffic(self.REPO, "token")
		responses = {
			"/traffic/clones": {
				"clones": [
					{"timestamp": "2026-08-20T00:00:00Z", "count": 9, "uniques": 4},
					{"timestamp": "2026-08-21T00:00:00Z", "count": 2, "uniques": 2},
				]
			},
			"/traffic/views": {"views": [{"timestamp": "2026-08-20T00:00:00Z", "count": 40, "uniques": 11}]},
			"/traffic/popular/referrers": [{"referrer": "news.ycombinator.com"}],
			"": {"stargazers_count": 7, "forks_count": 3},
		}
		client.get = lambda path: responses[path]
		return client
