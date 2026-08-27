# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The site name as an allocation: claimed by insert, refused by the primary key.

`site_name` keys a MariaDB database through `sha1(site_name)[:16]`, created with
`CREATE OR REPLACE DATABASE`, so two benches that win one name share one database and the
second drops the first tenant's data. The check that used to guard it ran in the request and
the row was written by a worker two minutes later.

A uniqueness violation is the one concurrency property a single transaction can prove, because
the second insert sees the first from the same connection. What twelve simultaneous callers do
is `scripts/admission_drill.py --mode site-name`.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.query_builder import DocType
from frappe.tests import IntegrationTestCase

from benchpress import api, site_names
from benchpress.benchpress.doctype.bench_instance import get_instance_id
from benchpress.credits import admission_repair
from benchpress.patches.name_bench_sites_by_site_name import execute as name_bench_sites

BENCH = "Bench Instance"
SITE = "Bench Site"
SETTINGS = "BenchPress Settings"

DOMAIN = "benchpress.cloud"
LABS = ("site-claim-lab-a", "site-claim-lab-b")


def _ensure_lab(lab_id: str):
	if frappe.db.exists("Lab", lab_id):
		return frappe.get_doc("Lab", lab_id)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Site claim {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
		}
	).insert(ignore_permissions=True)


def _drop_site(site_name: str) -> None:
	"""Every row that still carries this site name, including a suffixed duplicate."""
	for name in frappe.get_all(SITE, filters={"site_name": ("like", f"{site_name}%")}, pluck="name"):
		frappe.delete_doc(SITE, name, force=True, ignore_permissions=True)


def _drop_bench(bench_name: str) -> None:
	for site in frappe.get_all(SITE, filters={"bench": bench_name}, pluck="name"):
		frappe.delete_doc(SITE, site, force=True, ignore_permissions=True)
	if frappe.db.exists(BENCH, bench_name):
		frappe.delete_doc(BENCH, bench_name, force=True, ignore_permissions=True)


