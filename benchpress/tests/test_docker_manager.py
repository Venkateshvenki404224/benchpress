# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import unittest
from unittest.mock import MagicMock, patch

import docker

from benchpress.docker_manager import get_container_health


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
