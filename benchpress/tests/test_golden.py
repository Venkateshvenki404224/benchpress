# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import io
import json
import tarfile
import types
import unittest
from unittest.mock import MagicMock, patch

import docker
import frappe
from frappe.tests import IntegrationTestCase

from benchpress import deploy_manager, golden
from benchpress.golden import GOLDEN_DB_PREFIX, GOLDEN_DIR, build_golden, golden_database

MANIFEST = {"lab_id": "crm", "mariadb_version": "10.6.28-MariaDB", "dump_bytes": 3}


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
		with patch.object(golden.docker_manager, "get_client") as get_client:
			container = get_client.return_value.containers.get.return_value
			container.get_archive.return_value = _golden_archive()
			context = golden._build_context("cid", "benchpress/crm:lab", MANIFEST)
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


class TestGoldenLabels(unittest.TestCase):
	"""A deploy asks the image whether it has a golden; the `Lab` row is only ever a claim."""

	def test_the_appended_layer_stamps_what_a_deploy_reads_back(self):
		dockerfile = golden._dockerfile("benchpress/crm:lab", MANIFEST)

		self.assertIn('LABEL benchpress.golden="1"', dockerfile)
		self.assertIn('benchpress.golden.mariadb="10.6.28-MariaDB"', dockerfile)

	def test_an_unlabelled_image_has_no_golden_however_the_row_reads(self):
		client = MagicMock()
		client.images.get.return_value.labels = {}
		with patch.object(golden.docker_manager, "get_client", return_value=client):
			self.assertFalse(golden.image_has_golden("benchpress/crm:lab"))

	def test_an_image_that_is_not_on_this_host_has_no_golden(self):
		client = MagicMock()
		client.images.get.side_effect = docker.errors.ImageNotFound("gone")
		with patch.object(golden.docker_manager, "get_client", return_value=client):
			self.assertFalse(golden.image_has_golden("benchpress/ghost:lab"))

	def test_a_docker_that_cannot_answer_sends_the_deploy_down_the_cold_path(self):
		"""The alternative is a deploy that fails because an optimisation could not be checked."""
		client = MagicMock()
		client.images.get.side_effect = docker.errors.APIError("daemon busy")
		with patch.object(golden.docker_manager, "get_client", return_value=client):
			self.assertFalse(golden.image_has_golden("benchpress/crm:lab"))

	def test_coverage_counts_the_labelled_tags_only(self):
		client = MagicMock()
		client.images.list.return_value = [
			MagicMock(tags=["benchpress/crm:lab"], labels={golden.GOLDEN_LABEL: "1"}),
			MagicMock(tags=["benchpress/erpnext:lab"], labels={}),
		]
		with patch.object(golden.docker_manager, "get_client", return_value=client):
			self.assertEqual(golden.golden_tags(), {"benchpress/crm:lab"})


class TestAddGolden(unittest.TestCase):
	"""The wrapper a build calls. Its whole job is to have no failure mode of its own."""

	def test_the_switch_off_means_the_step_never_runs(self):
		with (
			patch.object(golden, "golden_images_enabled", return_value=False),
			patch.object(golden, "build_golden") as build,
		):
			self.assertIsNone(golden.add_golden(_lab()))

		build.assert_not_called()

	def test_a_golden_that_raises_comes_back_as_no_manifest(self):
		with (
			patch.object(golden, "golden_images_enabled", return_value=True),
			patch.object(golden, "build_golden", side_effect=Exception("out of disk")),
			patch.object(frappe, "log_error") as log_error,
		):
			self.assertIsNone(golden.add_golden(_lab()))

		log_error.assert_called_once()

	def test_a_finished_golden_hands_its_manifest_back(self):
		with (
			patch.object(golden, "golden_images_enabled", return_value=True),
			patch.object(golden, "build_golden", return_value=MANIFEST),
		):
			self.assertEqual(golden.add_golden(_lab()), MANIFEST)


class TestGoldenOnEveryBuild(IntegrationTestCase):
	"""The golden is a property of a build — and a build's outcome never depends on it."""

	LAB_ID = "golden-on-build"
	TAG = f"benchpress/{LAB_ID}:lab"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		if frappe.db.exists("Lab", cls.LAB_ID):
			frappe.delete_doc("Lab", cls.LAB_ID, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": cls.LAB_ID,
				"title": "Golden On Build",
				"frappe_version": "version-15",
				"apps": [{"app_name": "crm", "git_url": "https://github.com/frappe/crm", "branch": "main"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Lab", cls.LAB_ID, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _build(self, enabled=True, **build_golden_kwargs):
		lab = frappe.get_doc("Lab", self.LAB_ID)
		with (
			patch.object(deploy_manager, "build_lab_image", return_value=self.TAG),
			patch.object(deploy_manager.metering, "on_image_built"),
			patch.object(golden, "golden_images_enabled", return_value=enabled),
			patch.object(golden, "build_golden", **build_golden_kwargs) as build,
		):
			deploy_manager._build_lab_with_logs(lab, None)
		return frappe.get_doc("Lab", self.LAB_ID), build

	def test_a_build_bakes_the_golden_and_records_what_it_baked(self):
		lab, build = self._build(return_value=MANIFEST)

		build.assert_called_once()
		self.assertEqual(lab.status, "Ready")
		self.assertEqual(json.loads(lab.golden_manifest)["lab_id"], "crm")

	def test_the_switch_off_leaves_the_build_exactly_as_it_was(self):
		lab, build = self._build(enabled=False, return_value=MANIFEST)

		build.assert_not_called()
		self.assertEqual(lab.status, "Ready")
		self.assertEqual(lab.image_tag, self.TAG)
		self.assertFalse(lab.golden_manifest)

	def test_a_failed_golden_still_leaves_a_ready_lab_and_a_usable_image(self):
		lab, _build = self._build(side_effect=Exception("scratch container died"))

		self.assertEqual(lab.status, "Ready")
		self.assertEqual(lab.image_tag, self.TAG)
		self.assertFalse(lab.golden_manifest)

	def test_a_spec_change_takes_the_manifest_with_the_status(self):
		lab, _build = self._build(return_value=MANIFEST)

		lab.append(
			"apps", {"app_name": "hrms", "git_url": "https://github.com/frappe/hrms", "branch": "main"}
		)
		lab.save(ignore_permissions=True)

		self.assertEqual(lab.status, "Draft")
		self.assertFalse(lab.golden_manifest)

	def test_a_new_image_tag_takes_the_manifest_with_it(self):
		lab, _build = self._build(return_value=MANIFEST)

		lab.image_tag = "benchpress/somewhere-else:lab"
		lab.save(ignore_permissions=True)

		self.assertFalse(lab.golden_manifest)
