# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Pure-function tests for the address set — no container, no database."""

import unittest

from benchpress import addressing


class TestPublicUrls(unittest.TestCase):
	def test_public_site_url_is_none_when_base_domain_unset(self):
		self.assertIsNone(addressing.public_site_url("inst-1", None))
		self.assertIsNone(addressing.public_site_url("inst-1", ""))

	def test_public_site_url_is_none_for_localhost(self):
		self.assertIsNone(addressing.public_site_url("inst-1", "localhost"))

	def test_public_site_url_shape(self):
		self.assertEqual(
			addressing.public_site_url("inst-1", "benchpress.cloud"), "https://inst-1.benchpress.cloud"
		)

	def test_public_ide_url_is_none_when_base_domain_unset(self):
		self.assertIsNone(addressing.public_ide_url("inst-1", None))
		self.assertIsNone(addressing.public_ide_url("inst-1", ""))

	def test_public_ide_url_is_none_for_localhost(self):
		self.assertIsNone(addressing.public_ide_url("inst-1", "localhost"))

	def test_public_ide_url_shape(self):
		self.assertEqual(
			addressing.public_ide_url("inst-1", "benchpress.cloud"), "https://ide-inst-1.benchpress.cloud"
		)


class TestAddressesFor(unittest.TestCase):
	def test_tunnel_only_bench_has_no_public_address(self):
		addresses = addressing.addresses_for({"wg_ip": "172.27.0.2"})

		self.assertIsNone(addresses["public_site"])
		self.assertIsNone(addresses["public_ide"])
		self.assertEqual(addresses["tunnel_site"], "http://172.27.0.2:8000")
		self.assertEqual(addresses["tunnel_ide"], "http://172.27.0.2:8080/")

	def test_bench_with_no_address_at_all(self):
		addresses = addressing.addresses_for({})

		self.assertIsNone(addresses["public_site"])
		self.assertIsNone(addresses["tunnel_site"])
		self.assertIsNone(addresses["tunnel_ide"])
		self.assertEqual(addresses["host_label"], "")

	def test_tunnel_host_prefers_the_wireguard_address(self):
		"""The bridge address is the no-tunnel fallback, so it never wins over `wg_ip`."""
		bench = {"wg_ip": "172.27.0.2", "container_ip": "172.30.0.5"}

		self.assertEqual(addressing._tunnel_host(bench), "172.27.0.2")
		self.assertEqual(addressing._tunnel_host({"container_ip": "172.30.0.5"}), "172.30.0.5")

	def test_stored_addresses_are_carried_through(self):
		addresses = addressing.addresses_for(
			{
				"public_url": "https://inst-1.benchpress.cloud",
				"code_server_url": "https://ide-inst-1.benchpress.cloud",
				"wg_ip": "172.27.0.2",
			}
		)

		self.assertEqual(addresses["public_site"], "https://inst-1.benchpress.cloud")
		self.assertEqual(addresses["public_ide"], "https://ide-inst-1.benchpress.cloud")
		self.assertEqual(addresses["host_label"], "172.27.0.2:8000")
