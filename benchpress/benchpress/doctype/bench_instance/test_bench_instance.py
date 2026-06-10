# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import hashlib
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.benchpress.doctype.bench_instance import get_instance_id

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _make_lab(lab_id="test-lab-bench-instance"):
	if frappe.db.exists("Lab", lab_id):
		return frappe.get_doc("Lab", lab_id)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": "Test Lab (BenchInstance)",
			"frappe_version": "version-15",
		}
	).insert(ignore_permissions=True)


class IntegrationTestBenchInstance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab()
		cls.lab_name = cls.lab.name

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab_name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _insert_bench(self):
		frappe.set_user("Administrator")
		existing = get_instance_id("Administrator", self.lab_name)
		if frappe.db.exists("Bench Instance", existing):
			frappe.delete_doc("Bench Instance", existing, force=True, ignore_permissions=True)
			frappe.db.commit()
		bench = frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": self.lab_name,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
		self.addCleanup(
			lambda n=bench.name: frappe.delete_doc("Bench Instance", n, force=True, ignore_permissions=True)
			if frappe.db.exists("Bench Instance", n)
			else None
		)
		self.addCleanup(frappe.db.commit)
		return bench

	def test_before_insert_sets_bench_name_to_instance_id(self):
		bench = self._insert_bench()
		expected = get_instance_id("Administrator", self.lab_name)
		self.assertEqual(bench.bench_name, expected)

	def test_before_insert_sets_site_name_with_localhost_suffix(self):
		bench = self._insert_bench()
		self.assertTrue(bench.site_name.endswith(".localhost"))

	def test_before_insert_derives_ssh_username_from_email(self):
		bench = self._insert_bench()
		self.assertEqual(bench.ssh_username, "administrator")

	def test_derive_username_strips_invalid_chars(self):
		bench = frappe.new_doc("Bench Instance")
		with patch.object(frappe, "session", MagicMock(user="John#Doe@example.com")):
			result = bench._derive_username()
		self.assertEqual(result, "johndoe")

	def test_derive_username_handles_numeric_only_prefix(self):
		bench = frappe.new_doc("Bench Instance")
		with patch.object(frappe, "session", MagicMock(user="12345@example.com")):
			result = bench._derive_username()
		self.assertEqual(result, "user12345")

	def test_derive_username_caps_at_32_chars(self):
		bench = frappe.new_doc("Bench Instance")
		long_email = "a" * 40 + "@example.com"
		with patch.object(frappe, "session", MagicMock(user=long_email)):
			result = bench._derive_username()
		self.assertLessEqual(len(result), 32)

	def test_enqueue_start_throws_when_no_container_id(self):
		bench = self._insert_bench()
		bench.container_id = None
		bench.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			bench.enqueue_start()

	@patch("benchpress.docker_manager.start_container")
	def test_enqueue_start_starts_container_and_sets_running(self, mock_start):
		bench = self._insert_bench()
		bench.container_id = "test-container-abc"
		bench.save(ignore_permissions=True)
		bench.enqueue_start()
		mock_start.assert_called_once_with("test-container-abc")
		bench.reload()
		self.assertEqual(bench.status, "Running")

	@patch("benchpress.deploy_manager.stop_bench")
	def test_enqueue_stop_calls_stop_bench(self, mock_stop):
		bench = self._insert_bench()
		bench.enqueue_stop()
		mock_stop.assert_called_once_with(bench.name)

	def test_get_instance_id_is_deterministic(self):
		id1 = get_instance_id("user@example.com", "lab-001")
		id2 = get_instance_id("user@example.com", "lab-001")
		self.assertEqual(id1, id2)

	def test_get_instance_id_different_for_different_inputs(self):
		id1 = get_instance_id("user@example.com", "lab-001")
		id2 = get_instance_id("other@example.com", "lab-001")
		self.assertNotEqual(id1, id2)

	def test_get_instance_id_is_md5_hex(self):
		email, lab = "user@example.com", "lab-001"
		expected = hashlib.md5((email + lab).encode()).hexdigest()
		self.assertEqual(get_instance_id(email, lab), expected)