class TestSiteNameClaim(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.labs = [_ensure_lab(lab_id) for lab_id in LABS]

	def setUp(self):
		frappe.set_user("Administrator")
		self._set_single("base_domain", DOMAIN)
		# Off for the whole class: `create_bench` is behind `requires_admission`, and a module
		# about names has no business being refused by a cap or a balance.
		self._set_single("enable_credits", 0)
		for lab in self.labs:
			_drop_bench(get_instance_id("Administrator", lab.name))

	def _set_single(self, field: str, value) -> None:
		before = frappe.db.get_single_value(SETTINGS, field)
		frappe.db.set_single_value(SETTINGS, field, value)
		frappe.clear_cache(doctype=SETTINGS)
		self.addCleanup(frappe.clear_cache, doctype=SETTINGS)
		self.addCleanup(frappe.db.set_single_value, SETTINGS, field, before)

	def _bench(self, lab, site_name: str):
		bench = frappe.get_doc(
			{"doctype": BENCH, "lab": lab.name, "frappe_version": lab.frappe_version}
		).insert(ignore_permissions=True)
		frappe.db.set_value(BENCH, bench.name, "site_name", site_name, update_modified=False)
		bench.site_name = site_name
		self.addCleanup(_drop_bench, bench.name)
		return bench

	def _claimed(self, bench, status="Creating"):
		site = frappe.get_doc(
			{"doctype": SITE, "site_name": bench.site_name, "bench": bench.name, "status": status}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, SITE, site.name, force=True, ignore_permissions=True)
		return site

	# --- The key --------------------------------------------------------------

	def test_the_row_is_named_by_its_site_name(self):
		bench = self._bench(self.labs[0], f"named.{DOMAIN}")
		self.assertEqual(self._claimed(bench).name, f"named.{DOMAIN}")

	def test_a_second_row_for_one_name_is_refused_by_the_database(self):
		first = self._bench(self.labs[0], f"contested.{DOMAIN}")
		second = self._bench(self.labs[1], f"contested.{DOMAIN}")
		self._claimed(first)

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc({"doctype": SITE, "site_name": second.site_name, "bench": second.name}).insert(
				ignore_permissions=True
			)

	# --- The refusal ----------------------------------------------------------

	def test_a_taken_name_is_refused_in_the_request(self):
		taken = self._bench(self.labs[0], f"taken.{DOMAIN}")
		self._claimed(taken, status="Active")

		with self.assertRaises(frappe.ValidationError) as refusal:
			api.create_bench(frappe.as_json({"lab": self.labs[1].name, "site_name": "taken"}))
		self.assertIn("is already in use", str(refusal.exception))
		self.assertEqual(frappe.db.get_value(SITE, f"taken.{DOMAIN}", "bench"), taken.name)

	def test_the_refusal_carries_one_sentence_and_not_the_framework_s(self):
		"""The framework msgprints "Bench Site X already exists" before it raises."""
		taken = self._bench(self.labs[0], f"onesentence.{DOMAIN}")
		self._claimed(taken, status="Active")
		frappe.clear_messages()

		with self.assertRaises(frappe.ValidationError):
			api.create_bench(frappe.as_json({"lab": self.labs[1].name, "site_name": "onesentence"}))

		self.assertNotIn("already exists", self._messages())

	def test_a_redeploy_carries_no_message_of_its_own(self):
		"""The duplicate its claim hits is expected, so nothing about it belongs in the reply."""
		owner = self._bench(self.labs[0], f"quiet.{DOMAIN}")
		self._claimed(owner, status="Active")
		frappe.clear_messages()

		api.create_bench(frappe.as_json({"lab": self.labs[0].name, "site_name": "quiet"}))

		self.assertNotIn("already exists", self._messages())

	def _messages(self) -> str:
		return " ".join(str(entry) for entry in (frappe.local.message_log or []))

	def test_an_inactive_name_is_still_claimed(self):
		"""`stop_bench` deactivates without dropping, so the database is still on disk."""
		stopped = self._bench(self.labs[0], f"stopped.{DOMAIN}")
		self._claimed(stopped, status="Inactive")

		with self.assertRaises(frappe.ValidationError):
			api.create_bench(frappe.as_json({"lab": self.labs[1].name, "site_name": "stopped"}))

	# --- The bench that owns it ----------------------------------------------

	def test_a_redeploy_of_the_bench_that_owns_the_name_is_admitted(self):
		owner = self._bench(self.labs[0], f"mine.{DOMAIN}")
		self._claimed(owner, status="Active")

		result = api.create_bench(frappe.as_json({"lab": self.labs[0].name, "site_name": "mine"}))

		self.assertEqual(result["name"], owner.name)
		self.assertEqual(result["status"], "Deploying")

	def test_a_first_deploy_claims_the_name_before_any_worker_runs(self):
		result = api.create_bench(frappe.as_json({"lab": self.labs[0].name, "site_name": "early"}))
		self.addCleanup(_drop_bench, result["name"])

		claimed = frappe.db.get_value(SITE, f"early.{DOMAIN}", ["bench", "status"], as_dict=True)
		self.assertEqual(claimed.bench, result["name"])
		self.assertEqual(claimed.status, "Creating")

	def test_the_claim_is_owned_by_the_bench_and_not_by_the_session(self):
		"""`Bench Site` is read `if_owner`: an admin deploying for a tenant must not take it over."""
		bench = self._bench(self.labs[0], f"tenant.{DOMAIN}")
		frappe.db.set_value(BENCH, bench.name, "owner", "tenant@example.com", update_modified=False)
		bench.owner = "tenant@example.com"

		site_names.claim(bench)

		self.assertEqual(frappe.db.get_value(SITE, bench.site_name, "owner"), "tenant@example.com")

	def test_deleting_the_instance_frees_the_name(self):
		"""The row cannot outlive its bench: nothing would ever drop the database it named."""
		bench = self._bench(self.labs[0], f"freed.{DOMAIN}")
		self._claimed(bench)

		frappe.delete_doc(BENCH, bench.name, force=True, ignore_permissions=True)

		self.assertFalse(frappe.db.exists(SITE, f"freed.{DOMAIN}"))

	# --- Contention -----------------------------------------------------------

	def test_a_second_claim_on_one_name_is_refused(self):
		"""The whole design is that the primary key is the check."""
		owner = self._bench(self.labs[0], f"contended.{DOMAIN}")
		intruder = self._bench(self.labs[1], f"contended.{DOMAIN}")
		site_names.claim(owner)
		self.addCleanup(frappe.delete_doc, SITE, owner.site_name, force=True, ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError) as refusal:
			site_names.claim(intruder)

		self.assertIn("is already in use", str(refusal.exception))
		self.assertEqual(frappe.db.get_value(SITE, owner.site_name, "bench"), owner.name)

	def test_the_bench_that_holds_the_name_can_claim_it_again(self):
		"""A redeploy claims the name it already owns, and the duplicate is not an error."""
		owner = self._bench(self.labs[0], f"reclaimed.{DOMAIN}")
		site_names.claim(owner)
		self.addCleanup(frappe.delete_doc, SITE, owner.site_name, force=True, ignore_permissions=True)

		site_names.claim(owner)

		self.assertEqual(frappe.db.count(SITE, {"site_name": owner.site_name}), 1)

	# --- Release --------------------------------------------------------------

	def test_release_frees_every_name_the_bench_holds(self):
		bench = self._bench(self.labs[0], f"released.{DOMAIN}")
		self._claimed(bench)

		site_names.release(bench.name)

		self.assertFalse(frappe.db.exists(SITE, f"released.{DOMAIN}"))

	# --- The worker's last line of defence ------------------------------------

	def test_recording_a_site_that_belongs_to_another_bench_raises(self):
		from benchpress.deploy_manager import _record_primary_site

		owner = self._bench(self.labs[0], f"defended.{DOMAIN}")
		self._claimed(owner, status="Active")
		intruder = self._bench(self.labs[1], f"defended.{DOMAIN}")

		with self.assertRaises(Exception) as refusal:
			_record_primary_site(intruder, self.labs[1], "secret")
		self.assertIn(owner.name, str(refusal.exception))

	def test_recording_activates_the_row_the_request_claimed(self):
		from benchpress.deploy_manager import _record_primary_site

		bench = self._bench(self.labs[0], f"activated.{DOMAIN}")
		claimed = self._claimed(bench)

		_record_primary_site(bench, self.labs[0], "secret")

		self.assertEqual(frappe.db.get_value(SITE, claimed.name, "status"), "Active")
		self.assertEqual(frappe.db.count(SITE, {"bench": bench.name}), 1)

	# --- The standing rule ----------------------------------------------------

	def test_a_claim_no_deploy_ever_answered_is_retired(self):
		bench = self._bench(self.labs[0], f"stranded.{DOMAIN}")
		site = self._claimed(bench)
		frappe.db.set_value(SITE, site.name, "modified", "2020-01-01 00:00:00", update_modified=False)

		admission_repair.reconcile_admissions()

		self.assertEqual(frappe.db.get_value(SITE, site.name, "status"), "Inactive")

	def test_a_claim_still_inside_the_deploy_window_is_left_alone(self):
		bench = self._bench(self.labs[0], f"working.{DOMAIN}")
		site = self._claimed(bench)

		admission_repair.reconcile_admissions()

		self.assertEqual(frappe.db.get_value(SITE, site.name, "status"), "Creating")


class TestQualify(unittest.TestCase):
	def test_returns_none_for_empty_input(self):
		self.assertIsNone(site_names.qualify(None))
		self.assertIsNone(site_names.qualify(""))
		self.assertIsNone(site_names.qualify("   "))

	@patch("benchpress.site_names.frappe.db.get_single_value", return_value="benchpress.cloud")
	def test_lowercases_and_appends_base_domain(self, get_single_value):
		self.assertEqual(site_names.qualify("Acme"), "acme.benchpress.cloud")

	@patch("benchpress.site_names.frappe.db.get_single_value", return_value=None)
	def test_falls_back_to_localhost_when_base_domain_unset(self, get_single_value):
		self.assertEqual(site_names.qualify("acme"), "acme.localhost")

	def test_rejects_a_dotted_label(self):
		with self.assertRaises(frappe.ValidationError):
			site_names.qualify("acme.example.com")

	def test_rejects_invalid_characters(self):
		with self.assertRaises(frappe.ValidationError):
			site_names.qualify("Acme_1")

	def test_rejects_a_label_over_max_length(self):
		with self.assertRaises(frappe.ValidationError):
			site_names.qualify("a" * 64)


class TestNameBenchSitesBySiteName(IntegrationTestCase):
	"""The patch that moves existing rows onto the key, on data that predates it."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _ensure_lab("site-claim-patch-lab")
		cls.bench = frappe.get_doc({"doctype": BENCH, "lab": cls.lab.name}).insert(ignore_permissions=True)

	def _unkeyed_site(self, site_name: str, status: str = "Active"):
		"""A row named the way Frappe named them before `autoname: field:site_name`.

		The name is moved by query rather than by `rename_doc`, which syncs the autoname field to
		the new name and so cannot produce the very shape the patch exists to repair. Two rows
		share a name by being made one at a time, each moved off the key before the next.
		"""
		site = frappe.get_doc(
			{"doctype": SITE, "site_name": site_name, "bench": self.bench.name, "status": status}
		).insert(ignore_permissions=True)
		table = DocType(SITE)
		unkeyed = frappe.generate_hash(length=10)
		frappe.qb.update(table).set(table.name, unkeyed).where(table.name == site.name).run()
		self.addCleanup(_drop_site, site_name)
		return frappe.get_doc(SITE, unkeyed)

	def test_a_clean_row_is_renamed_onto_its_site_name(self):
		site = self._unkeyed_site(f"clean.{DOMAIN}")
		self.assertNotEqual(site.name, site.site_name)

		name_bench_sites()

		self.assertTrue(frappe.db.exists(SITE, f"clean.{DOMAIN}"))
		self.assertFalse(frappe.db.exists(SITE, site.name))

	def test_running_it_twice_changes_nothing(self):
		self._unkeyed_site(f"twice.{DOMAIN}")
		name_bench_sites()
		modified = frappe.db.get_value(SITE, f"twice.{DOMAIN}", "modified")

		name_bench_sites()

		self.assertEqual(frappe.db.get_value(SITE, f"twice.{DOMAIN}", "modified"), modified)

	def test_a_duplicate_loser_is_suffixed_and_deactivated_never_deleted(self):
		winner = self._unkeyed_site(f"shared.{DOMAIN}", status="Active")
		loser = self._unkeyed_site(f"shared.{DOMAIN}", status="Inactive")

		name_bench_sites()

		self.assertEqual(frappe.db.get_value(SITE, f"shared.{DOMAIN}", "bench"), winner.bench)
		survivors = frappe.get_all(
			SITE, filters={"site_name": ("like", f"shared.{DOMAIN}#dup-%")}, fields=["name", "status"]
		)
		self.assertEqual(len(survivors), 1)
		self.assertEqual(survivors[0].status, "Inactive")
		self.assertFalse(frappe.db.exists(SITE, loser.name))

	def test_the_survivor_is_the_row_furthest_from_gone(self):
		self._unkeyed_site(f"ranked.{DOMAIN}", status="Inactive")
		live = self._unkeyed_site(f"ranked.{DOMAIN}", status="Active")

		name_bench_sites()

		self.assertEqual(frappe.db.get_value(SITE, f"ranked.{DOMAIN}", "creation"), live.creation)

	def test_a_row_whose_bench_is_gone_is_still_renamed(self):
		"""Staging has one. `rename_doc` must not validate, or the link check stops the migration."""
		orphan = self._unkeyed_site(f"orphan.{DOMAIN}")
		frappe.db.set_value(SITE, orphan.name, "bench", "a-bench-that-never-existed")

		name_bench_sites()

		self.assertTrue(frappe.db.exists(SITE, f"orphan.{DOMAIN}"))
