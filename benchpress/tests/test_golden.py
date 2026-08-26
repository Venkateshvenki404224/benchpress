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

from benchpress import deploy_manager, golden, golden_drill
from benchpress.golden import GOLDEN_DB_PREFIX, GOLDEN_DIR, build_golden, golden_database

MANIFEST = {"lab_id": "crm", "mariadb_version": "10.6.28-MariaDB", "dump_bytes": 3}

VERIFY_OUTPUT = "mariadb: Deprecated program name\nGOLDEN_VERIFY 281 frappe crm\n"


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


class TestGoldenVerification(unittest.TestCase):
	"""A dump is never appended on the strength of an exit code — `--source-sql` exits 0 on nothing."""

	def test_the_read_back_is_taken_off_the_marked_line(self):
		self.assertEqual(golden._read_verified(VERIFY_OUTPUT), (281, ["frappe", "crm"]))

	def test_a_read_back_that_reported_nothing_raises(self):
		with self.assertRaises(Exception):
			golden._read_verified("ERROR 1146: Table 'tabInstalled Application' doesn't exist\n")

	def test_an_empty_restore_is_refused(self):
		with self.assertRaises(Exception):
			golden._assert_restored(_lab(), 0, ["frappe", "crm"])

	def test_a_restore_without_the_labs_apps_is_refused(self):
		with self.assertRaises(Exception):
			golden._assert_restored(_lab(), 281, ["frappe"])

	def test_a_restore_carrying_more_than_the_lab_asked_for_passes(self):
		golden._assert_restored(_lab(), 281, ["Frappe", "crm", "erpnext"])

	def test_the_restore_reads_the_dump_the_deploy_will_read(self):
		command = golden._restore_command(_db_server(), "_bpgolden_verify_crm")

		self.assertIn(f"gzip -cd {golden.DUMP_PATH}", command)
		self.assertIn("| mariadb -h benchpress-mariadb -P 3306", command)
		self.assertIn("_bpgolden_verify_crm", command)

	def test_the_apps_are_read_from_the_column_that_holds_them(self):
		"""`tabInstalled Application.name` is a row hash; the app's name is `app_name`."""
		self.assertIn(
			"SELECT app_name FROM `tabInstalled Application`",
			golden._restored_command(_db_server(), "_bpgolden_verify_crm"),
		)


class TestGoldenVerificationCleanup(IntegrationTestCase):
	def test_the_scratch_database_and_its_user_go_even_when_the_restore_fails(self):
		with (
			patch.object(golden, "create_mariadb_user", return_value=("db", "db_limited", "pw")),
			patch.object(golden, "execute_sql", return_value=(0, "")),
			patch.object(golden.docker_manager, "exec_in_container", return_value=(1, "gzip: bad")),
			patch.object(golden, "drop_site_database") as drop_database,
			patch.object(golden, "drop_mariadb_user") as drop_user,
		):
			with self.assertRaises(Exception):
				golden._verify_dump("cid", _db_server(), _lab(), None)

		drop_database.assert_called_once_with(
			"benchpress-mariadb", "bpgolden-verify-crm", "_bpgolden_verify_crm"
		)
		drop_user.assert_called_once_with("benchpress-mariadb", "bpgolden-verify-crm", "_bpgolden_verify_crm")

	def test_a_dump_that_does_not_verify_is_never_appended(self):
		container = MagicMock()
		with (
			patch.object(golden, "ensure_infrastructure", return_value="benchpress-mariadb"),
			patch.object(frappe, "get_doc", return_value=_db_server()),
			patch.object(golden, "_start_scratch_container", return_value=container),
			patch.object(golden, "_create_site"),
			patch.object(golden, "_dump_site", return_value=dict(MANIFEST)),
			patch.object(golden, "_verify_dump", side_effect=Exception("restored no tables")),
			patch.object(golden, "_append_layer") as append,
			patch.object(golden, "drop_site_database"),
		):
			with self.assertRaises(Exception):
				build_golden(_lab())

		append.assert_not_called()

	def test_what_the_restore_proved_travels_in_the_manifest(self):
		container = MagicMock()
		verified = {"tables": 281, "installed_apps": ["crm", "frappe"], "restore_seconds": 6.6}
		with (
			patch.object(golden, "ensure_infrastructure", return_value="benchpress-mariadb"),
			patch.object(frappe, "get_doc", return_value=_db_server()),
			patch.object(golden, "_start_scratch_container", return_value=container),
			patch.object(golden, "_create_site"),
			patch.object(golden, "_dump_site", return_value=dict(MANIFEST)),
			patch.object(golden, "_verify_dump", return_value=verified),
			patch.object(golden, "_append_layer"),
			patch.object(golden, "drop_site_database"),
		):
			manifest = build_golden(_lab())

		self.assertEqual(manifest["tables"], 281)
		self.assertEqual(manifest["installed_apps"], ["crm", "frappe"])
		self.assertEqual(manifest["restore_seconds"], 6.6)


