# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import types
import unittest
from unittest.mock import MagicMock, patch

import docker
import frappe
from frappe.tests import IntegrationTestCase

import benchpress.docker_manager as docker_manager
from benchpress.docker_manager import (
	DEFAULT_BPS,
	DEFAULT_IOPS,
	DEFAULT_PIDS_LIMIT,
	HOST_RUNTIMES_ATTRIBUTE,
	container_runtime,
	get_container_health,
	host_runtimes,
	preflight_runtime,
	wait_for_container_running,
)
from benchpress.request_cache import clear_local_cache


def _client_returning(status):
	client = MagicMock()
	client.containers.get.return_value.status = status
	return client


class TestContainerHealth(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_running_container_is_healthy(self, get_client):
		get_client.return_value = _client_returning("running")
		self.assertEqual(get_container_health("abc123"), "Healthy")

	@patch("benchpress.docker_manager.get_client")
	def test_exited_container_is_unhealthy(self, get_client):
		get_client.return_value = _client_returning("exited")
		self.assertEqual(get_container_health("abc123"), "Unhealthy")

	@patch("benchpress.docker_manager.get_client")
	def test_missing_container_is_unknown(self, get_client):
		client = MagicMock()
		client.containers.get.side_effect = docker.errors.NotFound("no such container")
		get_client.return_value = client
		self.assertEqual(get_container_health("gone"), "Unknown")


def _reloading_container(states):
	"""Container mock whose reload() steps through (status, attrs) states."""
	container = MagicMock()
	steps = iter(states)

	def advance():
		container.status, container.attrs = next(steps)

	container.reload.side_effect = advance
	return container


IP_ATTRS = {"NetworkSettings": {"Networks": {"benchpress": {"IPAddress": "172.30.0.5"}}}}
NO_IP_ATTRS = {"NetworkSettings": {"Networks": {"benchpress": {"IPAddress": ""}}}}


def exec_commands(container):
	"""Every command a mocked container was asked to exec, as text."""
	return [" ".join(call.kwargs["cmd"]) for call in container.exec_run.call_args_list]


def exec_environments(container):
	"""Every environment a mocked container's execs carried."""
	return [call.kwargs.get("environment") or {} for call in container.exec_run.call_args_list]


class TestWriteFileToContainer(unittest.TestCase):
	"""Docker publishes an exec's command line and not its environment, so the file rides in the environment."""

	def _container(self, result=(0, b"")):
		client = MagicMock()
		container = client.containers.get.return_value
		container.exec_run.return_value = result
		return client, container

	@patch("benchpress.docker_manager.get_client")
	def test_the_content_goes_into_the_environment_and_into_no_command(self, get_client):
		sentinel = "sB1XnOtAr3alPr1vat3K3y="
		client, container = self._container()
		get_client.return_value = client

		docker_manager.write_file_to_container("cid", f"PrivateKey = {sentinel}\n", "/etc/wireguard/wg0.conf")

		environment = exec_environments(container)[0]
		self.assertIn(sentinel, environment[docker_manager.FILE_CONTENT_VAR])
		for command in exec_commands(container):
			self.assertNotIn(sentinel, command)

	@patch("benchpress.docker_manager.get_client")
	def test_a_mode_is_applied_in_the_same_exec(self, get_client):
		"""The caller's second exec to repair the mode is what this replaces."""
		client, container = self._container()
		get_client.return_value = client

		docker_manager.write_file_to_container("cid", "conf", "/etc/wireguard/wg0.conf", mode=0o600)

		self.assertIn("chmod 600 /etc/wireguard/wg0.conf", exec_commands(container)[0])

	@patch("benchpress.docker_manager.get_client")
	def test_no_mode_leaves_an_existing_file_the_mode_it_had(self, get_client):
		"""`common_site_config.json` and `linkuser.sh` ship in the image already; a
		default here would silently restate their modes."""
		client, container = self._container()
		get_client.return_value = client

		docker_manager.write_file_to_container("cid", "{}", "/home/frappe/x.json")

		self.assertNotIn("chmod", exec_commands(container)[0])

	@patch("benchpress.docker_manager.get_client")
	def test_a_zero_exit_returns_without_complaint(self, get_client):
		get_client.return_value = self._container()[0]

		docker_manager.write_file_to_container("cid", "hello", "/etc/wireguard/wg0.conf")

	@patch("benchpress.docker_manager.get_client")
	def test_a_non_zero_exit_raises_naming_the_path_and_the_output(self, get_client):
		"""A bench whose wg0.conf did not land has no tunnel, and nothing else would say so."""
		get_client.return_value = self._container((1, b"Read-only file system"))[0]

		with self.assertRaises(Exception) as caught:
			docker_manager.write_file_to_container("cid", "hello", "/etc/wireguard/wg0.conf")

		self.assertIn("/etc/wireguard/wg0.conf", str(caught.exception))
		self.assertIn("Read-only file system", str(caught.exception))


class TestWaitForContainerRunning(unittest.TestCase):
	@patch("benchpress.docker_manager.time.sleep")
	@patch("benchpress.docker_manager.get_client")
	def test_returns_ip_when_running_on_third_poll(self, get_client, sleep):
		container = _reloading_container([("created", {}), ("created", {}), ("running", IP_ATTRS)])
		get_client.return_value.containers.get.return_value = container
		self.assertEqual(wait_for_container_running("abc123"), "172.30.0.5")
		self.assertEqual(container.reload.call_count, 3)
		self.assertEqual(sleep.call_count, 2)
		sleep.assert_called_with(2)

	@patch("benchpress.docker_manager.time.sleep")
	@patch("benchpress.docker_manager.get_client")
	def test_running_without_ip_keeps_polling(self, get_client, sleep):
		container = _reloading_container(
			[("running", NO_IP_ATTRS), ("running", NO_IP_ATTRS), ("running", IP_ATTRS)]
		)
		get_client.return_value.containers.get.return_value = container
		self.assertEqual(wait_for_container_running("abc123"), "172.30.0.5")
		self.assertEqual(container.reload.call_count, 3)

	@patch("benchpress.docker_manager.time.sleep")
	@patch("benchpress.docker_manager.get_client")
	def test_raises_clear_exception_on_timeout(self, get_client, sleep):
		container = _reloading_container([("created", {})] * 30)
		get_client.return_value.containers.get.return_value = container
		with self.assertRaises(Exception) as ctx:
			wait_for_container_running("abc123")
		self.assertIn("not running with an IP after 60s", str(ctx.exception))
		self.assertEqual(sleep.call_count, 30)


class TestResolveSiteName(unittest.TestCase):
	def test_returns_none_for_empty_input(self):
		self.assertIsNone(docker_manager.resolve_site_name(None))
		self.assertIsNone(docker_manager.resolve_site_name(""))
		self.assertIsNone(docker_manager.resolve_site_name("   "))

	@patch("benchpress.docker_manager.frappe.db.get_single_value", return_value="benchpress.cloud")
	def test_lowercases_and_appends_base_domain(self, get_single_value):
		self.assertEqual(docker_manager.resolve_site_name("Acme"), "acme.benchpress.cloud")

	@patch("benchpress.docker_manager.frappe.db.get_single_value", return_value=None)
	def test_falls_back_to_localhost_when_base_domain_unset(self, get_single_value):
		self.assertEqual(docker_manager.resolve_site_name("acme"), "acme.localhost")

	def test_rejects_a_dotted_label(self):
		with self.assertRaises(frappe.ValidationError):
			docker_manager.resolve_site_name("acme.example.com")

	def test_rejects_invalid_characters(self):
		with self.assertRaises(frappe.ValidationError):
			docker_manager.resolve_site_name("Acme_1")

	def test_rejects_a_label_over_max_length(self):
		with self.assertRaises(frappe.ValidationError):
			docker_manager.resolve_site_name("a" * 64)


def _make_lab(lab_id, **extra):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	doc = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Test Lab {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
			**extra,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc


class TestDockerManagerBlockIO(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

	def _container_create_kwargs(self, lab, runtime="runc", bridge_network="benchpress-0"):
		"""Run create_bench_container with Docker mocked and return the
		kwargs passed to client.containers.create."""
		bench = types.SimpleNamespace(
			bench_name="blockio-test-bench", runtime=runtime, bridge_network=bridge_network
		)
		with (
			patch("benchpress.docker_manager.get_client") as mock_client,
			patch("benchpress.docker_manager.ensure_bench_network_for"),
			patch("benchpress.docker_manager._get_host_block_devices", return_value=["/dev/sda"]),
		):
			mock_client.return_value.containers.create.return_value = MagicMock(id="cid")
			docker_manager.create_bench_container(bench, lab)
			return mock_client.return_value.containers.create.call_args.kwargs

	def test_no_volume_is_mounted_over_the_bench(self):
		"""A named volume over /home/frappe forces a full bench copy on every create."""
		lab = _make_lab("no-volume")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab)

		self.assertNotIn("volumes", kwargs)

	def test_lab_block_io_limits_passed_to_container(self):
		lab = _make_lab("blockio-custom", iops_limit=500, bps_limit=2 * 1024 * 1024)
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab)

		self.assertEqual(kwargs["device_read_iops"], [{"Path": "/dev/sda", "Rate": 500}])
		self.assertEqual(kwargs["device_write_iops"], [{"Path": "/dev/sda", "Rate": 500}])
		self.assertEqual(kwargs["device_read_bps"], [{"Path": "/dev/sda", "Rate": 2 * 1024 * 1024}])
		self.assertEqual(kwargs["device_write_bps"], [{"Path": "/dev/sda", "Rate": 2 * 1024 * 1024}])

	def test_unset_block_io_limits_fall_back_to_defaults(self):
		# iops_limit / bps_limit default to 0, which means "use the default".
		lab = _make_lab("blockio-default")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab)

		self.assertEqual(kwargs["device_read_iops"], [{"Path": "/dev/sda", "Rate": DEFAULT_IOPS}])
		self.assertEqual(kwargs["device_write_bps"], [{"Path": "/dev/sda", "Rate": DEFAULT_BPS}])

	def test_lab_pids_limit_passed_to_container(self):
		lab = _make_lab("pids-custom", pids_limit=250)
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab)

		self.assertEqual(kwargs["pids_limit"], 250)

	def test_unset_pids_limit_falls_back_to_default(self):
		# pids_limit defaults to 0, which means "use the default".
		lab = _make_lab("pids-default")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab)

		self.assertEqual(kwargs["pids_limit"], DEFAULT_PIDS_LIMIT)

	def test_the_container_is_created_on_the_bench_own_network(self):
		lab = _make_lab("network-family")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab, bridge_network="benchpress-1")

		self.assertEqual(kwargs["network"], "benchpress-1")

	def test_a_bench_with_no_network_falls_back_to_the_legacy_one(self):
		"""A row the backfill has not reached must not be sent to a bridge it is not on."""
		lab = _make_lab("network-legacy")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab, bridge_network="")

		self.assertEqual(kwargs["network"], "benchpress")

	def test_runc_passes_no_runtime_kwarg(self):
		"""A runc bench must produce the call it produced before runtimes existed."""
		lab = _make_lab("runtime-runc")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab, runtime="runc")

		self.assertNotIn("runtime", kwargs)

	def test_sysbox_passes_the_registered_runtime_name(self):
		lab = _make_lab("runtime-sysbox")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		kwargs = self._container_create_kwargs(lab, runtime="sysbox")

		self.assertEqual(kwargs["runtime"], "sysbox-runc")

	def test_unknown_runtime_is_refused_before_docker(self):
		lab = _make_lab("runtime-unknown")
		self.addCleanup(frappe.delete_doc, "Lab", lab.name, force=True, ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			self._container_create_kwargs(lab, runtime="gvisor")


class TestHostRuntimes(unittest.TestCase):
	def setUp(self):
		self.addCleanup(clear_local_cache, HOST_RUNTIMES_ATTRIBUTE)
		clear_local_cache(HOST_RUNTIMES_ATTRIBUTE)

	@staticmethod
	def _client(**info):
		client = MagicMock()
		client.info.return_value = {
			"Runtimes": {"runc": {}, "sysbox-runc": {}},
			"DefaultRuntime": "runc",
			**info,
		}
		return client

	@patch("benchpress.docker_manager.get_client")
	def test_reports_the_names_and_the_default(self, get_client):
		get_client.return_value = self._client()

		self.assertEqual(host_runtimes(), {"names": {"runc", "sysbox-runc"}, "default": "runc"})

	@patch("benchpress.docker_manager.get_client")
	def test_asked_twice_costs_one_round_trip(self, get_client):
		"""The deploy gate reads this per bench; a job must not pay `docker info` each time."""
		client = self._client()
		get_client.return_value = client

		host_runtimes()
		host_runtimes()

		client.info.assert_called_once()


class TestPreflightRuntime(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_a_working_runtime_reports_ok(self, get_client):
		client = MagicMock()
		get_client.return_value = client

		result = preflight_runtime("sysbox")

		self.assertTrue(result["ok"])
		self.assertEqual(client.containers.run.call_args.kwargs["runtime"], "sysbox-runc")
		self.assertTrue(client.containers.run.call_args.kwargs["remove"])

	@patch("benchpress.docker_manager.get_client")
	def test_a_registered_but_broken_runtime_reports_dockers_own_message(self, get_client):
		"""The trap this exists for: `docker info` lists it, and it still cannot start."""
		client = MagicMock()
		client.containers.run.side_effect = docker.errors.APIError("failed to create shim task")
		get_client.return_value = client

		result = preflight_runtime("sysbox")

		self.assertFalse(result["ok"])
		self.assertIn("failed to create shim task", result["detail"])

	@patch("benchpress.docker_manager.get_client")
	def test_runc_runs_under_the_daemon_default(self, get_client):
		client = MagicMock()
		client.info.return_value = {"Runtimes": {"runc": {}}, "DefaultRuntime": "runc"}
		get_client.return_value = client
		self.addCleanup(clear_local_cache, HOST_RUNTIMES_ATTRIBUTE)
		clear_local_cache(HOST_RUNTIMES_ATTRIBUTE)

		result = preflight_runtime("runc")

		self.assertTrue(result["ok"])
		self.assertNotIn("runtime", client.containers.run.call_args.kwargs)

	@patch("benchpress.docker_manager.get_client")
	def test_a_runtime_outside_the_allow_list_never_reaches_docker(self, get_client):
		client = MagicMock()
		get_client.return_value = client

		with self.assertRaises(frappe.ValidationError):
			preflight_runtime("gvisor")

		client.containers.run.assert_not_called()


class TestContainerRuntime(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_reads_the_runtime_the_daemon_recorded(self, get_client):
		client = MagicMock()
		client.containers.get.return_value.attrs = {"HostConfig": {"Runtime": "sysbox-runc"}}
		get_client.return_value = client

		self.assertEqual(container_runtime("cid"), "sysbox-runc")


class TestBenchNetworkSpec(unittest.TestCase):
	def test_index_zero_is_the_base_of_the_family(self):
		spec = docker_manager.bench_network_spec(0, "10.20")

		self.assertEqual(spec["name"], "benchpress-0")
		self.assertEqual(spec["device"], "bpbr0")
		self.assertEqual(spec["subnet"], "10.20.0.0/20")
		self.assertEqual(spec["gateway"], "10.20.0.1")

	def test_each_index_starts_on_its_own_slash_20_boundary(self):
		"""A /20 spans 16 third octets, so overlapping ones would share addresses."""
		subnets = [docker_manager.bench_network_spec(i, "10.20")["subnet"] for i in range(4)]

		self.assertEqual(subnets, ["10.20.0.0/20", "10.20.16.0/20", "10.20.32.0/20", "10.20.48.0/20"])

	def test_the_device_name_fits_ifnamsiz(self):
		self.assertLess(len(docker_manager.bench_network_spec(15, "10.20")["device"]), 16)

	def test_a_subnet_base_moves_only_the_addresses(self):
		spec = docker_manager.bench_network_spec(1, "10.40")

		self.assertEqual(spec["name"], "benchpress-1")
		self.assertEqual(spec["subnet"], "10.40.16.0/20")

	def test_index_round_trips_through_the_name(self):
		for index in (0, 1, 7):
			name = docker_manager.bench_network_spec(index)["name"]
			self.assertEqual(docker_manager.bench_network_index(name), index)

	def test_a_foreign_name_has_no_index(self):
		for name in ("benchpress", "benchpress_frappe_network", "benchpress-labs", "bridge"):
			self.assertIsNone(docker_manager.bench_network_index(name))


def _network_holding(*container_names):
	network = MagicMock()
	network.attrs = {"Containers": {f"cid{i}": {"Name": n} for i, n in enumerate(container_names)}}
	return network


class TestAttachInfrastructure(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_attaches_exactly_the_three_infrastructure_containers(self, get_client):
		network = _network_holding()
		get_client.return_value.networks.get.return_value = network

		attached = docker_manager.attach_infrastructure("benchpress-0")

		self.assertEqual(attached, list(docker_manager.INFRASTRUCTURE_CONTAINERS))
		self.assertEqual(
			[call.args[0] for call in network.connect.call_args_list],
			list(docker_manager.INFRASTRUCTURE_CONTAINERS),
		)

	@patch("benchpress.docker_manager.get_client")
	def test_the_control_plane_is_never_attached(self, get_client):
		"""A tenant bridge that reaches the control plane's own database is a breach."""
		network = _network_holding()
		get_client.return_value.networks.get.return_value = network

		docker_manager.attach_infrastructure("benchpress-0")

		connected = {call.args[0] for call in network.connect.call_args_list}
		self.assertTrue(
			connected.isdisjoint({"benchpress_db", "benchpress_redis-cache", "benchpress_redis-queue"})
		)

	@patch("benchpress.docker_manager.get_client")
	def test_an_already_connected_container_is_not_reconnected(self, get_client):
		network = _network_holding("benchpress_traefik")
		get_client.return_value.networks.get.return_value = network

		attached = docker_manager.attach_infrastructure("benchpress-0")

		self.assertIn("benchpress_traefik", attached)
		self.assertNotIn("benchpress_traefik", [call.args[0] for call in network.connect.call_args_list])

	@patch("benchpress.docker_manager.get_client")
	def test_a_missing_container_is_skipped(self, get_client):
		"""A dev checkout has no Traefik, and the deploy must still complete."""
		network = _network_holding()
		network.connect.side_effect = [docker.errors.NotFound("no such container"), None, None]
		get_client.return_value.networks.get.return_value = network

		attached = docker_manager.attach_infrastructure("benchpress-0")

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

	@patch("benchpress.docker_manager.subnet_base", return_value="10.20")
	@patch("benchpress.docker_manager.attach_infrastructure")
	@patch("benchpress.docker_manager.get_client")
	def test_creates_the_bridge_with_a_pinned_device(self, get_client, _attach, _base):
		"""The device option is honoured only at create; a later one keeps br-<hex>."""
		client = self._client_without("benchpress-0")
		get_client.return_value = client

		docker_manager.ensure_bench_network(0)

		kwargs = client.networks.create.call_args.kwargs
		self.assertEqual(kwargs["options"]["com.docker.network.bridge.name"], "bpbr0")
		pool = kwargs["ipam"]["Config"][0]
		self.assertEqual(pool["Subnet"], "10.20.0.0/20")
		self.assertEqual(pool["Gateway"], "10.20.0.1")

	@patch("benchpress.docker_manager.subnet_base", return_value="10.20")
	@patch("benchpress.docker_manager.attach_infrastructure")
	@patch("benchpress.docker_manager.get_client")
	def test_an_existing_bridge_is_not_recreated_but_is_reattached(self, get_client, attach, _base):
		client = MagicMock()
		client.networks.get.return_value = _network_holding()
		get_client.return_value = client

		self.assertEqual(docker_manager.ensure_bench_network(0), "benchpress-0")

		client.networks.create.assert_not_called()
		attach.assert_called_once_with("benchpress-0", client)

	@patch("benchpress.docker_manager.ensure_network")
	@patch("benchpress.docker_manager.get_client")
	def test_the_legacy_name_ensures_the_legacy_network(self, get_client, ensure_network):
		"""Benches that predate the family stay where their containers already are."""
		self.assertEqual(docker_manager.ensure_bench_network_for("benchpress"), "benchpress")

		ensure_network.assert_called_once()

	@patch("benchpress.docker_manager.get_client")
	def test_a_network_outside_the_family_is_refused(self, get_client):
		with self.assertRaises(frappe.ValidationError):
			docker_manager.ensure_bench_network_for("benchpress_frappe_network")


class TestReadBacksTakeTheirNetwork(unittest.TestCase):
	@patch("benchpress.docker_manager.get_client")
	def test_the_ip_is_read_from_the_named_network(self, get_client):
		container = MagicMock()
		container.attrs = {
			"NetworkSettings": {
				"Networks": {
					"benchpress": {"IPAddress": "172.30.0.5"},
					"benchpress-0": {"IPAddress": "10.20.0.5"},
				},
				"IPAddress": "",
			}
		}
		get_client.return_value.containers.get.return_value = container

		self.assertEqual(docker_manager.get_container_ip("abc123", "benchpress-0"), "10.20.0.5")
		self.assertEqual(docker_manager.get_container_ip("abc123"), "172.30.0.5")

	@patch("benchpress.docker_manager.time.sleep")
	@patch("benchpress.docker_manager.get_client")
	def test_waiting_polls_the_named_network(self, get_client, _sleep):
		attrs = {"NetworkSettings": {"Networks": {"benchpress-0": {"IPAddress": "10.20.0.5"}}}}
		container = _reloading_container([("running", attrs)])
		get_client.return_value.containers.get.return_value = container

		self.assertEqual(wait_for_container_running("abc123", "benchpress-0"), "10.20.0.5")


# The message this daemon really emits, copied from a live refusal on Docker 29.7.2 with a
# /29 scratch network. The create succeeded and the *start* raised it.
LIVE_EXHAUSTION = (
	"500 Server Error for http+docker://localhost/v1.55/containers/abc123/start: "
	'Internal Server Error ("failed to set up container networking: no available IPv4 '
	"addresses on this network's address pools: benchpress-0 (fd8f9346a771)\")"
)


class TestAddressPoolExhausted(unittest.TestCase):
	def test_the_live_refusal_is_recognised(self):
		self.assertTrue(docker_manager._address_pool_exhausted(docker.errors.APIError(LIVE_EXHAUSTION)))

	def test_another_five_hundred_is_not_a_full_bridge(self):
		"""The daemon answers 500 for everything, so only the wording separates the two."""
		error = docker.errors.APIError('500 Server Error: Internal Server Error ("no such image")')
		self.assertFalse(docker_manager._address_pool_exhausted(error))


class TestStartBenchContainer(unittest.TestCase):
	@patch("benchpress.docker_manager.start_container")
	def test_a_bridge_with_room_starts_the_container_it_was_given(self, start):
		self.assertEqual(docker_manager.start_bench_container("abc123", MagicMock(), MagicMock()), "abc123")
		start.assert_called_once_with("abc123")

	@patch("benchpress.placement.next_network", return_value="benchpress-1")
	@patch("benchpress.docker_manager.create_bench_container", return_value="def456")
	@patch("benchpress.docker_manager.remove_container")
	@patch("benchpress.docker_manager.container_network", return_value="benchpress-0")
	@patch("benchpress.docker_manager.start_container")
	def test_a_full_bridge_rolls_once_onto_the_next(self, start, _network, remove, create, _next):
		start.side_effect = [docker.errors.APIError(LIVE_EXHAUSTION), None]
		bench, lab = MagicMock(), MagicMock()

		self.assertEqual(docker_manager.start_bench_container("abc123", bench, lab), "def456")

		remove.assert_called_once_with("abc123")
		create.assert_called_once_with(bench, lab, "benchpress-1")

	@patch("benchpress.placement.next_network", return_value="benchpress-1")
	@patch("benchpress.docker_manager.create_bench_container", return_value="def456")
	@patch("benchpress.docker_manager.remove_container")
	@patch("benchpress.docker_manager.container_network", return_value="benchpress-0")
	@patch("benchpress.docker_manager.start_container")
	def test_a_second_refusal_is_raised_rather_than_looped_on(self, start, _network, _remove, _create, _next):
		"""Two bridges refusing in a row means the count disagrees with the daemon."""
		start.side_effect = docker.errors.APIError(LIVE_EXHAUSTION)

		with self.assertRaises(docker.errors.APIError):
			docker_manager.start_bench_container("abc123", MagicMock(), MagicMock())

	@patch("benchpress.docker_manager.start_container")
	def test_any_other_docker_error_is_not_rolled(self, start):
		start.side_effect = docker.errors.APIError("no such image")

		with self.assertRaises(docker.errors.APIError):
			docker_manager.start_bench_container("abc123", MagicMock(), MagicMock())
