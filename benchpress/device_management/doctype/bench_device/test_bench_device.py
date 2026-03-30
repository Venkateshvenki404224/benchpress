# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

_WG_SETTINGS = {
	"wg_server_public_key": "server-pub-key==",
	"wg_server_endpoint": "vpn.example.com",
	"wg_server_port": 51820,
}


def _patch_wg(func):
	import functools

	@functools.wraps(func)
	def wrapper(self, *args, **kwargs):
		with (
			patch("benchpress.wg_manager.add_peer_to_server"),
			patch("benchpress.wg_manager.allocate_ip", return_value="10.0.0.5"),
			patch(
				"benchpress.wg_manager.generate_keypair",
				return_value={"private_key": "priv==", "public_key": "pub=="},
			),
			patch("benchpress.wg_manager.generate_peer_config", return_value="[Interface]\n..."),
			patch("benchpress.wg_manager.sync_wg_config"),
		):
			return func(self, *args, **kwargs)

	return wrapper


class IntegrationTestBenchDevice(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", "device-test@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "device-test@example.com",
					"first_name": "Device",
					"last_name": "Tester",
					"send_welcome_email": 0,
					"roles": [{"role": "BenchPress User"}],
				}
			).insert(ignore_permissions=True)
		cls.test_user = "device-test@example.com"

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for d in frappe.get_all("Bench Device", filters={"owner": cls.test_user}, pluck="name"):
			frappe.delete_doc("Bench Device", d, force=True, ignore_permissions=True)
		if frappe.db.exists("User", cls.test_user):
			frappe.delete_doc("User", cls.test_user, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		for d in frappe.get_all("Bench Device", filters={"owner": self.test_user}, pluck="name"):
			frappe.delete_doc("Bench Device", d, force=True, ignore_permissions=True)
		frappe.db.commit()

	def test_register_device_throws_for_invalid_device_type(self):
		from benchpress.device_manager import register_device

		with self.assertRaises(frappe.ValidationError):
			register_device("My PC", "Toaster")

	def test_register_device_throws_when_wg_not_configured(self):
		from benchpress.device_manager import register_device

		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(
				wg_server_public_key=None,
				wg_server_endpoint=None,
			)
			with self.assertRaises(frappe.ValidationError):
				register_device("My PC", "Laptop")

	@_patch_wg
	def test_register_device_creates_bench_device_doc(self):
		from benchpress.device_manager import register_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			result = register_device("My Laptop", "Laptop")

		self.assertIn("name", result)
		self.assertIn("wg_ip", result)
		self.assertIn("wg_config", result)
		self.assertTrue(frappe.db.exists("Bench Device", result["name"]))

	@_patch_wg
	def test_unregister_device_throws_for_non_owner(self):
		from benchpress.device_manager import register_device, unregister_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			result = register_device("Shared Device", "Desktop")

		# Switch to a different user
		frappe.set_user("Administrator")
		# Admin is also admin, so try with a non-admin user
		with patch("benchpress.device_manager.is_admin", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				unregister_device(result["name"])

	@_patch_wg
	def test_unregister_device_succeeds_for_owner(self):
		from benchpress.device_manager import register_device, unregister_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			result = register_device("My Tablet", "Tablet")

		with (
			patch("benchpress.wg_manager.remove_peer_from_server"),
			patch("benchpress.wg_manager.sync_wg_config"),
		):
			unregister_device(result["name"])

		self.assertFalse(frappe.db.exists("Bench Device", result["name"]))

	@_patch_wg
	def test_list_devices_returns_only_current_user_devices(self):
		from benchpress.device_manager import list_devices, register_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			register_device("Device A", "Mobile")

		devices = list_devices()
		self.assertTrue(all(d.get("owner") != "Administrator" for d in devices))
		self.assertEqual(len(devices), 1)
		self.assertEqual(devices[0]["device_name"], "Device A")

	# --- get_device_config ---

	@_patch_wg
	def test_get_device_config_throws_for_non_owner(self):
		from benchpress.device_manager import get_device_config, register_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			result = register_device("IoT Sensor", "IoT")

		frappe.set_user("Administrator")
		with patch("benchpress.device_manager.is_admin", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				get_device_config(result["name"])

	@_patch_wg
	def test_get_device_config_returns_wg_config_for_owner(self):
		from benchpress.device_manager import get_device_config, register_device

		frappe.set_user(self.test_user)
		with patch("benchpress.device_manager.frappe.get_cached_doc") as mock_settings:
			mock_settings.return_value = MagicMock(**_WG_SETTINGS)
			result = register_device("My Server", "Server")

		config = get_device_config(result["name"])
		self.assertIsInstance(config, str)
		self.assertTrue(len(config) > 0)

	def test_get_device_config_throws_when_config_missing(self):
		from benchpress.device_manager import get_device_config

		# Insert a device doc without wg_config
		doc = frappe.get_doc(
			{
				"doctype": "Bench Device",
				"device_name": "No Config Device",
				"device_type": "Embedded",
				"status": "Active",
				"wg_ip": "10.0.0.99",
				"wg_public_key": "no-config-pub==",
				"wg_config": None,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			get_device_config(doc.name)

		frappe.delete_doc("Bench Device", doc.name, force=True, ignore_permissions=True)
