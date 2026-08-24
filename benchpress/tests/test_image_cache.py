# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""Phase 3: identical build specs must produce one image, not one per user.

Three contracts are asserted here, in the order they matter:

1. **The hash is the identity of the spec, and nothing else.** Child-row order must not change
   it, and every field that changes the image contents must.
2. **A hit skips the build.** The strongest assertion in the file is that the Docker build API is
   never called on a cache hit — a deploy that "reuses" an image but still builds is the exact
   bug this phase exists to remove.
3. **The cache is swept.** Cached images outlive the Labs that built them, so an unswept cache
   is an unbounded disk leak.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from benchpress import image_cache

BUILD_STREAM = [{"stream": "Successfully built abc123"}]


def _spec(frappe_version="version-15", apps=()):
	"""A Lab as the hash sees it: a version and some app rows."""
	return frappe._dict(
		lab_id="hash-spec",
		title="Hash Spec",
		frappe_version=frappe_version,
		apps=[frappe._dict(app) for app in apps],
	)


def _app(app_name="erpnext", git_url="https://github.com/frappe/erpnext", branch="version-15"):
	return {"app_name": app_name, "git_url": git_url, "branch": branch}


class TestBuildSpec(unittest.TestCase):
	"""`build_spec` is no longer the tag's identity — the tag is static per lab now — but it's
	still what `Lab.reset_status_if_spec_changed` compares to detect a Ready lab gone stale.
	"""

	def test_row_order_does_not_change_the_spec(self):
		crm, erpnext = _app("crm", "https://github.com/frappe/crm", "main"), _app()
		self.assertEqual(
			image_cache.build_spec(_spec(apps=[crm, erpnext])),
			image_cache.build_spec(_spec(apps=[erpnext, crm])),
		)

	def test_a_changed_branch_changes_the_spec(self):
		moved = _app(branch="version-14")
		self.assertNotEqual(
			image_cache.build_spec(_spec(apps=[_app()])),
			image_cache.build_spec(_spec(apps=[moved])),
		)

	def test_a_changed_app_changes_the_spec(self):
		self.assertNotEqual(
			image_cache.build_spec(_spec(apps=[_app()])),
			image_cache.build_spec(_spec(apps=[_app(), _app("hrms")])),
		)

	def test_a_changed_git_url_changes_the_spec(self):
		fork = _app(git_url="https://github.com/someone/erpnext")
		self.assertNotEqual(
			image_cache.build_spec(_spec(apps=[_app()])),
			image_cache.build_spec(_spec(apps=[fork])),
		)

	def test_a_changed_frappe_version_changes_the_spec(self):
		self.assertNotEqual(
			image_cache.build_spec(_spec("version-15")),
			image_cache.build_spec(_spec("version-16")),
		)

	def test_app_name_case_cannot_change_the_spec(self):
		# The build lowercases app names, so two specs that build the same image must compare equal.
		self.assertEqual(
			image_cache.build_spec(_spec(apps=[_app("ERPNext")])),
			image_cache.build_spec(_spec(apps=[_app("erpnext")])),
		)

	def test_the_tag_is_static_per_lab_id(self):
		spec = _spec(apps=[_app()])
		self.assertEqual(image_cache.cache_tag(spec), f"{image_cache.CACHE_REPOSITORY}/{spec.lab_id}:lab")
		# Editing the spec must not change the tag — that's the whole point of a static tag;
		# staleness is `Lab.reset_status_if_spec_changed`'s job, not the tag's.
		changed = _spec(apps=[_app(), _app("hrms")])
		self.assertEqual(image_cache.cache_tag(spec), image_cache.cache_tag(changed))


def _client_with_tags(*tags):
	client = MagicMock()
	client.images.list.return_value = [MagicMock(tags=list(tags))]
	client.api.build.return_value = iter(BUILD_STREAM)
	return client


