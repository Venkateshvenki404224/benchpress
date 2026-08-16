# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.vpn_adapter import (
	PEER_STATUS_FIELDS,
	get_device_config,
	get_device_peer_status,
	list_devices,
	register_device,
	unregister_device,
)

RECONCILE_HOOK = "vpn_management.vpn_management.doctype.vpn_peer.vpn_peer.VPNPeer._enqueue_reconcile"


def _fake_server():
	return SimpleNamespace(address_cidr="172.27.0.1/16", listen_port=44556)


def _fake_peer(name="PEER-00001", owner_user="Administrator"):
	peer = MagicMock()
	peer.name = name
	peer.owner_user = owner_user
	peer.assigned_ip = "172.27.0.9"
	return peer


def _peer_row(**overrides):
	row = frappe._dict(
		name="PEER-00001",
		peer_name="[Laptop] My Laptop",
		status="Active",
		assigned_ip="172.27.0.9",
		public_key="PUB==",
		rx_bytes=1024,
		tx_bytes=2048,
		last_handshake="2026-08-16 10:00:00",
		creation="2026-08-01 09:30:00",
	)
	row.update(overrides)
	return row


class TestRegisterDevice(IntegrationTestCase):
	def test_rejects_an_unknown_device_type(self):
		with self.assertRaises(frappe.ValidationError):
			register_device("My Toaster", "Toaster")

	@patch("vpn_management.api.client_config._render_client_config", return_value="CONF")
	@patch("benchpress.vpn_adapter.frappe.get_cached_doc", return_value=_fake_server())
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_creates_an_owned_peer_with_the_type_encoded(self, mock_get_doc, _server, _render):
		mock_get_doc.return_value = _fake_peer()

		register_device("My Laptop", "Laptop", "PUB==")

		peer_fields = mock_get_doc.call_args.args[0]
		self.assertEqual(peer_fields["doctype"], "VPN Peer")
		self.assertEqual(peer_fields["peer_name"], "[Laptop] My Laptop")
		self.assertEqual(peer_fields["owner_user"], frappe.session.user)
		self.assertEqual(peer_fields["server"], "wg0")
		self.assertEqual(peer_fields["public_key"], "PUB==")
		# Devices route only the pool, not the peer's full-tunnel default.
		self.assertEqual(peer_fields["client_allowed_ips"], "172.27.0.0/16")
		mock_get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)

	@patch("vpn_management.api.client_config._render_client_config", return_value="CONF")
	@patch("benchpress.vpn_adapter.frappe.get_cached_doc", return_value=_fake_server())
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_returns_the_old_bench_device_reply_shape(self, mock_get_doc, _server, _render):
		mock_get_doc.return_value = _fake_peer()

		result = register_device("My Laptop", "Laptop")

		self.assertEqual(result, {"name": "PEER-00001", "wg_ip": "172.27.0.9", "wg_config": "CONF"})


class TestListDevices(IntegrationTestCase):
	@patch("benchpress.vpn_adapter.frappe.get_all")
	def test_maps_peer_fields_to_the_old_names(self, mock_get_all):
		mock_get_all.side_effect = [[], [_peer_row()]]

		rows = list_devices()

		self.assertEqual(
			rows,
			[
				{
					"name": "PEER-00001",
					"device_name": "My Laptop",
					"device_type": "Laptop",
					"status": "Active",
					"wg_ip": "172.27.0.9",
					"wg_public_key": "PUB==",
					"wg_rx_bytes": 1024,
					"wg_tx_bytes": 2048,
					# Phase 5 needs the handshake; _as_device_row used to drop it.
					"last_handshake": "2026-08-16 10:00:00",
					"registered_on": "2026-08-01 09:30:00",
				}
			],
		)

	@patch("benchpress.vpn_adapter.frappe.get_all")
	def test_scopes_to_the_session_user_and_excludes_bench_peers(self, mock_get_all):
		mock_get_all.side_effect = [["PEER-BENCH"], []]

		list_devices()

		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["owner_user"], frappe.session.user)
		self.assertEqual(filters["name"], ("not in", ["PEER-BENCH"]))

	@patch("benchpress.vpn_adapter.frappe.get_all")
	def test_labels_peers_without_a_type_prefix_generically(self, mock_get_all):
		mock_get_all.side_effect = [[], [_peer_row(peer_name="desk-created-peer")]]

		rows = list_devices()

		self.assertEqual(rows[0]["device_name"], "desk-created-peer")
		self.assertEqual(rows[0]["device_type"], "Device")


