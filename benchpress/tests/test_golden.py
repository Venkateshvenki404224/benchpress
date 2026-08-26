# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import io
import json
import tarfile
import types
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import golden
from benchpress.golden import GOLDEN_DB_PREFIX, GOLDEN_DIR, build_golden, golden_database


def _lab(**extra):
	fields = {
		"lab_id": "crm",
		"title": "CRM",
		"image_tag": "benchpress/crm:lab",
		"frappe_version": "version-16",
		"memory_limit": "1g",
		"apps": [frappe._dict(app_name="crm", git_url="https://github.com/frappe/crm", branch="main")],
	}
	return types.SimpleNamespace(**{**fields, **extra})


def _db_server():
	return types.SimpleNamespace(
		name="benchpress-mariadb",
		container_name="benchpress-mariadb",
		get_connection_config=lambda: {"db_host": "benchpress-mariadb", "db_port": 3306},
	)


def _golden_archive() -> tuple[list[bytes], dict]:
	"""What `container.get_archive(GOLDEN_DIR)` returns for a finished dump."""
	buffer = io.BytesIO()
	with tarfile.open(fileobj=buffer, mode="w") as tar:
		info = tarfile.TarInfo("golden/site.sql.gz")
		info.size = 3
		tar.addfile(info, io.BytesIO(b"gz!"))
	return [buffer.getvalue()], {}


class TestGoldenNames(unittest.TestCase):
	def test_golden_database_is_the_only_name_shape_this_feature_drops(self):
		self.assertTrue(golden_database("bpgolden-crm").startswith(GOLDEN_DB_PREFIX))

	def test_a_tenant_site_never_produces_a_golden_database_name(self):
		from benchpress.mariadb_manager import get_database_name

		self.assertFalse(get_database_name("tenant.benchpress.cloud").startswith(GOLDEN_DB_PREFIX))


class TestGoldenDump(unittest.TestCase):
	def test_dump_names_the_sites_own_database_and_pipes_through_gzip(self):
		command = golden._dump_command(_db_server(), "bpgolden-crm")

		self.assertIn("sites/bpgolden-crm/site_config.json", command)
		self.assertIn('mariadb-dump -h benchpress-mariadb -P 3306 -u "$user"', command)
		self.assertIn("| gzip -c > /opt/benchpress/golden/site.sql.gz", command)
		self.assertIn("set -euo pipefail", command)

	def test_meta_is_read_off_the_marked_line_and_not_off_a_client_warning(self):
		output = "mariadb: Deprecated program name\nGOLDEN_META 314572 abc123 10.6.28-MariaDB\n"

		self.assertEqual(golden._read_meta(output), (314572, "abc123", "10.6.28-MariaDB"))

	def test_a_dump_that_reported_nothing_raises(self):
		with self.assertRaises(Exception):
			golden._read_meta("mariadb-dump: connection refused\n")


class TestGoldenBuildContext(unittest.TestCase):
	def _context_members(self) -> dict[str, bytes]:
		manifest = {"lab_id": "crm", "dump_bytes": 3}
		with patch.object(golden.docker_manager, "get_client") as get_client:
			container = get_client.return_value.containers.get.return_value
			container.get_archive.return_value = _golden_archive()
			context = golden._build_context("cid", "benchpress/crm:lab", manifest)
		with tarfile.open(fileobj=context) as tar:
			return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}

	def test_dockerfile_appends_a_layer_to_the_labs_own_tag(self):
		dockerfile = self._context_members()["Dockerfile"].decode()

		self.assertIn("FROM benchpress/crm:lab\n", dockerfile)
		self.assertIn(f"COPY golden {GOLDEN_DIR}\n", dockerfile)

	def test_the_dump_and_the_script_that_reads_it_travel_together(self):
		members = self._context_members()

		self.assertEqual(members["golden/site.sql.gz"], b"gz!")
		self.assertIn("--source-sql", members["setup-site.sh"].decode())

	def test_the_manifest_is_in_the_context(self):
		manifest = json.loads(self._context_members()["golden/manifest.json"])

		self.assertEqual(manifest["lab_id"], "crm")


class TestGoldenManifest(IntegrationTestCase):
	def test_manifest_describes_the_same_recipe_as_the_image_tag(self):
		from benchpress import image_cache

		lab = _lab()
		manifest = golden._manifest(lab, (314572, "abc123", "10.6.28-MariaDB"))
		spec = image_cache.build_spec(lab)

		self.assertEqual(manifest["frappe_version"], spec["frappe_version"])
		self.assertEqual(manifest["apps"], spec["apps"])
		self.assertEqual(manifest["image_tag"], "benchpress/crm:lab")
		self.assertEqual(manifest["mariadb_version"], "10.6.28-MariaDB")


class TestGoldenCleanup(IntegrationTestCase):
	def test_a_lab_with_no_image_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			build_golden(_lab(image_tag=None))

	def test_the_database_and_the_container_go_even_when_the_layer_build_fails(self):
		container = MagicMock()
		with (
			patch.object(golden, "ensure_infrastructure", return_value="benchpress-mariadb"),
			patch.object(frappe, "get_doc", return_value=_db_server()),
			patch.object(golden, "_start_scratch_container", return_value=container),
			patch.object(golden, "_create_site"),
			patch.object(golden, "_dump_site", return_value={}),
			patch.object(golden, "_append_layer", side_effect=Exception("build failed")),
			patch.object(golden, "drop_site_database") as drop,
		):
			with self.assertRaises(Exception):
				build_golden(_lab())

		drop.assert_called_once_with("benchpress-mariadb", "bpgolden-crm", golden_database("bpgolden-crm"))
		container.remove.assert_called_once_with(force=True)