class TestResolve(unittest.TestCase):
	def setUp(self):
		image_cache.clear_cached_tags()
		self.addCleanup(image_cache.clear_cached_tags)

	def test_resolve_reports_a_hit_when_the_image_exists(self):
		spec = _spec(apps=[_app()])
		with patch(
			"benchpress.docker_manager.get_client",
			return_value=_client_with_tags(image_cache.cache_tag(spec)),
		):
			tag, hit = image_cache.resolve(spec)
		self.assertTrue(hit)
		self.assertEqual(tag, image_cache.cache_tag(spec))

	def test_resolve_reports_a_miss_for_an_unknown_spec(self):
		with patch(
			"benchpress.docker_manager.get_client",
			return_value=_client_with_tags("benchpress/some-other-lab:lab"),
		):
			_tag, hit = image_cache.resolve(_spec(apps=[_app()]))
		self.assertFalse(hit)

	def test_images_outside_the_cache_repository_are_ignored(self):
		with patch(
			"benchpress.docker_manager.get_client",
			return_value=_client_with_tags("benchpress/crm-lab:latest", "mariadb:10.6"),
		):
			self.assertEqual(image_cache.cached_tags(), set())

	def test_docker_is_asked_once_per_request_not_once_per_lab(self):
		client = _client_with_tags("benchpress/cache:000000000000")
		with patch("benchpress.docker_manager.get_client", return_value=client):
			for version in ("version-15", "version-16"):
				image_cache.resolve(_spec(version))
			self.assertEqual(client.images.list.call_count, 1)

			# ...and a build inside the same job invalidates it, so the next read is fresh.
			image_cache.clear_cached_tags()
			image_cache.cached_tags()
			self.assertEqual(client.images.list.call_count, 2)


def _lab(lab_id, apps=(), **extra):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	lab = frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Image Cache {lab_id}",
			"frappe_version": "version-15",
			"apps": [dict(app) for app in apps],
			**extra,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return lab


