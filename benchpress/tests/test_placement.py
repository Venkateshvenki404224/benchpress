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


def _network(endpoints: int):
	network = MagicMock()
	network.attrs = {"Containers": {f"c{i}": {"Name": f"c{i}"} for i in range(endpoints)}}
	return network


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
			docker_manager.INFRASTRUCTURE_CONTAINERS,
			("benchpress_traefik", "benchpress-mariadb", "benchpress-redis"),
		)

	def test_the_control_plane_is_never_attachable(self):
		for name in ("benchpress_db", "benchpress_redis-cache", "benchpress_redis-queue"):
			self.assertNotIn(name, docker_manager.INFRASTRUCTURE_CONTAINERS)
