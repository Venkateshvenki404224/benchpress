# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Which bridge a bench prefers, and the one tuple that is allowed to reach a bench bridge."""

import unittest
from unittest.mock import MagicMock, patch

import docker
import frappe

from benchpress import docker_manager, placement

BRIDGE_COUNT = 3
SLOTS = 10


def _network_holding(*container_names):
	network = MagicMock()
	network.attrs = {"Containers": {f"cid{i}": {"Name": n} for i, n in enumerate(container_names)}}
	return network


def _network(endpoints: int):
	return _network_holding(*(f"c{i}" for i in range(endpoints)))


def _client(sizes: dict[str, int]):
	"""A Docker client whose bench bridges hold the given endpoint counts; the rest are absent."""
	client = MagicMock()

	def get(name):
		if name not in sizes:
			raise docker.errors.NotFound(name)
		return _network(sizes[name])

	client.networks.get.side_effect = get
	return client


class PlacementTestCase(unittest.TestCase):
	def _pick(self, sizes: dict[str, int], count=BRIDGE_COUNT, slots=SLOTS):
		with (
			patch("benchpress.docker_manager.get_client", return_value=_client(sizes)),
			patch("benchpress.placement.bridge_count", return_value=count),
			patch("benchpress.placement.slots_per_bridge", return_value=slots),
		):
			return placement.pick_network()

	def _usage(self, sizes: dict[str, int], count=BRIDGE_COUNT, slots=SLOTS):
		with (
			patch("benchpress.docker_manager.get_client", return_value=_client(sizes)),
			patch("benchpress.placement.bridge_count", return_value=count),
			patch("benchpress.placement.slots_per_bridge", return_value=slots),
		):
			return placement.bridge_usage()


class TestPickNetwork(PlacementTestCase):
	def test_a_family_with_no_bridge_yet_prefers_index_zero(self):
		"""A missing bridge is empty, not unusable — that is what makes creation lazy."""
		self.assertEqual(self._pick({}), "benchpress-0")

	def test_the_lowest_bridge_with_room_wins(self):
		self.assertEqual(self._pick({"benchpress-0": 3}), "benchpress-0")

	def test_a_full_bridge_is_skipped(self):
		self.assertEqual(self._pick({"benchpress-0": SLOTS}), "benchpress-1")

	def test_the_next_bridge_need_not_exist(self):
		self.assertEqual(self._pick({"benchpress-0": SLOTS, "benchpress-1": SLOTS}), "benchpress-2")

	def test_infrastructure_counts_against_the_cap(self):
		"""Three endpoints hold three addresses and three bridge ports like any other."""
		self.assertEqual(self._pick({"benchpress-0": SLOTS - 3}), "benchpress-0")
		self.assertEqual(self._pick({"benchpress-0": SLOTS - 2}), "benchpress-0")

	def test_a_full_family_is_refused_with_a_sentence(self):
		full = {f"benchpress-{i}": SLOTS for i in range(BRIDGE_COUNT)}
		with self.assertRaises(frappe.ValidationError) as refusal:
			self._pick(full)
		self.assertIn(str(BRIDGE_COUNT), str(refusal.exception))
		self.assertIn(str(SLOTS), str(refusal.exception))


class TestNextNetwork(PlacementTestCase):
	def _next(self, network, count=BRIDGE_COUNT):
		with patch("benchpress.placement.bridge_count", return_value=count):
			return placement.next_network(network)

	def test_a_refused_bridge_rolls_to_the_one_after_it(self):
		self.assertEqual(self._next("benchpress-0"), "benchpress-1")

	def test_a_legacy_bench_rolls_into_the_base_of_the_family(self):
		self.assertEqual(self._next(docker_manager.LEGACY_NETWORK), "benchpress-0")

	def test_the_last_bridge_has_nowhere_to_roll(self):
		with self.assertRaises(frappe.ValidationError) as refusal:
			self._next(f"benchpress-{BRIDGE_COUNT - 1}")
		self.assertIn(f"benchpress-{BRIDGE_COUNT - 1}", str(refusal.exception))


