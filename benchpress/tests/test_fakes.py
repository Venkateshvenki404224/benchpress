# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import ast
import unittest
from pathlib import Path

import docker
import frappe
from frappe.tests import IntegrationTestCase

from benchpress import docker_manager, mariadb_manager
from benchpress.tests.fakes import GET_CLIENT_MODULES, FakeDocker, FakeDockerMixin, UnscriptedExec


class TestFakeDocker(unittest.TestCase):
	def test_get_on_an_unknown_id_raises_not_found(self):
		with self.assertRaises(docker.errors.NotFound):
			FakeDocker().containers.get("nope")

	def test_list_returns_a_container_the_label_filter_matches(self):
		fake = FakeDocker()
		fake.add_container("bench-a", labels={"benchpress.managed": "true"})

		found = fake.containers.list(filters={"label": "benchpress.managed=true"})

		self.assertEqual([c.name for c in found], ["bench-a"])

	def test_list_omits_a_container_the_label_filter_misses(self):
		"""A list that returned everything would let a managed-only filter ship broken."""
		fake = FakeDocker()
		fake.add_container("bench-a", labels={"benchpress.managed": "true"})
		fake.add_container("stranger", labels={"com.example.other": "true"})

		found = fake.containers.list(filters={"label": "benchpress.managed=true"})

		self.assertEqual([c.name for c in found], ["bench-a"])

	def test_list_omits_a_stopped_container_unless_asked_for_all(self):
		fake = FakeDocker()
		fake.add_container("stopped", status="exited")

		self.assertEqual(fake.containers.list(), [])
		self.assertEqual([c.name for c in fake.containers.list(all=True)], ["stopped"])

	def test_script_exec_matches_on_substring(self):
		fake = FakeDocker()
		fake.script_exec("SELECT VERSION", (0, b"10.6.16"))
		container = fake.add_container("db")

		self.assertEqual(
			container.exec_run(cmd=["bash", "-c", "mariadb -e 'SELECT VERSION()'"]), (0, b"10.6.16")
		)

	def test_an_unmatched_exec_returns_zero_and_empty_output(self):
		container = FakeDocker().add_container("bench")

		self.assertEqual(container.exec_run(cmd=["bash", "-c", "true"]), (0, b""))

	def test_strict_raises_on_an_unmatched_exec(self):
		container = FakeDocker(strict=True).add_container("bench")

		with self.assertRaises(UnscriptedExec):
			container.exec_run(cmd=["bash", "-c", "true"])

	def test_every_exec_is_recorded(self):
		fake = FakeDocker()
		fake.add_container("bench").exec_run(cmd=["bash", "-c", "whoami"])

		self.assertEqual(fake.execs, ["bash -c whoami"])


class TestFakeDockerMixinOnUnitTestCase(FakeDockerMixin, unittest.TestCase):
	def test_every_get_client_binding_answers_with_the_fake(self):
		for module in GET_CLIENT_MODULES:
			self.assertIs(module.get_client(), self.docker)

	def test_the_two_host_reads_are_stubbed(self):
		self.assertEqual(docker_manager._get_host_block_devices(), ["/dev/sda"])
		self.assertEqual(mariadb_manager._compose_cmd("ps"), (0, ""))


class TestFakeDockerMixinOnIntegrationTestCase(FakeDockerMixin, IntegrationTestCase):
	def test_the_fake_installs_alongside_the_frappe_fixtures(self):
		self.assertIs(docker_manager.get_client(), self.docker)


class TestGetClientImporters(unittest.TestCase):
	def test_the_mixin_patches_every_module_that_binds_get_client(self):
		"""A new module-level import would otherwise reach the real daemon in silence."""
		patched = {module.__name__ for module in GET_CLIENT_MODULES}

		self.assertEqual(_modules_binding_get_client() | {"benchpress.docker_manager"}, patched)


def _modules_binding_get_client() -> set[str]:
	root = Path(frappe.get_app_path("benchpress"))
	found = set()
	for path in root.rglob("*.py"):
		if "tests" in path.parts:
			continue
		tree = ast.parse(path.read_text())
		for node in tree.body:
			if not isinstance(node, ast.ImportFrom) or node.module != "benchpress.docker_manager":
				continue
			if any(alias.name == "get_client" for alias in node.names):
				found.add(_dotted_name(root, path))
	return found


def _dotted_name(root: Path, path: Path) -> str:
	parts = path.relative_to(root).with_suffix("").parts
	return ".".join((root.name, *parts))
