# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import re
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import docker
import frappe
import yaml
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from benchpress import docker_manager, ingress, reconcile
from benchpress.reconcile import (
	DEFAULT_DEPLOY_LOG_CAP,
	DEFAULT_GRACE_MINUTES,
	compare,
	configured_grace_minutes,
)
from benchpress.tests.fakes import FakeDocker
from benchpress.tests.test_deploy_manager import _fresh_bench, _make_lab

LIVE_ID = "40c6dd07a12727f3648970f0a1ae5cdc912f17a6756566264687f2ede0d0ec15"
OTHER_ID = "7716d70b337b7783837f3b515725506c593b41b7cef81dda3f96011a0f24ef66"

# Any dotted quad, anywhere in the rendered file: routes must name containers, never addresses.
IPV4_IN_TEXT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")

# What the reap reports on a host with nothing to reap, for the tests that are about another step.
NO_CONTAINERS = {"orphans": 0, "removed": [], "in_grace": 0, "missing_rows": 0}


def _container(container_id=LIVE_ID, *, age_minutes=60, name="bench-one"):
	"""One entry in the shape `docker_manager.list_benches` returns."""
	created = None if age_minutes is None else datetime.now(UTC) - timedelta(minutes=age_minutes)
	return {
		"id": container_id,
		"name": name,
		"bench_name": name,
		"status": "running",
		"health": "Healthy",
		"created": created,
	}


