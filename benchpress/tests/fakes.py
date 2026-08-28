# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""One stateful in-memory Docker, installed at `docker_manager.get_client`.

Tests read state (`self.docker.created[-1]`) rather than mock call records.
"""

import base64
from unittest.mock import patch

import docker

from benchpress import diagnostics, docker_manager, mariadb_manager
from benchpress.request_cache import clear_local_cache

# The modules that bind `get_client` at import instead of reaching it through
# `docker_manager`, so `patch.object(docker_manager, ...)` alone misses them.
# `test_fakes.TestGetClientImporters` re-derives this from source: a new
# module-level import fails a test rather than reaching a real daemon.
GET_CLIENT_MODULES = (docker_manager, mariadb_manager, diagnostics)

DEFAULT_BLOCK_DEVICES = ["/dev/sda"]
DEFAULT_INFO = {"Runtimes": {"runc": {}, "sysbox-runc": {}}, "DefaultRuntime": "runc"}
DEFAULT_STATS = {
	"cpu_stats": {
		"cpu_usage": {"total_usage": 200_000_000},
		"system_cpu_usage": 4_000_000_000,
		"online_cpus": 2,
	},
	"precpu_stats": {"cpu_usage": {"total_usage": 100_000_000}, "system_cpu_usage": 2_000_000_000},
	"memory_stats": {"usage": 128 * 1024 * 1024, "limit": 512 * 1024 * 1024},
}


class UnscriptedExec(AssertionError):
	"""A strict FakeDocker was asked to run a command no test registered."""


def _command_text(cmd) -> str:
	return " ".join(cmd) if isinstance(cmd, list | tuple) else str(cmd)


def sql_of(exec_command: str) -> str:
	"""The SQL inside an `execute_sql` exec, which travels base64 so nothing is shell-interpolated."""
	return base64.b64decode(exec_command.split("'")[1]).decode()


class FakeContainer:
	def __init__(self, client, container_id, name, labels, network, runtime, ip, status="created"):
		self.client = client
		self.id = container_id
		self.name = name
		self.labels = labels or {}
		self.status = status
		self.health = ""
		self.stats_response = dict(DEFAULT_STATS)
		self.execs: list[str] = []
		self.start_refusal = ""
		self.stop_refusal = ""
		self.remove_refusal = ""
		self.archives: dict[str, bytes] = {}
		self.attrs = {
			"HostConfig": {"Runtime": runtime or "runc", "NetworkMode": network},
			"NetworkSettings": {"Networks": {network: {"IPAddress": ip}}, "IPAddress": ip},
			"State": {"Health": {"Status": self.health}},
		}

	def exec_run(self, cmd=None, **kwargs):
		self.execs.append(_command_text(cmd))
		return self.client._run_exec(cmd)

	def start(self, **kwargs):
		if self.start_refusal:
			raise docker.errors.APIError(self.start_refusal)
		self.status = "running"

	def stop(self, **kwargs):
		if self.stop_refusal:
			raise docker.errors.APIError(self.stop_refusal)
		self.client.stopped.append(self.name)
		self.status = "exited"

	def restart(self, **kwargs):
		self.status = "running"

	def remove(self, **kwargs):
		if self.remove_refusal:
			raise docker.errors.APIError(self.remove_refusal)
		self.client.removed.append(self.name)
		self.client._store.pop(self.id, None)

	def reload(self):
		self.attrs["State"]["Health"]["Status"] = self.health

	def logs(self, **kwargs):
		return b""

	def stats(self, stream=False, **kwargs):
		return self.stats_response

	def get_archive(self, path, **kwargs):
		data = self.archives.get(path, b"")
		return iter([data]), {"name": path, "size": len(data)}

	def put_archive(self, path, data):
		self.client.archives_put.append((path, data))
		return True


class FakeNetwork:
	def __init__(self, client, name, **kwargs):
		self.client = client
		self.name = name
		self.kwargs = kwargs
		self.attrs = {"Name": name, "Containers": {}}

	def connect(self, container, **kwargs):
		name = getattr(container, "name", container)
		if name not in self.client._by_name:
			raise docker.errors.NotFound(f"no such container: {name}")
		found = self.client._by_name[name]
		self.attrs["Containers"][found.id] = {"Name": name}


class FakeVolume:
	def __init__(self, name):
		self.name = name
		self.attrs = {"Name": name}


class _Containers:
	def __init__(self, client):
		self.client = client

	def get(self, key):
		container = self.client._store.get(key) or self.client._by_name.get(key)
		if container is None:
			raise docker.errors.NotFound(f"no such container: {key}")
		return container

	def create(self, **kwargs):
		self.client.created.append(kwargs)
		return self.client._add(kwargs)

	def run(self, image=None, command=None, **kwargs):
		container = self.create(image=image, command=command, **kwargs)
		container.start()
		if kwargs.get("remove"):
			container.remove()
		return container

	def list(self, all=False, filters=None):
		found = list(self.client._store.values())
		if not all:
			found = [c for c in found if c.status == "running"]
		for key, value in (filters or {}).items():
			found = [c for c in found if _matches(c, key, value)]
		return found


class _Networks:
	def __init__(self, client):
		self.client = client

	def get(self, name):
		network = self.client._networks.get(name)
		if network is None:
			raise docker.errors.NotFound(f"no such network: {name}")
		return network

	def create(self, name, **kwargs):
		network = FakeNetwork(self.client, name, **kwargs)
		self.client._networks[name] = network
		return network


class _Volumes:
	def __init__(self, client):
		self.client = client

	def get(self, name):
		self.client.volume_gets.append(name)
		volume = self.client._volumes.get(name)
		if volume is None:
			raise docker.errors.NotFound(f"no such volume: {name}")
		return volume

	def create(self, name=None, **kwargs):
		volume = FakeVolume(name)
		self.client._volumes[name] = volume
		return volume


class _Images:
	def __init__(self, client):
		self.client = client

	def remove(self, tag, **kwargs):
		self.client.images_removed.append(tag)


def _matches(container, key, value) -> bool:
	if key == "label":
		wanted = value if isinstance(value, list) else [value]
		return all(_has_label(container, term) for term in wanted)
	if key == "status":
		return container.status == value
	if key == "name":
		return value in container.name
	raise AssertionError(f"FakeDocker does not filter on {key!r}")


def _has_label(container, term: str) -> bool:
	name, _, value = term.partition("=")
	if not value:
		return name in container.labels
	return container.labels.get(name) == value


class FakeDocker:
	def __init__(self, *, strict: bool = False):
		self.strict = strict
		self.containers = _Containers(self)
		self.networks = _Networks(self)
		self.volumes = _Volumes(self)
		self.images = _Images(self)
		self.created: list[dict] = []
		self.execs: list[str] = []
		self.stopped: list[str] = []
		self.removed: list[str] = []
		self.volume_gets: list[str] = []
		self.images_removed: list[str] = []
		self.archives_put: list[tuple[str, bytes]] = []
		self.info_response = dict(DEFAULT_INFO)
		self._scripted: list[tuple[str, tuple[int, bytes]]] = []
		self._start_refusals: dict[str, str] = {}
		self._store: dict[str, FakeContainer] = {}
		self._networks: dict[str, FakeNetwork] = {}
		self._volumes: dict[str, FakeVolume] = {}
		self._next_id = 0

	def info(self):
		return self.info_response

	def script_exec(self, substring: str, result: tuple[int, bytes]) -> None:
		"""Answer any exec whose command contains `substring` with `result`."""
		self._scripted.append((substring, result))

	def refuse_start(self, name: str, message: str) -> None:
		"""Make this container's `start()` raise `APIError`, the way a daemon refusing one does."""
		self._start_refusals[name] = message

	def add_container(self, name, *, labels=None, status="running", health="", network="benchpress"):
		"""Seed a container the app did not create, for `containers.get` and `list`."""
		return self._add(
			{"name": name, "labels": labels, "network": network},
			status=status,
			health=health,
		)

	def _add(self, kwargs, status="created", health=""):
		self._next_id += 1
		container_id = f"fake{self._next_id:04d}"
		network = kwargs.get("network") or docker_manager.LEGACY_NETWORK
		container = FakeContainer(
			self,
			container_id,
			kwargs.get("name") or container_id,
			kwargs.get("labels"),
			network,
			kwargs.get("runtime"),
			f"172.30.0.{self._next_id % 250 + 2}",
			status=status,
		)
		container.health = health
		container.start_refusal = self._start_refusals.get(container.name, "")
		self._store[container_id] = container
		return container

	@property
	def _by_name(self) -> dict[str, FakeContainer]:
		return {c.name: c for c in self._store.values()}

	def _run_exec(self, cmd) -> tuple[int, bytes]:
		command = _command_text(cmd)
		self.execs.append(command)
		for substring, result in self._scripted:
			if substring in command:
				return result
		if self.strict:
			raise UnscriptedExec(f"unscripted exec: {command}")
		return 0, b""


class FakeDockerMixin:
	"""Installs a `FakeDocker` at every `get_client` binding, plus the two host reads."""

	docker_strict = False

	def setUp(self):
		super().setUp()
		self.docker = FakeDocker(strict=self.docker_strict)
		for module in GET_CLIENT_MODULES:
			self._install(module, "get_client", self.docker)
		# `host_runtimes` memoises on `frappe.local`, which outlives a test, so a real daemon
		# read taken earlier in the run would otherwise survive the fake.
		clear_local_cache(docker_manager.HOST_RUNTIMES_ATTRIBUTE)
		self.addCleanup(clear_local_cache, docker_manager.HOST_RUNTIMES_ATTRIBUTE)
		self.host_block_devices = self._install(
			docker_manager, "_get_host_block_devices", list(DEFAULT_BLOCK_DEVICES)
		)
		self.compose_cmd = self._install(mariadb_manager, "_compose_cmd", (0, ""))

	def _install(self, module, attribute, return_value):
		patcher = patch.object(module, attribute, return_value=return_value)
		mock = patcher.start()
		self.addCleanup(patcher.stop)
		return mock
