# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The bench bridge: which one a bench prefers, and how it comes to exist.

Choosing is advisory. Placement asks how many endpoints a bridge already holds, which can
go stale between the count and the create; the arbiter is Docker, which refuses the create
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
DEFAULT_SUBNET_BASE = "10.20"

NETWORK_PREFIX = "benchpress-"
BRIDGE_DEVICE_PREFIX = "bpbr"

# Attached to every bench bridge so Docker's embedded DNS answers in both
# directions. The control plane's own db and redis are deliberately absent: a
# tenant bridge that reaches them is a breach, not a convenience.
INFRASTRUCTURE_CONTAINERS = ("benchpress_traefik", "benchpress-mariadb", "benchpress-redis")


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
			return bench_network_spec(index)["name"]
	frappe.throw(
		_("Every bench bridge is full: {0} bridges at {1} benches each.").format(bridge_count(), cap)
	)


def next_network(network: str) -> str:
	"""The bridge after `network`, for a create Docker has already refused."""
	index = bench_network_index(network)
	if index is None:
		index = -1  # a legacy bench has nowhere to advance to but the family's base
	if index + 1 >= bridge_count():
		frappe.throw(
			_("Bench bridge '{0}' is full and it is the last of {1}.").format(network, bridge_count())
		)
	return bench_network_spec(index + 1)["name"]


def ensure_bench_network(index: int, client: docker.DockerClient | None = None) -> str:
	"""Create bench bridge `index` if absent, attach infrastructure, return its name."""
	client = client or docker_manager.get_client()
	spec = bench_network_spec(index, subnet_base())
	try:
		client.networks.get(spec["name"])
	except docker.errors.NotFound:
		client.networks.create(
			spec["name"],
			driver="bridge",
			ipam=docker.types.IPAMConfig(
				pool_configs=[docker.types.IPAMPool(subnet=spec["subnet"], gateway=spec["gateway"])]
			),
			options={
				# Honoured only at create. A network that already exists without it
				# keeps its br-<hex> device forever, and phase 3's per-device
				# proxy_arp sysctl has no stable path to write.
				"com.docker.network.bridge.name": spec["device"],
				"com.docker.network.bridge.enable_icc": "true",
				"com.docker.network.bridge.enable_ip_masquerade": "true",
			},
		)
	attach_infrastructure(spec["name"], client)
	return spec["name"]


def ensure_bench_network_for(network: str, client: docker.DockerClient | None = None) -> str:
	"""Ensure the network a bench row names, whether legacy or one of the family."""
	client = client or docker_manager.get_client()
	if network == docker_manager.LEGACY_NETWORK:
		docker_manager.ensure_network(client)
		return network
	index = bench_network_index(network)
	if index is None:
		frappe.throw(_("'{0}' is not a BenchPress bench network.").format(network))
	return ensure_bench_network(index, client)


def attach_infrastructure(network: str, client: docker.DockerClient | None = None) -> list[str]:
	"""Connect the three infrastructure containers to `network`; returns those now on it.

	Only INFRASTRUCTURE_CONTAINERS is ever attachable. The tuple is a security
	boundary: an attachment reaches `Network.connect`, and putting the control
	plane's own database on a network tenants share is a breach.
	"""
	client = client or docker_manager.get_client()
	net = client.networks.get(network)
	missing = missing_infrastructure(network, client)
	attached = [name for name in INFRASTRUCTURE_CONTAINERS if name not in missing]
	for name in missing:
		try:
			net.connect(name)
			attached.append(name)
		except docker.errors.NotFound:
			continue  # a dev checkout has no Traefik
		except docker.errors.APIError as e:
			frappe.logger("benchpress").warning(f"could not attach {name} to {network}: {e}")
	return attached


def missing_infrastructure(network: str, client: docker.DockerClient | None = None) -> list[str]:
	"""Infrastructure containers absent from `network`; empty when the bridge does not exist."""
	client = client or docker_manager.get_client()
	try:
		net = client.networks.get(network)
	except docker.errors.NotFound:
		return []
	present = {c.get("Name") for c in net.attrs.get("Containers", {}).values()}
	return [name for name in INFRASTRUCTURE_CONTAINERS if name not in present]


