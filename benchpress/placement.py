# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Which bench bridge a new bench prefers.

Advisory only. Placement asks how many endpoints a bridge already holds, which can go
stale between the count and the create; the arbiter is Docker, which refuses the create
when the address pool is empty and lets `docker_manager.start_bench_container` roll on.
Nothing here takes a lock, so it cannot invert the `Bench Instance` -> `Credit Account`
-> `Bench Admission` order `credits/admission.py` depends on.
"""

import docker
import frappe
from frappe import _
from frappe.utils import cint

from benchpress import docker_manager

DEFAULT_BRIDGE_COUNT = 16
DEFAULT_SLOTS_PER_BRIDGE = 1000


def bridge_count() -> int:
	return _setting("bench_bridge_count", DEFAULT_BRIDGE_COUNT)


def slots_per_bridge() -> int:
	return _setting("bench_slots_per_bridge", DEFAULT_SLOTS_PER_BRIDGE)


def _setting(fieldname: str, fallback: int) -> int:
	"""`.get` rather than attribute access: a Single holds only the fields somebody has saved,
	so a knob nobody has touched since the migration is absent, not empty."""
	return cint(frappe.get_cached_doc("BenchPress Settings").get(fieldname)) or fallback


def pick_network() -> str:
	"""The lowest-index bench bridge with room.

	Names a bridge; does not create one. `create_bench_container` ensures whatever
	network it is handed, so a bridge appears when a bench actually reaches it and a
	Draft bench that is never deployed costs nothing.
	"""
	client = docker_manager.get_client()
	cap = slots_per_bridge()
	for index in range(bridge_count()):
		if used_addresses(index, client) < cap:
			return docker_manager.bench_network_spec(index)["name"]
	frappe.throw(
		_("Every bench bridge is full: {0} bridges at {1} benches each.").format(bridge_count(), cap)
	)


def next_network(network: str) -> str:
	"""The bridge after `network`, for a create Docker has already refused."""
	index = docker_manager.bench_network_index(network)
	if index is None:
		index = -1  # a legacy bench has nowhere to advance to but the family's base
	if index + 1 >= bridge_count():
		frappe.throw(
			_("Bench bridge '{0}' is full and it is the last of {1}.").format(network, bridge_count())
		)
	return docker_manager.bench_network_spec(index + 1)["name"]


def used_addresses(index: int, client: docker.DockerClient | None = None) -> int:
	"""Endpoints on bench bridge `index`, infrastructure included; 0 if it does not exist.

	Infrastructure counts because it holds both an address and a bridge port. Three
	endpoints against a cap of a thousand is not worth modelling separately, and
	pretending otherwise is how a soft cap quietly becomes a hard one.
	"""
	network = _network(index, client or docker_manager.get_client())
	return _endpoints(network) if network else 0


def bridge_usage(client: docker.DockerClient | None = None) -> list[dict]:
	"""Used and free slots on every bench bridge that exists, lowest index first."""
	client = client or docker_manager.get_client()
	cap = slots_per_bridge()
	usage = []
	for index in range(bridge_count()):
		network = _network(index, client)
		if network is None:
			continue
		used = _endpoints(network)
		usage.append(
			{
				"network": docker_manager.bench_network_spec(index)["name"],
				"used": used,
				"free": max(cap - used, 0),
			}
		)
	return usage


def headroom(usage: list[dict] | None = None) -> int:
	"""Benches the family could still take, counting bridges that do not exist yet."""
	usage = bridge_usage() if usage is None else usage
	return bridge_count() * slots_per_bridge() - sum(bridge["used"] for bridge in usage)


def _network(index: int, client: docker.DockerClient):
	try:
		return client.networks.get(docker_manager.bench_network_spec(index)["name"])
	except docker.errors.NotFound:
		return None


def _endpoints(network) -> int:
	return len(network.attrs.get("Containers") or {})
