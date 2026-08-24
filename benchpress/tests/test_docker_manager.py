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
	get_container_health,
	wait_for_container_running,
)


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


class TestWriteFileToContainer(unittest.TestCase):
	"""The exec result used to be discarded, so a file that never landed looked written."""

	def _client_exec_returning(self, result):
		client = MagicMock()
		client.containers.get.return_value.exec_run.return_value = result
		return client

	@patch("benchpress.docker_manager.get_client")
	def test_a_zero_exit_returns_without_complaint(self, get_client):
		get_client.return_value = self._client_exec_returning((0, b""))

		docker_manager.write_file_to_container("cid", "hello", "/etc/wireguard/wg0.conf")

	@patch("benchpress.docker_manager.get_client")
	def test_a_non_zero_exit_raises_naming_the_path_and_the_output(self, get_client):
		get_client.return_value = self._client_exec_returning((1, b"Read-only file system"))

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


class TestResolveSiteNameCollisions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("site-collision-lab")
		cls.other_bench = frappe.get_doc(
			{"doctype": "Bench Instance", "lab": cls.lab.name, "frappe_version": cls.lab.frappe_version}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc("Bench Instance", cls.other_bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _make_site(self, site_name, status, bench=None):
		site = frappe.get_doc(
			{
				"doctype": "Bench Site",
				"bench": bench or self.other_bench.name,
				"site_name": site_name,
				"status": status,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Site", site.name, force=True, ignore_permissions=True)
		self.addCleanup(frappe.db.commit)
		frappe.db.commit()
		return site

	@patch("benchpress.docker_manager.frappe.db.get_single_value", return_value="benchpress.cloud")
	def test_resolve_site_name_throws_on_a_live_collision(self, get_single_value):
		self._make_site("acme.benchpress.cloud", "Active")
		with self.assertRaises(frappe.ValidationError):
			docker_manager.resolve_site_name("acme")

	@patch("benchpress.docker_manager.frappe.db.get_single_value", return_value="benchpress.cloud")
	def test_resolve_site_name_ignores_an_inactive_collision(self, get_single_value):
		self._make_site("acme.benchpress.cloud", "Inactive")
		self.assertEqual(docker_manager.resolve_site_name("acme"), "acme.benchpress.cloud")

	@patch("benchpress.docker_manager.frappe.db.get_single_value", return_value="benchpress.cloud")
	def test_resolve_site_name_excludes_its_own_bench_from_the_collision_check(self, get_single_value):
		self._make_site("acme.benchpress.cloud", "Active", bench=self.other_bench.name)
		self.assertEqual(
			docker_manager.resolve_site_name("acme", exclude_bench=self.other_bench.name),
			"acme.benchpress.cloud",
		)


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

	def _container_create_kwargs(self, lab, runtime="runc"):
		"""Run create_bench_container with Docker mocked and return the
		kwargs passed to client.containers.create."""
		bench = types.SimpleNamespace(bench_name="blockio-test-bench", runtime=runtime)
		with (
			patch("benchpress.docker_manager.get_client") as mock_client,
			patch("benchpress.docker_manager.ensure_network"),
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