def repair() -> dict[str, dict[str, list[str]]]:
	"""Put the three infrastructure containers back on every bench bridge that lost one.

	`docker compose up -d traefik` recreates the proxy holding only its compose networks, so
	every bridge this app made itself silently loses its ingress and the benches on it start
	answering 502. Reattaching is hot, which is the whole reason this belongs on the pass
	that already runs `*/5` rather than in a restart nobody wants to schedule.

	A bridge that does not exist reports nothing missing, so the pass never grows the family
	on a timer; only a deploy does that.

	Reports both halves: `missing` is what the read found before the write, `attached` is what
	the write put back. A bridge in the first and not the second could not be repaired, and
	without the split it reports exactly what a healthy bridge reports.
	"""
	missing_by_network = {}
	restored = {}
	for index in range(bridge_count()):
		network = bench_network_spec(index)["name"]
		missing = missing_infrastructure(network)
		if not missing:
			continue
		missing_by_network[network] = missing
		now_on = attach_infrastructure(network)
		reattached = [name for name in missing if name in now_on]
		if reattached:
			restored[network] = reattached
	if restored:
		frappe.logger("benchpress").info(f"reattached infrastructure: {restored}")
	return {"attached": restored, "missing": missing_by_network}


def record_bridge_network(bench, network: str) -> None:
	"""Stamp the bridge onto the row, around the refusal that guards the field.

	`Bench Instance.validate` refuses a `bridge_network` change to anyone but an admin and to
	anything but a `Draft` — and a deploy job runs as the tenant and has to write one more
	time after the container exists. Writing the column directly is the honest way through:
	this is the system recording where Docker put the container, not a caller choosing.
	"""
	if bench.bridge_network == network:
		return
	frappe.db.set_value("Bench Instance", bench.name, "bridge_network", network, update_modified=False)
	bench.bridge_network = network


def bench_network_spec(index: int, base: str | None = None) -> dict:
	"""Name, bridge device, subnet and gateway for one bench bridge.

	`index * 16` in the third octet starts every /20 on its own boundary, so a later
	per-node /16 scheme renumbers nothing.
	"""
	base = base or DEFAULT_SUBNET_BASE
	octet = index * 16
	return {
		"name": f"{NETWORK_PREFIX}{index}",
		"device": f"{BRIDGE_DEVICE_PREFIX}{index}",
		"subnet": f"{base}.{octet}.0/20",
		"gateway": f"{base}.{octet}.1",
	}


def bench_network_index(network: str) -> int | None:
	"""The family index a network name encodes, or None if the name is not one of ours."""
	if not network.startswith(NETWORK_PREFIX):
		return None
	suffix = network[len(NETWORK_PREFIX) :]
	return int(suffix) if suffix.isdigit() else None


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
				"network": bench_network_spec(index)["name"],
				"used": used,
				"free": max(cap - used, 0),
			}
		)
	return usage


def headroom(usage: list[dict] | None = None) -> int:
	"""Benches the family could still take, counting bridges that do not exist yet."""
	usage = bridge_usage() if usage is None else usage
	return bridge_count() * slots_per_bridge() - sum(bridge["used"] for bridge in usage)


def used_addresses(index: int, client: docker.DockerClient | None = None) -> int:
	"""Endpoints on bench bridge `index`, infrastructure included; 0 if it does not exist.

	Infrastructure counts because it holds both an address and a bridge port. Three
	endpoints against a cap of a thousand is not worth modelling separately, and
	pretending otherwise is how a soft cap quietly becomes a hard one.
	"""
	network = _network(index, client or docker_manager.get_client())
	return _endpoints(network) if network else 0


def slots_per_bridge() -> int:
	return _setting("bench_slots_per_bridge", DEFAULT_SLOTS_PER_BRIDGE)


def bridge_count() -> int:
	return _setting("bench_bridge_count", DEFAULT_BRIDGE_COUNT)


def subnet_base() -> str:
	return frappe.get_cached_doc("BenchPress Settings").bench_subnet_base or DEFAULT_SUBNET_BASE


def _setting(fieldname: str, fallback: int) -> int:
	"""`.get` rather than attribute access: a Single holds only the fields somebody has saved,
	so a knob nobody has touched since the migration is absent, not empty."""
	return cint(frappe.get_cached_doc("BenchPress Settings").get(fieldname)) or fallback


def _network(index: int, client: docker.DockerClient):
	try:
		return client.networks.get(bench_network_spec(index)["name"])
	except docker.errors.NotFound:
		return None


def _endpoints(network) -> int:
	return len(network.attrs.get("Containers") or {})