class TestBridgeUsage(PlacementTestCase):
	def test_only_bridges_that_exist_are_reported(self):
		usage = self._usage({"benchpress-0": 4, "benchpress-2": 1})
		self.assertEqual([row["network"] for row in usage], ["benchpress-0", "benchpress-2"])

	def test_used_and_free_add_up_to_the_cap(self):
		[row] = self._usage({"benchpress-0": 4})
		self.assertEqual((row["used"], row["free"]), (4, SLOTS - 4))

	def test_an_overfull_bridge_reports_no_free_slots_rather_than_a_negative(self):
		[row] = self._usage({"benchpress-0": SLOTS + 2})
		self.assertEqual(row["free"], 0)

	def test_headroom_counts_the_bridges_that_do_not_exist_yet(self):
		usage = self._usage({"benchpress-0": 4})
		with (
			patch("benchpress.placement.bridge_count", return_value=BRIDGE_COUNT),
			patch("benchpress.placement.slots_per_bridge", return_value=SLOTS),
		):
			self.assertEqual(placement.headroom(usage), BRIDGE_COUNT * SLOTS - 4)


class TestInfrastructureIsolation(unittest.TestCase):
	"""The tuple that decides what may reach a tenant bridge.

	labs-devops swept its control-plane database onto all sixteen tenant bridges and did not
	notice for 107 days. Adding a fourth name here has to be a deliberate act with a failing
	test in front of it.
	"""

	def test_exactly_the_three_infrastructure_containers_are_attachable(self):
		self.assertEqual(
			placement.INFRASTRUCTURE_CONTAINERS,
			("benchpress_traefik", "benchpress-mariadb", "benchpress-redis"),
		)

	def test_the_control_plane_is_never_attachable(self):
		for name in ("benchpress_db", "benchpress_redis-cache", "benchpress_redis-queue"):
			self.assertNotIn(name, placement.INFRASTRUCTURE_CONTAINERS)


class TestBenchNetworkSpec(unittest.TestCase):
	def test_index_zero_is_the_base_of_the_family(self):
		spec = placement.bench_network_spec(0, "10.20")

		self.assertEqual(spec["name"], "benchpress-0")
		self.assertEqual(spec["device"], "bpbr0")
		self.assertEqual(spec["subnet"], "10.20.0.0/20")
		self.assertEqual(spec["gateway"], "10.20.0.1")

	def test_each_index_starts_on_its_own_slash_20_boundary(self):
		"""A /20 spans 16 third octets, so overlapping ones would share addresses."""
		subnets = [placement.bench_network_spec(i, "10.20")["subnet"] for i in range(4)]

		self.assertEqual(subnets, ["10.20.0.0/20", "10.20.16.0/20", "10.20.32.0/20", "10.20.48.0/20"])

	def test_the_device_name_fits_ifnamsiz(self):
		self.assertLess(len(placement.bench_network_spec(15, "10.20")["device"]), 16)

	def test_a_subnet_base_moves_only_the_addresses(self):
		spec = placement.bench_network_spec(1, "10.40")

		self.assertEqual(spec["name"], "benchpress-1")
		self.assertEqual(spec["subnet"], "10.40.16.0/20")

	def test_index_round_trips_through_the_name(self):
		for index in (0, 1, 7):
			name = placement.bench_network_spec(index)["name"]
			self.assertEqual(placement.bench_network_index(name), index)

	def test_a_foreign_name_has_no_index(self):
		for name in ("benchpress", "benchpress_frappe_network", "benchpress-labs", "bridge"):
			self.assertIsNone(placement.bench_network_index(name))


