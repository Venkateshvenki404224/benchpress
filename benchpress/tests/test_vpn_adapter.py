# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests import IntegrationTestCase

from benchpress.vpn_adapter import configure_container, create_container_peer, render_container_config


def _fake_server():
	return SimpleNamespace(
		address_cidr="172.27.0.1/16",
		listen_port=44556,
		server_public_key="SERVERPUB==",
	)


def _fake_peer(name="PEER-00001", assigned_ip="172.27.0.2"):
	peer = MagicMock()
	peer.name = name
	peer.assigned_ip = assigned_ip
	return peer


class TestCreateContainerPeer(IntegrationTestCase):
	@patch("vpn_management.tasks.reconcile_interface")
	@patch("vpn_management.crypto.generate_keypair", return_value=("PRIV==", "PUB=="))
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_registers_public_key_and_returns_claimed_ip(self, mock_get_doc, _keygen, mock_reconcile):
		mock_get_doc.return_value = _fake_peer()
		bench = SimpleNamespace(name="BENCH-0001", bench_name="my-bench", owner="user@example.com")

		result = create_container_peer(bench)

		peer_fields = mock_get_doc.call_args.args[0]
		self.assertEqual(peer_fields["doctype"], "VPN Peer")
		self.assertEqual(peer_fields["peer_name"], "my-bench")
		self.assertEqual(peer_fields["owner_user"], "user@example.com")
		self.assertEqual(peer_fields["public_key"], "PUB==")
		self.assertEqual(result["assigned_ip"], "172.27.0.2")
		self.assertEqual(result["private_key"], "PRIV==")
		mock_reconcile.assert_called_once_with("wg0")

	@patch("vpn_management.tasks.reconcile_interface")
	@patch("vpn_management.crypto.generate_keypair", return_value=("PRIV==", "PUB=="))
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_never_persists_the_private_key(self, mock_get_doc, _keygen, _reconcile):
		mock_get_doc.return_value = _fake_peer()
		bench = SimpleNamespace(name="BENCH-0001", bench_name="my-bench", owner="user@example.com")

		create_container_peer(bench)

		peer_fields = mock_get_doc.call_args.args[0]
		self.assertNotIn("private_key", peer_fields)
		self.assertNotIn("PRIV==", str(peer_fields))

	@patch("vpn_management.tasks.reconcile_interface")
	@patch("vpn_management.crypto.generate_keypair", return_value=("PRIV==", "PUB=="))
	@patch("benchpress.vpn_adapter.frappe.get_doc")
	def test_reconciles_after_the_ip_is_claimed(self, mock_get_doc, _keygen, mock_reconcile):
		flow = MagicMock()
		peer = _fake_peer()
		mock_get_doc.return_value = peer
		flow.attach_mock(peer.insert, "insert")
		flow.attach_mock(mock_reconcile, "reconcile")
		bench = SimpleNamespace(name="BENCH-0001", bench_name=None, owner="user@example.com")

		create_container_peer(bench)

		peer.insert.assert_called_once_with(ignore_permissions=True)
		# The insert (atomic IP claim) must precede the interface converge.
		call_order = [name for name, _args, _kwargs in flow.mock_calls]
		self.assertEqual(call_order, ["insert", "reconcile"])


class TestRenderContainerConfig(IntegrationTestCase):
	@patch("benchpress.vpn_adapter._get_docker_gateway", return_value="172.30.0.1")
	@patch("benchpress.vpn_adapter.frappe.get_cached_doc", return_value=_fake_server())
	def test_renders_the_container_client_conf(self, _server, _gateway):
		config = render_container_config("PRIV==", "172.27.0.5")

		self.assertIn("PrivateKey = PRIV==", config)
		self.assertIn("Address = 172.27.0.5/32", config)
		self.assertIn("PublicKey = SERVERPUB==", config)
		# AllowedIPs is the pool network, normalized from the server's host CIDR.
		self.assertIn("AllowedIPs = 172.27.0.0/16", config)
		# Containers reach wg0 through the Docker gateway, not the public endpoint.
		self.assertIn("Endpoint = 172.30.0.1:44556", config)
		self.assertIn("PersistentKeepalive = 25", config)


class TestConfigureContainer(IntegrationTestCase):
	@patch("benchpress.vpn_adapter.render_container_config", return_value="CONF")
	@patch("benchpress.docker_manager.exec_in_container", return_value=(0, ""))
	@patch("benchpress.docker_manager.write_file_to_container")
	def test_writes_conf_and_brings_tunnel_up(self, mock_write, mock_exec, _render):
		configure_container("cid123", "PRIV==", "172.27.0.5")

		mock_write.assert_called_once_with("cid123", "CONF", "/etc/wireguard/wg0.conf")
		commands = [call.args[1] for call in mock_exec.call_args_list]
		self.assertIn("chmod 600 /etc/wireguard/wg0.conf", commands)
		self.assertIn("wg-quick up wg0", commands)

	@patch("benchpress.vpn_adapter.render_container_config", return_value="CONF")
	@patch("benchpress.docker_manager.exec_in_container")
	@patch("benchpress.docker_manager.write_file_to_container")
	def test_raises_when_wg_quick_fails(self, _write, mock_exec, _render):
		mock_exec.side_effect = [(0, ""), (1, "wg-quick: boom")]

		with self.assertRaises(Exception) as caught:
			configure_container("cid123", "PRIV==", "172.27.0.5")

		self.assertIn("wg-quick up failed", str(caught.exception))