class TestGoldenVersionGate(unittest.TestCase):
	"""The one check that cannot be made inside the image: the server it is restored into."""

	def _decide(self, dump: str, server: str, enabled: bool = True):
		with (
			patch.object(golden, "restore_enabled", return_value=enabled),
			patch.object(golden, "golden_mariadb_version", return_value=dump),
			patch.object(deploy_manager, "server_version", return_value=server),
		):
			return deploy_manager._golden_matches_server("benchpress/crm:lab", _db_server())

	def test_the_same_major_restores(self):
		self.assertEqual(self._decide("10.6.28-MariaDB-ubu2204", "10.6.28-MariaDB-ubu2204"), (True, ""))

	def test_a_patch_bump_is_not_a_mismatch(self):
		"""Refusing on one would take every golden on the host out of service on a server update."""
		use_golden, refusal = self._decide("10.6.31-MariaDB", "10.6.28-MariaDB-ubu2204")

		self.assertTrue(use_golden)
		self.assertEqual(refusal, "")

	def test_a_different_major_takes_the_cold_path_and_says_why(self):
		use_golden, refusal = self._decide("11.4.5-MariaDB", "10.6.28-MariaDB-ubu2204")

		self.assertFalse(use_golden)
		self.assertIn("11.4", refusal)
		self.assertIn("10.6", refusal)

	def test_a_server_that_will_not_name_itself_takes_the_cold_path(self):
		use_golden, refusal = self._decide("10.6.28-MariaDB", "")

		self.assertFalse(use_golden)
		self.assertIn("Could not compare", refusal)

	def test_an_image_with_no_golden_is_already_reported_by_the_image_step(self):
		self.assertEqual(self._decide("", "10.6.28-MariaDB"), (False, ""))

	def test_the_switch_off_creates_the_site_even_where_a_golden_exists(self):
		use_golden, refusal = self._decide("10.6.28-MariaDB", "10.6.28-MariaDB", enabled=False)

		self.assertFalse(use_golden)
		self.assertIn("turned off", refusal)


class TestGoldenDrillMeasure(IntegrationTestCase):
	"""The drill reads a run out of its own Deploy Log, through the pipeline's own parser."""

	LOG = (
		"=== Deploy started ===\n"
		"=== Step 7/11: Creating the site [site @1.9s] ===\n"
		"Site golddrill-crm.benchpress.cloud restored from the image's golden dump\n"
		"=== Step 8/11: Preparing assets [assets @11.6s] ===\n"
		"=== Step 11/11: Deploy complete [complete @12.4s] ===\n"
	)

	def _measure(self, message: str) -> dict:
		with patch.object(frappe, "get_all", return_value=[frappe._dict(name="dl", message=message)]):
			return golden_drill.measure("bench")

	def test_the_site_step_is_the_gap_to_the_next_marker(self):
		measured = self._measure(self.LOG)

		self.assertEqual(measured["site_seconds"], 9.7)
		self.assertEqual(measured["total_seconds"], 12.4)
		self.assertTrue(measured["restored"])

	def test_a_cold_run_reports_itself_as_one(self):
		cold = self.LOG.replace("restored from the image's golden dump", "created successfully")

		self.assertFalse(self._measure(cold)["restored"])

	def test_a_run_that_never_reached_the_site_step_measures_nothing(self):
		measured = self._measure("=== Step 2/11: Preparing the lab image [image @0.4s] ===\n")

		self.assertIsNone(measured["site_seconds"])
		self.assertIsNone(measured["total_seconds"])


class TestGoldenSwitchDefaults(IntegrationTestCase):
	"""A `Check` default only reaches a Single when something writes it."""

	def test_the_patch_turns_both_switches_on_where_nothing_has_set_them(self):
		from benchpress.patches.default_golden_switches import FIELDS, execute

		with (
			patch.object(frappe.db, "get_singles_dict", return_value={}),
			patch.object(frappe.db, "set_single_value") as write,
		):
			execute()

		self.assertEqual([call.args[1] for call in write.call_args_list], list(FIELDS))

	def test_a_switch_an_admin_turned_off_is_left_off(self):
		from benchpress.patches.default_golden_switches import execute

		with (
			patch.object(frappe.db, "get_singles_dict", return_value={"restore_from_golden": 0}),
			patch.object(frappe.db, "set_single_value") as write,
		):
			execute()

		self.assertEqual([call.args[1] for call in write.call_args_list], ["enable_golden_images"])