class TestAttachInfrastructure(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_attaches_exactly_the_three_infrastructure_containers(self, get_client):
		network = _network_holding()
		get_client.return_value.networks.get.return_value = network

		attached = placement.attach_infrastructure("benchpress-0")

		self.assertEqual(attached, list(placement.INFRASTRUCTURE_CONTAINERS))
		self.assertEqual(
			[call.args[0] for call in network.connect.call_args_list],
			list(placement.INFRASTRUCTURE_CONTAINERS),
		)

	@patch("benchpress.docker_manager.get_client")
	def test_the_control_plane_is_never_attached(self, get_client):
		"""A tenant bridge that reaches the control plane's own database is a breach."""
		network = _network_holding()
		get_client.return_value.networks.get.return_value = network

		placement.attach_infrastructure("benchpress-0")

		connected = {call.args[0] for call in network.connect.call_args_list}
		self.assertTrue(
			connected.isdisjoint({"benchpress_db", "benchpress_redis-cache", "benchpress_redis-queue"})
		)

	@patch("benchpress.docker_manager.get_client")
	def test_an_already_connected_container_is_not_reconnected(self, get_client):
		network = _network_holding("benchpress_traefik")
		get_client.return_value.networks.get.return_value = network

		attached = placement.attach_infrastructure("benchpress-0")

		self.assertIn("benchpress_traefik", attached)
		self.assertNotIn("benchpress_traefik", [call.args[0] for call in network.connect.call_args_list])

	@patch("benchpress.docker_manager.get_client")
	def test_a_missing_container_is_skipped(self, get_client):
		"""A dev checkout has no Traefik, and the deploy must still complete."""
		network = _network_holding()
		network.connect.side_effect = [docker.errors.NotFound("no such container"), None, None]
		get_client.return_value.networks.get.return_value = network

		attached = placement.attach_infrastructure("benchpress-0")

		self.assertEqual(attached, ["benchpress-mariadb", "benchpress-redis"])


class TestEnsureBenchNetwork(unittest.TestCase):
	def _client_without(self, network_name):
		client = MagicMock()

		def get(name):
			if name == network_name:
				raise docker.errors.NotFound(name)
			return _network_holding()

		client.networks.get.side_effect = get
		return client

	@patch("benchpress.placement.subnet_base", return_value="10.20")
	@patch("benchpress.placement.attach_infrastructure")
	@patch("benchpress.docker_manager.get_client")
	def test_creates_the_bridge_with_a_pinned_device(self, get_client, _attach, _base):
		"""The device option is honoured only at create; a later one keeps br-<hex>."""
		client = self._client_without("benchpress-0")
		get_client.return_value = client

		placement.ensure_bench_network(0)

		kwargs = client.networks.create.call_args.kwargs
		self.assertEqual(kwargs["options"]["com.docker.network.bridge.name"], "bpbr0")
		pool = kwargs["ipam"]["Config"][0]
		self.assertEqual(pool["Subnet"], "10.20.0.0/20")
		self.assertEqual(pool["Gateway"], "10.20.0.1")

	@patch("benchpress.placement.subnet_base", return_value="10.20")
	@patch("benchpress.placement.attach_infrastructure")
	@patch("benchpress.docker_manager.get_client")
	def test_an_existing_bridge_is_not_recreated_but_is_reattached(self, get_client, attach, _base):
		client = MagicMock()
		client.networks.get.return_value = _network_holding()
		get_client.return_value = client

		self.assertEqual(placement.ensure_bench_network(0), "benchpress-0")

		client.networks.create.assert_not_called()
		attach.assert_called_once_with("benchpress-0", client)

	@patch("benchpress.docker_manager.ensure_network")
	@patch("benchpress.docker_manager.get_client")
	def test_the_legacy_name_ensures_the_legacy_network(self, get_client, ensure_network):
		"""Benches that predate the family stay where their containers already are."""
		self.assertEqual(placement.ensure_bench_network_for("benchpress"), "benchpress")

		ensure_network.assert_called_once()

	@patch("benchpress.docker_manager.get_client")
	def test_a_network_outside_the_family_is_refused(self, get_client):
		with self.assertRaises(frappe.ValidationError):
			placement.ensure_bench_network_for("benchpress_frappe_network")
