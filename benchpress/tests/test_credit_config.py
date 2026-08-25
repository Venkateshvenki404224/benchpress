# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 1 of the credits engine ships config only — nothing enforces anything yet.

So the assertions here are about the two contracts every later phase leans on: the config is
seeded and internally consistent, and `benchpress.credits.config` is the only read path, cheap
enough to call in a request. The most important one is `test_credits_are_off_by_default`: a
self-hoster must never discover that credits exist.
"""

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.credits import config
from benchpress.credits.seed import CREDIT_PACKS, INSTANCE_SIZES, seed_defaults

BENCHPRESS_SETTINGS = "BenchPress Settings"


class TestCreditConfig(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# The test site predates this doctype, so the patch that seeds it has already been
		# recorded as run. Seeding here is idempotent and doubles as a test of the seeder.
		seed_defaults()
		# Class fixtures must outlive the per-test transaction.
		frappe.db.commit()  # nosemgrep

	def setUp(self):
		config.clear_size_index()

	def test_seeded_sizes_and_packs_exist(self):
		for row in INSTANCE_SIZES:
			self.assertTrue(frappe.db.exists("Instance Size", row["size_label"]))
		for row in CREDIT_PACKS:
			self.assertTrue(frappe.db.exists("Credit Pack", row["pack_label"]))

	def test_seeding_twice_creates_no_duplicates(self):
		before = frappe.db.count("Instance Size")
		seed_defaults()
		self.assertEqual(frappe.db.count("Instance Size"), before)

	def test_exactly_one_size_is_default(self):
		defaults = frappe.get_all("Instance Size", filters={"is_default": 1}, pluck="name")
		self.assertEqual(len(defaults), 1, f"expected one default size, found {defaults}")

	def test_a_second_default_size_is_rejected(self):
		size = frappe.new_doc("Instance Size")
		size.update(
			{
				"size_label": "Second Default",
				"memory_limit": "8g",
				"cpu_cores": 8,
				"credits_per_hour": 8.0,
				"is_default": 1,
			}
		)
		self.assertRaises(frappe.ValidationError, size.insert)

	def test_a_size_below_one_core_is_rejected(self):
		size = frappe.new_doc("Instance Size")
		size.update({"size_label": "Zero Core", "memory_limit": "1g", "cpu_cores": 0})
		self.assertRaises(frappe.ValidationError, size.insert)

	def test_credits_are_off_by_default(self):
		"""The master switch ships off, and off must mean the feature does not exist."""
		field = frappe.get_meta(BENCHPRESS_SETTINGS).get_field("enable_credits")
		self.assertEqual(field.default, "0")

		self.set_credits_enabled(0)
		self.assertFalse(config.credits_enabled())

	def test_credits_enabled_reads_the_switch(self):
		self.set_credits_enabled(1)
		self.assertTrue(config.credits_enabled())

	def test_size_for_lab_resolves_every_seeded_size(self):
		for row in INSTANCE_SIZES:
			lab = frappe._dict(memory_limit=row["memory_limit"], cpu_cores=row["cpu_cores"])
			self.assertEqual(config.size_for_lab(lab).size_label, row["size_label"])

	def test_size_for_lab_is_case_insensitive_on_memory(self):
		lab = frappe._dict(memory_limit="2G", cpu_cores=2)
		self.assertEqual(config.size_for_lab(lab).size_label, "Medium")

	def test_size_for_lab_falls_back_to_the_default(self):
		lab = frappe._dict(memory_limit="777m", cpu_cores=3)
		self.assertEqual(config.size_for_lab(lab).name, config.default_size().name)

	def test_size_for_lab_hits_the_database_once_per_request(self):
		lab = frappe._dict(memory_limit="1g", cpu_cores=1)
		config.size_for_lab(lab)
		with self.assertQueryCount(0):
			config.size_for_lab(lab)

	def test_active_packs_are_ordered_and_filtered(self):
		labels = [pack.pack_label for pack in config.active_packs()]
		self.assertEqual(labels, [row["pack_label"] for row in CREDIT_PACKS])

		self.deactivate_pack("Regular")
		self.assertNotIn("Regular", [pack.pack_label for pack in config.active_packs()])

	def test_a_pack_granting_no_credits_is_rejected(self):
		pack = frappe.new_doc("Credit Pack")
		pack.update({"pack_label": "Empty", "inr_price": 99, "credits": 0})
		self.assertRaises(frappe.ValidationError, pack.insert)

	def test_settings_are_served_from_cache(self):
		config.settings()
		with self.assertQueryCount(0):
			self.assertEqual(config.settings().doctype, "Credit Settings")

	def test_settings_carry_the_seeded_defaults(self):
		settings = config.settings()
		self.assertEqual(settings.reap_after_days, 7)
		self.assertEqual(settings.signup_grant_credits, 40)

	def test_a_negative_cap_is_rejected(self):
		settings = frappe.get_doc("Credit Settings")
		self.addCleanup(self.restore_setting, "reap_after_days", settings.reap_after_days)
		settings.reap_after_days = -1
		self.assertRaises(frappe.ValidationError, settings.save)

	def set_credits_enabled(self, value: int) -> None:
		original = frappe.db.get_single_value(BENCHPRESS_SETTINGS, "enable_credits")
		self.addCleanup(frappe.db.set_single_value, BENCHPRESS_SETTINGS, "enable_credits", original)
		self.addCleanup(frappe.clear_cache, doctype=BENCHPRESS_SETTINGS)
		frappe.db.set_single_value(BENCHPRESS_SETTINGS, "enable_credits", value)
		frappe.clear_cache(doctype=BENCHPRESS_SETTINGS)

	def deactivate_pack(self, label: str) -> None:
		pack = frappe.get_doc("Credit Pack", label)
		self.addCleanup(self.reactivate_pack, label)
		pack.is_active = 0
		pack.save(ignore_permissions=True)

	def reactivate_pack(self, label: str) -> None:
		pack = frappe.get_doc("Credit Pack", label)
		pack.is_active = 1
		pack.save(ignore_permissions=True)

	def restore_setting(self, field: str, value) -> None:
		settings = frappe.get_doc("Credit Settings")
		settings.set(field, value)
		settings.save(ignore_permissions=True)