class TestCompare(unittest.TestCase):
	"""Both sides arrive as arguments, so every case here runs without a database or a daemon."""

	def drift(self, rows, containers, grace_minutes=DEFAULT_GRACE_MINUTES):
		return compare(rows, containers, grace_minutes=grace_minutes)

	def test_a_container_with_no_row_is_an_orphan(self):
		drift = self.drift([], [_container()])

		self.assertEqual([c["id"] for c in drift["orphan_containers"]], [LIVE_ID])
		self.assertEqual(drift["in_grace"], [])

	def test_a_container_inside_the_grace_window_is_never_an_orphan(self):
		"""Every deploy passes through this state: the container exists before the row names it."""
		drift = self.drift([], [_container(age_minutes=2)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual([c["id"] for c in drift["in_grace"]], [LIVE_ID])

	def test_a_container_of_unknown_age_is_never_an_orphan(self):
		drift = self.drift([], [_container(age_minutes=None)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual([c["id"] for c in drift["in_grace"]], [LIVE_ID])

	def test_a_wider_window_spares_an_older_container(self):
		drift = self.drift([], [_container(age_minutes=60)], grace_minutes=120)

		self.assertEqual(drift["orphan_containers"], [])

	def test_a_row_whose_container_is_gone_is_named_missing(self):
		drift = self.drift([{"name": "bench-one", "container_id": LIVE_ID, "status": "Running"}], [])

		self.assertEqual([r["name"] for r in drift["missing_containers"]], ["bench-one"])

	def test_a_matched_pair_is_no_drift_either_way(self):
		rows = [{"name": "bench-one", "container_id": LIVE_ID, "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual(drift, {"orphan_containers": [], "in_grace": [], "missing_containers": []})

	def test_a_row_holding_the_short_id_still_matches_its_container(self):
		rows = [{"name": "bench-one", "container_id": LIVE_ID[:12], "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual(drift["missing_containers"], [])

	def test_a_row_with_no_container_is_not_drift(self):
		"""A Draft bench has no container yet, and never had one."""
		drift = self.drift([{"name": "draft", "container_id": None, "status": "Draft"}], [])

		self.assertEqual(drift["missing_containers"], [])

	def test_both_directions_are_named_at_once(self):
		rows = [{"name": "gone", "container_id": OTHER_ID, "status": "Running"}]

		drift = self.drift(rows, [_container()])

		self.assertEqual([c["id"] for c in drift["orphan_containers"]], [LIVE_ID])
		self.assertEqual([r["name"] for r in drift["missing_containers"]], ["gone"])

	def test_compare_reads_neither_side(self):
		"""The guard against a second, disagreeing implementation that goes and looks for itself."""
		with (
			patch("frappe.get_all", side_effect=AssertionError("compare queried the database")),
			patch(
				"benchpress.docker_manager.get_client",
				side_effect=AssertionError("compare asked the daemon"),
			),
		):
			drift = self.drift([], [_container()])

		self.assertEqual(len(drift["orphan_containers"]), 1)


class TestConfiguredGraceWindow(IntegrationTestCase):
	def _set_window(self, value):
		before = frappe.db.get_single_value("BenchPress Settings", "orphan_grace_minutes")
		frappe.db.set_single_value("BenchPress Settings", "orphan_grace_minutes", value)
		frappe.clear_cache(doctype="BenchPress Settings")
		self.addCleanup(frappe.clear_cache, doctype="BenchPress Settings")
		self.addCleanup(frappe.db.set_single_value, "BenchPress Settings", "orphan_grace_minutes", before)

	def test_an_unset_window_falls_back_to_fifteen(self):
		self._set_window(0)

		self.assertEqual(configured_grace_minutes(), DEFAULT_GRACE_MINUTES)

	def test_the_setting_is_what_compare_uses(self):
		self._set_window(120)

		drift = compare([], [_container(age_minutes=60)])

		self.assertEqual(drift["orphan_containers"], [])
		self.assertEqual(len(drift["in_grace"]), 1)

	def test_the_window_matches_the_admission_claim_grace(self):
		"""Both exist because a deploy that has not written its row is still a deploy."""
		from benchpress.credits import admission_repair

		self.assertEqual(reconcile.DEFAULT_GRACE_MINUTES, admission_repair.CLAIM_GRACE_MINUTES)


@contextmanager
def _route_dir(base_domain="benchpress.cloud"):
	"""A tmp route directory, and a pass whose other steps are stubbed out.

	This runs on a live host: an unstubbed `run` would remove real containers and delete real rows.
	"""
	with tempfile.TemporaryDirectory() as tmp:
		target_dir = Path(tmp) / "dynamic"
		target_dir.mkdir()
		with (
			patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir),
			patch("frappe.get_cached_doc", return_value=frappe._dict(base_domain=base_domain)),
			patch("benchpress.placement.repair", return_value={"attached": {}, "missing": {}}),
			patch.object(reconcile, "_reap_orphan_containers", return_value=dict(NO_CONTAINERS)),
			patch.object(reconcile, "_report_orphan_databases", return_value={}),
			patch.object(reconcile, "_trim_deploy_records", return_value={}),
		):
			yield reconcile, target_dir


class TestReconcileSchedule(IntegrationTestCase):
	"""The `*/5` tick. The entry is the enqueuer and never the pass."""

	def test_the_tick_hands_the_pass_to_the_long_queue(self):
		with patch("frappe.enqueue") as enqueue:
			reconcile.enqueue_run()

		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], "benchpress.reconcile.run")
		self.assertEqual(kwargs["queue"], "long")
		# Unchanged by the move: a job id is a dedup key, not an import path, and renaming it
		# would let a job queued under the old one run beside a new one.
		self.assertEqual(kwargs["job_id"], "route_reconcile")
		self.assertTrue(kwargs["deduplicate"])

	def test_the_cron_entry_is_the_enqueuer_and_never_the_pass(self):
		"""Frappe sends cron to `default`, which `queue-short` also consumes — and that container
		has neither the route mount nor the Docker socket."""
		from benchpress.hooks import scheduler_events

		cron_methods = [method for methods in scheduler_events["cron"].values() for method in methods]

		self.assertIn("benchpress.reconcile.enqueue_run", scheduler_events["cron"]["*/5 * * * *"])
		self.assertNotIn("benchpress.reconcile.run", cron_methods)

	def test_the_settings_save_reaches_the_same_pass(self):
		"""`BenchPress Settings.on_update` re-anchors through this pass, on the queue that can."""
		settings = frappe.get_doc("BenchPress Settings")
		settings._doc_before_save = frappe._dict(base_domain="some-other-zone.example")

		with patch("frappe.enqueue") as enqueue:
			settings.on_update()

		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], "benchpress.reconcile.run")
		self.assertEqual(kwargs["queue"], "long")
		self.assertEqual(kwargs["job_id"], "reconcile_instance_routes")


class TestRunReportsEveryStep(unittest.TestCase):
	def test_every_step_reports_its_own_count(self):
		"""Six counts, never a bare success: a pass that reports "issued" is how drift survives."""
		with (
			patch("benchpress.placement.repair", return_value={"attached": {}, "missing": {}}),
			patch.object(reconcile, "_converge_routes", return_value={"written": 3}),
			patch.object(
				reconcile, "_reap_orphan_containers", return_value={"orphans": 1, "removed": [LIVE_ID]}
			),
			patch.object(reconcile, "_report_orphan_databases", return_value={"orphans": 2}),
			patch.object(reconcile, "_trim_deploy_records", return_value={"deleted": 4}),
			patch.object(reconcile, "_verify_reaped", return_value={"reaped": 1}) as verify,
		):
			result = reconcile.run()

		self.assertEqual(
			sorted(result),
			["bridges", "containers", "databases", "deploy_records", "routes", "verified"],
		)
		# The verification reads the ids the reap issued, not its own idea of what to check.
		verify.assert_called_once_with([LIVE_ID])


class TestReapOrphanContainers(unittest.TestCase):
	"""The removal, and the two things that must never be removed."""

	def setUp(self):
		self.client = FakeDocker()
		patcher = patch("benchpress.docker_manager.get_client", return_value=self.client)
		patcher.start()
		self.addCleanup(patcher.stop)

	def _managed(self, name, **kwargs):
		return self.client.add_container(name, labels={docker_manager.MANAGED_LABEL: "true"}, **kwargs)

	def _reap(self, rows=()):
		with patch.object(reconcile, "_bench_rows", return_value=list(rows)):
			return reconcile._reap_orphan_containers()

	def test_a_labelled_orphan_past_the_grace_window_is_removed(self):
		orphan = self._managed("orphan-one", age_minutes=60)

		report = self._reap()

		self.assertEqual(report["orphans"], 1)
		self.assertEqual(report["removed"], [orphan.id])
		self.assertEqual(self.client.removed, ["orphan-one"])

	def test_a_container_inside_the_grace_window_is_left_alone(self):
		"""Every deploy passes through this state, so removing one destroys a deploy in flight."""
		self._managed("deploying", age_minutes=2)

		report = self._reap()

		self.assertEqual(report["orphans"], 0)
		self.assertEqual(report["in_grace"], 1)
		self.assertEqual(self.client.removed, [])

	def test_an_unlabelled_container_is_never_removed(self):
		"""The negative control, and the worst outcome available here: it is not this app's."""
		stranger = self.client.add_container("someone-elses-postgres", age_minutes=600)

		report = self._reap()

		self.assertEqual(report["orphans"], 0)
		self.assertEqual(self.client.removed, [])
		self.assertIn(stranger.id, self.client._store)

	def test_a_claimed_container_is_not_an_orphan(self):
		claimed = self._managed("live-bench", age_minutes=60)

		report = self._reap([{"name": "bench", "container_id": claimed.id, "status": "Running"}])

		self.assertEqual(report["orphans"], 0)
		self.assertEqual(self.client.removed, [])

	def test_a_refused_removal_does_not_stop_the_next_one(self):
		stuck = self._managed("stuck", age_minutes=60)
		stuck.remove_refusal = "device or resource busy"
		self._managed("removable", age_minutes=60)

		report = self._reap()

		self.assertEqual(report["orphans"], 2)
		self.assertEqual(self.client.removed, ["removable"])


class TestVerifyReaped(unittest.TestCase):
	"""The independent second opinion — read from the daemon, not from the removal's report."""

	def setUp(self):
		self.client = FakeDocker()
		patcher = patch("benchpress.docker_manager.get_client", return_value=self.client)
		patcher.start()
		self.addCleanup(patcher.stop)
		logged = patch("frappe.log_error")
		self.log_error = logged.start()
		self.addCleanup(logged.stop)
		committed = patch("frappe.db.commit")
		committed.start()
		self.addCleanup(committed.stop)

	def _managed(self, name):
		return self.client.add_container(name, labels={docker_manager.MANAGED_LABEL: "true"}, age_minutes=60)

	def test_a_removal_that_took_reports_it_reaped(self):
		container = self._managed("gone-now")
		container.remove()

		report = reconcile._verify_reaped([container.id])

		self.assertEqual(report, {"rechecked": 1, "reissued": 0, "reaped": 1, "still_present": []})
		self.log_error.assert_not_called()

	def test_a_removal_that_did_not_take_is_reported_still_present(self):
		"""The failure the item exists for: "their reconciler reported success while the
		container kept running"."""
		container = self._managed("still-here")
		container.remove_refusal = "device or resource busy"

		report = reconcile._verify_reaped([container.id])

		self.assertEqual(report["reaped"], 0)
		self.assertEqual(report["reissued"], 1)
		self.assertEqual(report["still_present"], [container.id])
		self.assertIn(container.id, self.client._store)
		self.log_error.assert_called_once()

	def test_a_re_issued_removal_that_works_is_reported_reaped(self):
		container = self._managed("second-time-lucky")

		report = reconcile._verify_reaped([container.id])

		self.assertEqual(report["reissued"], 1)
		self.assertEqual(report["reaped"], 1)
		self.assertEqual(self.client.removed, ["second-time-lucky"])

	def test_nothing_issued_asks_the_daemon_nothing(self):
		with patch("benchpress.docker_manager.list_benches", side_effect=AssertionError("asked anyway")):
			report = reconcile._verify_reaped([])

		self.assertEqual(report["rechecked"], 0)


class TestOrphanDatabases(unittest.TestCase):
	"""Counted and named, never dropped. The `DROP` assertion is the load-bearing one."""

	def _report(self, schemas, claimed=frozenset()):
		self.executed = []

		def execute_sql(server, sql):
			self.executed.append(sql)
			return 0, "Database\n" + "\n".join(schemas) + "\n"

		with (
			patch.object(reconcile, "_database_servers", return_value=["db-one"]),
			patch.object(reconcile, "_claimed_databases", return_value=set(claimed)),
			patch("benchpress.mariadb_manager.execute_sql", side_effect=execute_sql),
		):
			return reconcile._report_orphan_databases()

	def test_a_schema_no_row_claims_is_counted_and_named(self):
		report = self._report(["_aaaa000000000000", "_bbbb111111111111"], claimed={"_aaaa000000000000"})

		self.assertEqual(report["schemas"], 2)
		self.assertEqual(report["orphans"], 1)
		self.assertEqual(report["names"], {"db-one": ["_bbbb111111111111"]})

	def test_no_drop_is_ever_issued(self):
		"""The assertion that stops a future contributor "finishing" the feature. Dropping a
		tenant's database is unrecoverable, and the leak's cause is upstream."""
		self._report(["_bbbb111111111111"])

		self.assertTrue(self.executed)
		for sql in self.executed:
			self.assertNotIn("DROP", sql.upper())

	def test_a_server_that_cannot_be_read_does_not_end_the_pass(self):
		with (
			patch.object(reconcile, "_database_servers", return_value=["db-one"]),
			patch.object(reconcile, "_claimed_databases", return_value=set()),
			patch(
				"benchpress.mariadb_manager.list_site_databases",
				side_effect=docker.errors.NotFound("no such container"),
			),
		):
			report = reconcile._report_orphan_databases()

		self.assertEqual(report, {"schemas": 0, "orphans": 0, "names": {}})

	def test_the_backup_directory_is_not_a_schema(self):
		"""MariaDB lists every directory in its data dir, and `backups` is one this app writes."""
		report = self._report(["backups", "_bbbb111111111111"])

		self.assertEqual(report["names"], {"db-one": ["_bbbb111111111111"]})


class TestTrimDeployRecords(IntegrationTestCase):
	"""The per-bench cap that sits on top of Frappe's 7-day age sweep."""

	CAP = 5
	BENCH = "trim-cap-throwaway-bench"

	def setUp(self):
		self.addCleanup(self._forget_rows)

	def _forget_rows(self):
		frappe.db.delete("Deploy Log", {"bench": self.BENCH})
		frappe.db.commit()

	def _seed(self, count):
		for index in range(count):
			frappe.get_doc(
				{
					"doctype": "Deploy Log",
					"bench": self.BENCH,
					"log_type": "info",
					"message": f"run {index}\n",
					"timestamp": add_to_date(now_datetime(), minutes=index),
				}
			).insert(ignore_permissions=True, ignore_links=True)
		frappe.db.commit()

	def test_the_grouped_read_finds_a_bench_over_the_cap(self):
		self._seed(self.CAP + 3)

		over = {row.bench: row.rows for row in reconcile._benches_over_cap(self.CAP)}

		self.assertEqual(over.get(self.BENCH), self.CAP + 3)

	def test_a_bench_at_the_cap_is_not_over_it(self):
		self._seed(self.CAP)

		over = {row.bench for row in reconcile._benches_over_cap(self.CAP)}

		self.assertNotIn(self.BENCH, over)

	def test_the_trim_keeps_the_newest_rows_and_deletes_the_rest(self):
		self._seed(self.CAP + 3)
		over = [row for row in reconcile._benches_over_cap(self.CAP) if row.bench == self.BENCH]

		with (
			patch.object(reconcile, "configured_deploy_log_cap", return_value=self.CAP),
			patch.object(reconcile, "_benches_over_cap", return_value=over),
		):
			report = reconcile._trim_deploy_records()

		kept = frappe.get_all(
			"Deploy Log", filters={"bench": self.BENCH}, pluck="message", order_by="timestamp desc"
		)
		self.assertEqual(report["deleted"], 3)
		self.assertEqual(report["cap"], self.CAP)
		self.assertEqual(kept, [f"run {index}\n" for index in range(7, 2, -1)])

	def test_the_cap_is_a_setting_with_a_default(self):
		self.assertEqual(reconcile.configured_deploy_log_cap(), DEFAULT_DEPLOY_LOG_CAP)


class TestConvergeRoutes(IntegrationTestCase):
	"""The route directory converges on the database — the pass `ingress.reconcile` used to be."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-reconcile-routes")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _bench(self, status, container_ip):
		bench = _fresh_bench(self, self.lab.name)
		bench.status = status
		bench.container_ip = container_ip
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		return bench

	def _seed(self, target_dir, name, body="stale\n"):
		path = target_dir / name
		path.write_text(body)
		return path

	def _instance_files(self, target_dir):
		return sorted(p.name for p in target_dir.glob("*.yml") if p.name not in ingress.PROTECTED_ROUTE_FILES)

	def test_a_route_file_naming_no_bench_instance_is_deleted(self):
		"""The orphan case: a hostname with no document behind it still resolves and still
		routes, so it keeps serving whichever container inherited that IP."""
		with _route_dir() as (reconciler, target_dir):
			orphan = self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")

			routes = reconciler.run()["routes"]

			self.assertFalse(orphan.exists())
			self.assertGreaterEqual(routes["deleted"], 1)

	def test_a_bench_that_is_not_running_loses_its_route_file(self):
		"""A stopped bench's recorded IP is an address Docker has already handed back, so the
		file is not a dead link — it is the next bench's hostname collision."""
		for status in ("Stopped", "Draft", "Error"):
			with self.subTest(status=status):
				bench = self._bench(status, "172.30.0.11")
				with _route_dir() as (reconciler, target_dir):
					route_file = self._seed(target_dir, f"{bench.name}.yml")

					reconciler.run()

					self.assertFalse(route_file.exists())

	def test_a_running_bench_route_is_rewritten_to_name_its_container(self):
		"""Convergence, not merely reaping: a file that survives must also be right. Seeded with
		an address backend so passing means the pass rewrote it to the container name."""
		bench = self._bench("Running", "172.30.0.12")

		with _route_dir() as (reconciler, target_dir):
			self._seed(target_dir, f"{bench.name}.yml", "http://172.30.0.99:8000\n")

			routes = reconciler.run()["routes"]

			written_text = (target_dir / f"{bench.name}.yml").read_text()
			config = yaml.safe_load(written_text)
			backends = [
				server["url"]
				for service in config["http"]["services"].values()
				for server in service["loadBalancer"]["servers"]
			]
			self.assertIn(f"http://{bench.name}:8000", backends)
			self.assertNotRegex(written_text, IPV4_IN_TEXT)
			self.assertGreaterEqual(routes["written"], 1)

	def test_the_control_plane_router_and_the_anchor_survive_a_full_sweep(self):
		"""The guard that stops this pass taking the platform off the internet. `dynamic.yml` is
		the control plane's own router and the anchor is every bench's certificate; a run that
		deletes every instance file must still leave both."""
		with _route_dir() as (reconciler, target_dir):
			control_plane = self._seed(target_dir, "dynamic.yml", "control plane\n")
			ingress.ensure_anchor("benchpress.cloud")
			anchor = target_dir / "wildcard-anchor.yml"
			anchor_text = anchor.read_text()
			self._seed(target_dir, "16b283bccf6560ab1aa5f078d492d005.yml")
			self._seed(target_dir, "5dc12efd9c154796adae757adec1b2f3.yml")

			routes = reconciler.run()["routes"]

			self.assertEqual(control_plane.read_text(), "control plane\n")
			self.assertEqual(anchor.read_text(), anchor_text)
			self.assertEqual(routes["kept"], 2)

	def test_a_run_always_leaves_the_certificate_anchored(self):
		"""The anchor holds the wildcard the resolver-free bench routers serve, so the pass
		writes it first rather than waiting for the next deploy."""
		with _route_dir() as (reconciler, target_dir):
			routes = reconciler.run()["routes"]

			self.assertTrue(routes["anchored"])
			config = yaml.safe_load((target_dir / "wildcard-anchor.yml").read_text())
			router = config["http"]["routers"]["benchpress-wildcard-anchor"]
			self.assertEqual(router["rule"], "Host(`tls-anchor.benchpress.cloud`)")

	def test_the_returned_counts_match_what_happened_on_disk(self):
		"""A reaper that reports what it attempted rather than what converged is how a directory
		drifts for weeks without anyone noticing."""
		bench = self._bench("Running", "172.30.0.13")

		with _route_dir() as (reconciler, target_dir):
			self._seed(target_dir, "dynamic.yml", "control plane\n")
			self._seed(target_dir, f"{bench.name}.yml")
			self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")
			self._seed(target_dir, "5dc12efd9c154796adae757adec1b2f3.yml")

			routes = reconciler.run()["routes"]

			self.assertEqual(routes["deleted"], 2)
			self.assertEqual(routes["kept"], 2)
			self.assertEqual(routes["written"], len(self._instance_files(target_dir)))
			self.assertIn(f"{bench.name}.yml", self._instance_files(target_dir))

	def test_a_second_run_deletes_nothing_and_touches_nothing(self):
		"""Idempotence is the read side agreeing with the write side. A pass that keeps finding
		things to delete disagrees with the files it just wrote — and one that rewrites unchanged
		files is a Traefik reload every five minutes, since it reloads on mtime."""
		self._bench("Running", "172.30.0.14")

		with _route_dir() as (reconciler, target_dir):
			self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")
			reconciler.run()
			before = {p.name: p.stat().st_mtime_ns for p in target_dir.iterdir()}

			routes = reconciler.run()["routes"]

			self.assertEqual(routes["deleted"], 0)
			self.assertFalse(routes["anchored"])
			self.assertEqual({p.name: p.stat().st_mtime_ns for p in target_dir.iterdir()}, before)

	def test_a_container_without_the_route_mount_reports_instead_of_raising(self):
		"""Only `queue-long` mounts the directory, so a by-hand run anywhere else used to do the
		bridge half and then raise out of `ensure_anchor`."""
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", Path(tmp) / "dynamic"),
				patch("frappe.get_cached_doc", return_value=frappe._dict(base_domain="benchpress.cloud")),
			):
				routes = reconcile._converge_routes()

		# None, not 0: nothing was read, and zero counts are what a converged pass reports.
		self.assertEqual(routes, {"anchored": None, "written": None, "deleted": None, "kept": None})

	def test_the_unmounted_pass_records_what_it_saw(self):
		"""The recurring pass is the only writer on a host that never deploys, so returning
		without recording left the diagnostics row blaming the scheduler for a missing mount."""
		frappe.cache().delete_value(ingress.ROUTE_STATE_KEY)
		self.addCleanup(frappe.cache().delete_value, ingress.ROUTE_STATE_KEY)

		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", Path(tmp) / "dynamic"),
				patch("frappe.get_cached_doc", return_value=frappe._dict(base_domain="benchpress.cloud")),
			):
				reconcile._converge_routes()

		state = ingress.directory_state()
		self.assertIsNotNone(state, "the pass returned without reporting what it saw")
		self.assertFalse(state["mounted"])

	def test_a_dev_checkout_is_left_byte_for_byte_alone(self):
		"""No public domain means no route directory this pass understands, so it writes nothing
		and reaps nothing."""
		for base_domain in (None, "", "localhost"):
			with self.subTest(base_domain=base_domain), _route_dir(base_domain) as (reconciler, target_dir):
				survivor = self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")

				routes = reconciler.run()["routes"]

				self.assertTrue(survivor.exists())
				self.assertEqual(routes, {"anchored": False, "written": 0, "deleted": 0, "kept": 0})