class TestDeployReusesTheSharedImage(IntegrationTestCase):
	"""The acceptance criterion: the second user to deploy a spec runs no build."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _lab("image-cache-deploy", apps=[_app("crm", "https://github.com/frappe/crm", "main")])
		if not frappe.db.exists("Database Server", "test-db-image-cache"):
			frappe.get_doc(
				{
					"doctype": "Database Server",
					"container_name": "test-db-image-cache",
					"mariadb_version": "10.6",
				}
			).insert(ignore_permissions=True)
		cls.db_server_name = frappe.db.get_value(
			"Database Server", {"container_name": "test-db-image-cache"}, "name"
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.db.delete("Deploy Log", {"bench": name})
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		if cls.db_server_name and frappe.db.exists("Database Server", cls.db_server_name):
			frappe.delete_doc("Database Server", cls.db_server_name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		image_cache.clear_cached_tags()
		self.addCleanup(image_cache.clear_cached_tags)

	def _bench(self):
		from benchpress.tests.test_deploy_manager import _fresh_bench

		bench = _fresh_bench(self, self.lab.name)
		self.addCleanup(frappe.db.commit)
		self.addCleanup(lambda name=bench.name: frappe.db.delete("Deploy Log", {"bench": name}))
		return bench

	def _run_deploy(self, bench, cached_tags=()):
		"""A whole deploy with every side effect mocked but the log and the Docker client."""
		from benchpress import deploy_manager

		client = _client_with_tags(*cached_tags)
		with (
			patch("benchpress.docker_manager.get_client", return_value=client),
			patch.object(deploy_manager, "ensure_infrastructure", autospec=True) as mock_infra,
			patch.object(deploy_manager, "wait_for_mariadb", autospec=True),
			patch.object(deploy_manager, "_remove_stale_container", autospec=True),
			patch.object(deploy_manager, "create_bench_container", autospec=True) as mock_create,
			patch.object(deploy_manager, "start_container", autospec=True),
			patch.object(deploy_manager, "wait_for_container_running", autospec=True) as mock_wait,
			patch.object(deploy_manager, "_setup_container_vpn", autospec=True),
			patch.object(deploy_manager, "write_file_to_container", autospec=True),
			patch.object(deploy_manager, "exec_in_container", autospec=True) as mock_exec,
			patch.object(deploy_manager, "create_site_in_container", autospec=True) as mock_site,
			patch.object(deploy_manager, "_notify_owner", autospec=True),
			# Traefik's route directory is mounted into queue-long, not into the container
			# these tests run in, so both writers have to be mocked for the deploy to reach
			# its end — as the docstring above says it does.
			patch.object(deploy_manager, "_ensure_wildcard_anchor", autospec=True),
			patch.object(deploy_manager, "_write_instance_route", autospec=True),
			# The certificate check opens a real TLS socket to Traefik; a unit test must
			# not depend on one running.
			patch.object(deploy_manager, "_certificate_error", autospec=True, return_value=None),
		):
			mock_infra.return_value = self.db_server_name
			mock_create.return_value = "cid-image-cache"
			mock_wait.return_value = "172.30.0.21"
			mock_exec.return_value = (0, "")
			mock_site.return_value = (0, "site created")
			deploy_manager.deploy_bench(bench.name)
		return client

	def _log(self, bench_name):
		logs = frappe.get_all(
			"Deploy Log",
			filters={"bench": bench_name},
			fields=["message"],
			order_by="creation desc",
			limit_page_length=1,
		)
		return logs[0].message if logs else ""

	def test_a_ready_lab_with_its_image_cached_performs_no_build(self):
		bench = self._bench()
		tag = image_cache.cache_tag(self.lab)
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": tag})
		frappe.db.commit()

		client = self._run_deploy(bench, cached_tags=[tag])

		client.api.build.assert_not_called()
		self.assertIn(f"Using built image {tag}", self._log(bench.name))

	def test_the_step_explains_which_image_it_used(self):
		bench = self._bench()
		tag = image_cache.cache_tag(self.lab)
		frappe.db.set_value("Lab", self.lab.name, {"status": "Ready", "image_tag": tag})
		frappe.db.commit()

		self._run_deploy(bench, cached_tags=[tag])

		log = self._log(bench.name)
		self.assertIn("Step 2/11", log)
		self.assertIn(f"Using built image {tag}", log)

	def test_a_deploy_never_builds_it_fails_fast_instead(self):
		"""The core contract this phase adds: deploy is a lookup, never a build."""
		bench = self._bench()
		frappe.db.set_value("Lab", self.lab.name, {"status": "Draft", "image_tag": None})
		frappe.db.commit()

		client = self._run_deploy(bench, cached_tags=[])

		client.api.build.assert_not_called()
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")
		self.assertIn("No built image", self._log(bench.name))

	def test_a_stale_tag_on_a_ready_lab_also_fails_fast(self):
		"""`status == Ready` alone isn't enough — the tag must match what's actually cached."""
		bench = self._bench()
		frappe.db.set_value(
			"Lab",
			self.lab.name,
			{"status": "Ready", "image_tag": f"{image_cache.CACHE_REPOSITORY}/stale:lab"},
		)
		frappe.db.commit()

		client = self._run_deploy(bench, cached_tags=[image_cache.cache_tag(self.lab)])

		client.api.build.assert_not_called()
		self.assertEqual(frappe.db.get_value("Bench Instance", bench.name, "status"), "Error")


class TestPrewarmCatalog(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		image_cache.clear_cached_tags()
		self.addCleanup(image_cache.clear_cached_tags)

	def test_every_uncached_template_is_queued_once(self):
		from benchpress import lab_templates

		with (
			patch("benchpress.docker_manager.get_client", return_value=_client_with_tags()),
			patch("frappe.enqueue") as enqueue,
		):
			result = image_cache.prewarm_catalog()

		keys = [template["key"] for template in lab_templates.get_templates()]
		self.assertEqual(result["queued"], keys)
		self.assertEqual(result["cached"], 0)
		self.assertEqual(enqueue.call_count, len(keys))
		for call in enqueue.call_args_list:
			self.assertEqual(call.kwargs["queue"], "long")
			self.assertTrue(call.kwargs["deduplicate"])

	def test_an_already_cached_template_is_not_rebuilt(self):
		from benchpress import lab_templates

		erpnext = lab_templates.get_template("erpnext")
		cached = image_cache.cache_tag(image_cache.template_spec(erpnext))
		with (
			patch("benchpress.docker_manager.get_client", return_value=_client_with_tags(cached)),
			patch("frappe.enqueue") as enqueue,
		):
			result = image_cache.prewarm_catalog()

		self.assertNotIn("erpnext", result["queued"])
		self.assertEqual(result["cached"], 1)
		self.assertEqual(enqueue.call_count, len(lab_templates.get_templates()) - 1)

	def test_the_cron_hands_the_work_to_the_worker_with_the_socket(self):
		"""Scheduled jobs run on `queue-short`, which has no Docker socket mounted."""
		with patch("frappe.enqueue") as enqueue:
			image_cache.enqueue_prewarm_catalog()
			image_cache.enqueue_sweep()

		methods = [call.args[0] for call in enqueue.call_args_list]
		self.assertEqual(
			methods,
			["benchpress.image_cache.prewarm_catalog", "benchpress.image_cache.sweep_cached_images"],
		)
		for call in enqueue.call_args_list:
			self.assertEqual(call.kwargs["queue"], "long")

	def test_a_template_build_tags_by_the_template_s_own_key(self):
		from benchpress import lab_templates

		client = _client_with_tags()
		with patch("benchpress.docker_manager.get_client", return_value=client):
			tag = image_cache.build_template_image("crm")

		expected = image_cache.cache_tag(image_cache.template_spec(lab_templates.get_template("crm")))
		self.assertEqual(tag, expected)
		self.assertEqual(client.api.build.call_args.kwargs["tag"], expected)


class TestSweepCachedImages(IntegrationTestCase):
	"""Cached images outlive their Labs, so an unswept cache leaks disk without bound."""

	ORPHAN = "benchpress/orphan-lab:lab"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _lab(
			"image-cache-sweep", apps=[_app("hrms", "https://github.com/frappe/hrms", "version-15")]
		)
		cls.referenced = image_cache.cache_tag(cls.lab)
		frappe.db.set_value("Lab", cls.lab.name, {"status": "Ready", "image_tag": cls.referenced})
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		image_cache.clear_cached_tags()
		self.addCleanup(image_cache.clear_cached_tags)

	def _sweep(self, *tags):
		client = _client_with_tags(*tags)
		with patch("benchpress.docker_manager.get_client", return_value=client):
			return image_cache.sweep_cached_images(), client

	def test_an_orphan_tag_is_removed(self):
		result, client = self._sweep(self.ORPHAN)
		self.assertEqual(result["removed"], [self.ORPHAN])
		client.images.remove.assert_called_once_with(self.ORPHAN)

	def test_a_tag_a_lab_still_points_at_is_kept(self):
		result, client = self._sweep(self.referenced, self.ORPHAN)
		self.assertEqual(result["removed"], [self.ORPHAN])
		self.assertEqual(result["kept"], 1)
		self.assertNotIn(self.referenced, [call.args[0] for call in client.images.remove.call_args_list])

	def test_a_catalog_tag_is_kept_even_with_no_lab(self):
		from benchpress import lab_templates

		catalog = image_cache.cache_tag(image_cache.template_spec(lab_templates.get_template("erpnext")))
		result, _client = self._sweep(catalog, self.ORPHAN)
		self.assertEqual(result["removed"], [self.ORPHAN])

	def test_a_tag_a_running_container_was_created_from_is_kept(self):
		bench = self._bench_on(self.ORPHAN)
		result, _client = self._sweep(self.ORPHAN)
		self.assertEqual(result["removed"], [])
		self.assertTrue(frappe.db.exists("Bench Instance", bench))

	def test_the_image_a_running_build_will_produce_is_kept(self):
		"""A Building lab has no `image_tag` yet, so the sweep hashes its spec instead."""
		frappe.db.set_value("Lab", self.lab.name, {"status": "Building", "image_tag": None})
		self.addCleanup(
			frappe.db.set_value, "Lab", self.lab.name, {"status": "Ready", "image_tag": self.referenced}
		)
		frappe.db.commit()
		frappe.clear_document_cache("Lab", self.lab.name)

		result, _client = self._sweep(self.referenced, self.ORPHAN)

		self.assertEqual(result["removed"], [self.ORPHAN])

	def test_pre_cache_lab_images_are_left_alone(self):
		result, client = self._sweep("benchpress/legacy-lab:latest")
		self.assertEqual(result["removed"], [])
		client.images.remove.assert_not_called()

	def _bench_on(self, image_tag):
		from benchpress.tests.test_deploy_manager import _fresh_bench

		bench = _fresh_bench(self, self.lab.name)
		frappe.db.set_value("Bench Instance", bench.name, "container_image", image_tag)
		frappe.db.commit()
		return bench.name