class TestDeviceOwnership(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")

	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_non_owner_cannot_fetch_another_users_config(self, mock_get_doc):
		mock_get_doc.return_value = _fake_peer(owner_user="owner@example.com")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			get_device_config("PEER-00001")

	@patch("benchpress.vpn_adapter.frappe.delete_doc")
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_non_owner_cannot_remove_another_users_device(self, mock_get_doc, mock_delete):
		mock_get_doc.return_value = _fake_peer(owner_user="owner@example.com")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			unregister_device("PEER-00001")
		mock_delete.assert_not_called()

	@patch("vpn_management.api.client_config._render_client_config", return_value="CONF")
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_owner_fetches_their_own_config(self, mock_get_doc, _render):
		mock_get_doc.return_value = _fake_peer(owner_user="Guest")
		frappe.set_user("Guest")

		self.assertEqual(get_device_config("PEER-00001"), "CONF")

	@patch("vpn_management.api.client_config._render_client_config", return_value="CONF")
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_admin_may_fetch_any_config(self, mock_get_doc, _render):
		mock_get_doc.return_value = _fake_peer(owner_user="owner@example.com")

		self.assertEqual(get_device_config("PEER-00001"), "CONF")

	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_non_owner_cannot_read_another_users_peer_status(self, mock_get_doc):
		mock_get_doc.return_value = _fake_peer(owner_user="owner@example.com")
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			get_device_peer_status("PEER-00001")


class TestDeviceRoundTrip(IntegrationTestCase):
	"""add → list → remove against real VPN Peer rows (reconcile enqueue stubbed out)."""

	def setUp(self):
		super().setUp()
		self._ensure_endpoint_host_configured()
		self._ensure_wg0_pool_materialized()

	def _ensure_endpoint_host_configured(self):
		"""Config rendering needs a public endpoint host — set on the local stack, empty in CI."""
		if not frappe.db.get_single_value("VPN Settings", "vpn_endpoint_host"):
			frappe.db.set_single_value("VPN Settings", "vpn_endpoint_host", "vpn.test.local")

	def _ensure_wg0_pool_materialized(self):
		"""A bare CI bench has the wg0 server but no pool; the local stack has both."""
		if frappe.db.exists("IP Allocation", {"server": "wg0"}):
			return
		from vpn_management import allocation

		pool = frappe.db.get_value("Network Pool", {"server": "wg0"}, "name")
		if not pool:
			with patch("frappe.enqueue"):
				pool = (
					frappe.get_doc(
						{
							"doctype": "Network Pool",
							"pool_name": "pool-wg0",
							"server": "wg0",
							"cidr": "172.27.0.0/24",
							"gateway_ip": "172.27.0.1",
						}
					)
					.insert(ignore_permissions=True)
					.name
				)
		allocation.materialize(pool)

	@patch(RECONCILE_HOOK)
	def test_add_list_remove_round_trip(self, _reconcile):
		result = register_device("Contract Phone", "Mobile")

		self.assertRegex(result["wg_ip"], r"^172\.27\.")
		self.assertIn("[Interface]", result["wg_config"])
		self.assertIn(f"Address = {result['wg_ip']}/32", result["wg_config"])
		self.assertIn("Endpoint = ", result["wg_config"])
		self.assertIn("AllowedIPs = 172.27.0.0/16", result["wg_config"])

		rows = [row for row in list_devices() if row["name"] == result["name"]]
		self.assertEqual(rows[0]["device_name"], "Contract Phone")
		self.assertEqual(rows[0]["device_type"], "Mobile")
		self.assertEqual(rows[0]["wg_ip"], result["wg_ip"])

		status = get_device_peer_status(result["name"])
		# The owner-scoped status must stay the shape vpn_management's own
		# endpoint returns — that endpoint is gated on VPN DocPerms no
		# BenchPress role holds, so this wrapper is what the SPA reaches.
		from vpn_management.api.peers import get_peer_status

		self.assertEqual(set(status), set(get_peer_status(result["name"])))
		self.assertEqual(set(status), set(PEER_STATUS_FIELDS))
		self.assertEqual(status["assigned_ip"], result["wg_ip"])

		unregister_device(result["name"])

		self.assertFalse(frappe.db.exists("VPN Peer", result["name"]))
		self.assertEqual(frappe.db.count("IP Allocation", {"ip_address": result["wg_ip"], "allocated": 1}), 0)
