# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import types
import unittest
from unittest.mock import MagicMock, patch

import docker
import frappe
from frappe.tests import IntegrationTestCase

import benchpress.docker_manager as docker_manager
from benchpress.docker_manager import DEFAULT_BPS, DEFAULT_IOPS, get_container_health


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

	def _container_create_kwargs(self, lab):
		"""Run create_bench_container with Docker mocked and return the
		kwargs passed to client.containers.create."""
		bench = types.SimpleNamespace(bench_name="blockio-test-bench")
		with (
			patch("benchpress.docker_manager.get_client") as mock_client,
			patch("benchpress.docker_manager.ensure_network"),
			patch("benchpress.docker_manager._get_host_block_devices", return_value=["/dev/sda"]),
		):
			mock_client.return_value.containers.create.return_value = MagicMock(id="cid")
			docker_manager.create_bench_container(bench, lab)
			return mock_client.return_value.containers.create.call_args.kwargs

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
