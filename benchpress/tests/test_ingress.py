# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import re
import ssl
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
import yaml
from frappe.tests import IntegrationTestCase

from benchpress import ingress
from benchpress.credits.config import clear_size_index
from benchpress.tests.test_deploy_manager import _fresh_bench, _make_lab

# Any dotted quad, anywhere in the rendered file. The property routes must hold is that no
# address of any kind appears — asserting one known IP is absent would pass for the next one.
IPV4_IN_TEXT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _mounted(tmp) -> Path:
	"""The route directory arranged the way production has it: a bind mount that exists.

	Tests create it rather than relying on the writers to, so the missing-mount guard is
	exercised by the tests that are about it instead of bypassed by every other test.
	"""
	target_dir = Path(tmp) / "instances"
	target_dir.mkdir()
	return target_dir


def _make_size(label, include_code_server, memory_limit, **fields):
	"""A throwaway `Instance Size`, replaced rather than reused so its flags are known."""
	if frappe.db.exists("Instance Size", label):
		frappe.delete_doc("Instance Size", label, force=True, ignore_permissions=True)
	size = frappe.new_doc("Instance Size")
	size.update(
		{
			"size_label": label,
			"memory_limit": memory_limit,
			"cpu_cores": 3,
			"credits_per_hour": 1.0,
			"include_code_server": include_code_server,
			**fields,
		}
	)
	return size.insert(ignore_permissions=True)


class TestPublish(unittest.TestCase):
	"""Pure-function tests, no container/DB — the URL helpers moved to test_addressing.py.

	The IDE flag is forced here; whether a bench has one is `TestIdeRouter`'s subject.
	"""

	def test_publish_writes_router_and_service(self):
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "benchpress.cloud")
				config = yaml.safe_load((Path(tmp) / "instances" / "inst-1.yml").read_text())

			# TLS on, no resolver — the certificate comes from the store, put there by
			# `wildcard-anchor.yml`. See test_instance_route_names_no_certificate_resolver.
			expected_tls = {}

			router = config["http"]["routers"]["site-inst-1"]
			self.assertEqual(router["rule"], "Host(`inst-1.benchpress.cloud`)")
			self.assertEqual(router["service"], "site-inst-1")
			self.assertEqual(router["tls"], expected_tls)

			service = config["http"]["services"]["site-inst-1"]
			self.assertEqual(service["loadBalancer"]["servers"], [{"url": "http://inst-1:8000"}])

			ide_router = config["http"]["routers"]["ide-inst-1"]
			self.assertEqual(ide_router["rule"], "Host(`ide-inst-1.benchpress.cloud`)")
			self.assertEqual(ide_router["service"], "ide-inst-1")
			self.assertEqual(ide_router["tls"], expected_tls)

			ide_service = config["http"]["services"]["ide-inst-1"]
			self.assertEqual(ide_service["loadBalancer"]["servers"], [{"url": "http://inst-1:8080"}])

	def test_publish_no_ops_for_localhost(self):
		"""Runs unmounted: the localhost return has to come before the missing-mount guard,
		or a dev checkout would raise where it used to write nothing."""
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = Path(tmp) / "instances"
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "localhost")

			self.assertFalse(target_dir.exists())

	def test_instance_route_names_no_certificate_resolver(self):
		"""A resolver here would cost an ACME call per bench spawn.

		Let's Encrypt allows five certificates per identifier set per seven days, so a
		per-bench resolver caps the platform at about five benches a week. The wildcard is
		held by `wildcard-anchor.yml` instead. Asserted against the rendered text because
		the regression is a resolver at *any* depth, not one known key.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "benchpress.cloud")
				written_text = (Path(tmp) / "instances" / "inst-1.yml").read_text()

		self.assertNotIn("certResolver", written_text)
		# One `{}` literal per router, so PyYAML emits the mapping each time rather than an
		# anchor/alias pair that Traefik would have to resolve.
		self.assertEqual(written_text.count("tls: {}"), 3)

	def test_instance_route_names_the_container_and_no_address(self):
		"""The property this phase exists to create. Both services name the container, which
		Docker's embedded DNS resolves, so no lifecycle transition can make the file stale."""
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "benchpress.cloud")
				written_text = (Path(tmp) / "instances" / "inst-1.yml").read_text()

		config = yaml.safe_load(written_text)
		backends = sorted(
			server["url"]
			for service in config["http"]["services"].values()
			for server in service["loadBalancer"]["servers"]
		)
		self.assertEqual(backends, ["http://inst-1:8000", "http://inst-1:8080"])
		self.assertNotRegex(written_text, IPV4_IN_TEXT)

	def test_rewriting_a_route_leaves_one_file_and_no_temp(self):
		"""The write is a rename, not a truncate: Traefik reads this directory live, so a
		half-written file is a config-parse error on the one internet-facing container."""
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = _mounted(tmp)
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "benchpress.cloud")
				ingress.publish("inst-1", "benchpress.cloud")

			# iterdir, so a leftover dotfile temp counts against this.
			self.assertEqual([p.name for p in target_dir.iterdir()], ["inst-1.yml"])

	def test_an_unchanged_route_is_not_rewritten(self):
		"""Traefik reloads on mtime, and the convergence cron rewrites every running bench's
		route every five minutes — so an identical write has to be a no-op."""
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = _mounted(tmp)
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir),
				patch.object(ingress, "has_ide", return_value=True),
			):
				ingress.publish("inst-1", "benchpress.cloud")
				mtime = (target_dir / "inst-1.yml").stat().st_mtime_ns

				ingress.publish("inst-1", "benchpress.cloud")

				self.assertEqual((target_dir / "inst-1.yml").stat().st_mtime_ns, mtime)


class TestServiceHealthCheck(unittest.TestCase):
	"""Traefik's own probe, which is the only thing that ejects a server from routing.

	Docker's verdict cannot: Traefik reads the file provider and has no socket to hear it on.
	"""

	def _config(self, **settings):
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)),
				patch.object(ingress, "has_ide", return_value=True),
				patch.object(ingress, "rate_limits", return_value=ingress.DEFAULT_RATE_LIMITS),
				patch.object(ingress, "frappe") as frappe_mock,
			):
				frappe_mock.get_cached_doc.return_value = frappe._dict(settings)
				ingress.publish("inst-1", "benchpress.cloud")
				return yaml.safe_load((Path(tmp) / "instances" / "inst-1.yml").read_text())

	def _health(self, service, **settings):
		return self._config(**settings)["http"]["services"][service]["loadBalancer"]["healthCheck"]

	def test_both_services_carry_a_health_check(self):
		services = self._config()["http"]["services"]
		for name in ("site-inst-1", "ide-inst-1"):
			self.assertIn("healthCheck", services[name]["loadBalancer"])

	def test_the_site_service_probes_the_site(self):
		self.assertEqual(self._health("site-inst-1")["path"], "/api/method/ping")

	def test_the_ide_service_probes_the_ide(self):
		"""Asserted apart from the site's: a copy-paste that gives both the same path passes
		any test that only asks whether a health check exists."""
		self.assertEqual(self._health("ide-inst-1")["path"], "/healthz")

	def test_the_probe_rate_comes_from_settings(self):
		health = self._health(
			"site-inst-1", traefik_health_interval_seconds=7, traefik_health_timeout_seconds=2
		)
		self.assertEqual((health["interval"], health["timeout"]), ("7s", "2s"))

	def test_an_install_that_never_saved_its_settings_still_gets_a_rate(self):
		"""A Single holds only what somebody wrote, and a settings save materialises the rest
		as zero — so both readings have to fall back rather than probe every zero seconds."""
		self.assertEqual(self._health("ide-inst-1")["interval"], "10s")
		self.assertEqual(self._health("ide-inst-1", traefik_health_interval_seconds=0)["interval"], "10s")

	def test_the_probe_names_no_hostname(self):
		"""It is sent to the server URL, so the Host header is the container name and the
		bench's `default_site` resolves it. A `hostname` key would look like a fix and be none."""
		self.assertEqual(sorted(self._health("site-inst-1")), ["interval", "path", "timeout"])

	def test_the_router_half_is_untouched(self):
		"""This phase changes what a service does and nothing about how a request is matched.
		A lost `tls: {}` is a TLS outage and a changed rule is a bench nobody can reach."""
		self.assertEqual(
			self._config()["http"]["routers"],
			{
				"site-inst-1": {
					"rule": "Host(`inst-1.benchpress.cloud`)",
					"entryPoints": ["websecure"],
					"priority": ingress.ROUTER_PRIORITY,
					"service": "site-inst-1",
					"middlewares": ["inst-1-rl-site"],
					"tls": {},
				},
				"assets-inst-1": {
					"rule": "Host(`inst-1.benchpress.cloud`) && (PathPrefix(`/assets`) || PathPrefix(`/files`))",
					"entryPoints": ["websecure"],
					"priority": ingress.ASSETS_ROUTER_PRIORITY,
					"service": "site-inst-1",
					"middlewares": ["inst-1-rl-assets"],
					"tls": {},
				},
				"ide-inst-1": {
					"rule": "Host(`ide-inst-1.benchpress.cloud`)",
					"entryPoints": ["websecure"],
					"priority": ingress.ROUTER_PRIORITY,
					"service": "ide-inst-1",
					"middlewares": ["inst-1-rl-ide"],
					"tls": {},
				},
			},
		)


class TestIdeRouter(IntegrationTestCase):
	"""Whether `ide-<id>` exists at all — see specs/…/phase-3-code-server-router.md.

	The live bug: `enable_code_server` gated the process and nothing else, so a lab with the
	IDE off still published a public hostname pointing at a port nothing listens on.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# Resources no seeded size claims, so `size_for_lab`'s by-resources rung cannot pick
		# one of these by accident.
		cls.ide_size = _make_size("Phase Three IDE", 1, "777m")
		cls.no_ide_size = _make_size("Phase Three No IDE", 0, "778m")
		cls.lab = _make_lab("test-lab-ide-router")
		# A second lab, because one bench exists per (user, lab) and the fleet read has to be
		# shown resolving more than one bench in the same query.
		cls.other_lab = _make_lab("test-lab-ide-router-other")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for lab in (cls.lab, cls.other_lab):
			for name in frappe.get_all("Bench Instance", filters={"lab": lab.name}, pluck="name"):
				frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
			lab.delete(ignore_permissions=True)
		for size in (cls.ide_size, cls.no_ide_size):
			frappe.delete_doc("Instance Size", size.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		clear_size_index()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		clear_size_index()

	def _bench(self, *, lab_size, lab_flag=1, bench_size=None, lab=None):
		lab_name = (lab or self.lab).name
		frappe.db.set_value("Lab", lab_name, {"instance_size": lab_size, "enable_code_server": lab_flag})
		bench = _fresh_bench(self, lab_name)
		bench.status = "Running"
		bench.container_ip = "172.30.0.21"
		bench.instance_size = bench_size
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		return bench

	def _http(self, target_dir, bench):
		return yaml.safe_load((target_dir / f"{bench.name}.yml").read_text())["http"]

	def _assert_site_only(self, target_dir, bench):
		text = (target_dir / f"{bench.name}.yml").read_text()
		http = yaml.safe_load(text)["http"]
		self.assertEqual(set(http["routers"]), {f"site-{bench.name}", f"assets-{bench.name}"})
		self.assertEqual(set(http["services"]), {f"site-{bench.name}"})
		# No router and no service, so Traefik matches nothing and answers 404 rather than
		# the 502 a router pointing at a dead port would give.
		self.assertNotIn("ide-", text)

	def test_a_bench_with_an_ide_gets_both_routers(self):
		bench = self._bench(lab_size=self.ide_size.name)

		with _route_dir() as (ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")
			http = self._http(target_dir, bench)

		self.assertEqual(
			set(http["routers"]),
			{f"site-{bench.name}", f"assets-{bench.name}", f"ide-{bench.name}"},
		)
		self.assertEqual(set(http["services"]), {f"site-{bench.name}", f"ide-{bench.name}"})

	def test_a_lab_with_code_server_off_publishes_no_ide_hostname(self):
		bench = self._bench(lab_size=self.ide_size.name, lab_flag=0)

		with _route_dir() as (ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")

			self._assert_site_only(target_dir, bench)

	def test_a_size_with_code_server_off_publishes_no_ide_hostname(self):
		bench = self._bench(lab_size=self.no_ide_size.name)

		with _route_dir() as (ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")

			self._assert_site_only(target_dir, bench)

	def test_the_size_the_bench_deployed_at_beats_the_labs_current_one(self):
		"""Billing prices the recorded size, and the routers follow the same rule: re-pointing
		a Lab must not change what a bench that is already running publishes."""
		bench = self._bench(lab_size=self.ide_size.name, bench_size=self.no_ide_size.name)

		with _route_dir() as (ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")

			self._assert_site_only(target_dir, bench)

	def test_the_reconcile_writes_the_same_bytes_the_deploy_wrote(self):
		"""The derivability assertion, and nothing else catches it: the `*/5` pass has none of
		the deploy's context, so a flag it resolved differently rewrites this file every pass —
		and Traefik reloads on mtime."""
		for size, routers in ((self.ide_size.name, 3), (self.no_ide_size.name, 2)):
			with self.subTest(size=size):
				bench = self._bench(lab_size=size)

				with _route_dir() as (ingress, target_dir):
					ingress.publish(bench.name, "benchpress.cloud")
					route = target_dir / f"{bench.name}.yml"
					deployed = route.read_bytes()
					mtime = route.stat().st_mtime_ns

					ingress.reconcile()

					self.assertEqual(route.read_bytes(), deployed)
					self.assertEqual(route.stat().st_mtime_ns, mtime)

				self.assertEqual(len(yaml.safe_load(deployed)["http"]["routers"]), routers)

	def test_the_flag_is_resolved_in_the_fleet_read(self):
		"""One query for every bench: resolving per bench would cost the `*/5` pass one query
		each, which is 300 a pass at the load profile this exists for."""
		self._bench(lab_size=self.ide_size.name)
		self._bench(lab_size=self.no_ide_size.name, lab=self.other_lab)

		with _route_dir() as (ingress, _target_dir):
			with patch.object(ingress, "_fleet_rows", wraps=ingress._fleet_rows) as fleet_rows:
				result = ingress.reconcile()

		self.assertEqual(fleet_rows.call_count, 1)
		self.assertGreaterEqual(result["written"], 2)

	def test_a_lab_answers_the_same_rule_before_any_bench_exists(self):
		"""The Lab detail screen has no bench to ask about and must not offer an IDE row for a
		size that has none."""
		frappe.db.set_value(
			"Lab", self.lab.name, {"instance_size": self.no_ide_size.name, "enable_code_server": 1}
		)

		self.assertFalse(ingress.lab_has_ide(frappe.get_doc("Lab", self.lab.name)))

		frappe.db.set_value("Lab", self.lab.name, "instance_size", self.ide_size.name)

		self.assertTrue(ingress.lab_has_ide(frappe.get_doc("Lab", self.lab.name)))


class TestPathSplitAndRateLimits(IntegrationTestCase):
	"""The render/assets split and the rate limit each router carries.

	The path this guards is a *missing* `/assets` file, which renders a full 404 page.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		# Numbers no tier would pick, so a hardcoded 20/60 cannot pass this by accident.
		cls.tuned_size = _make_size("Rate Limit Tuned", 1, "781m", rate_average=7, rate_burst=9)
		# Zero is what a row that predates the fields reads back as, and Traefik reads
		# `average: 0` as no limit at all.
		cls.unseeded_size = _make_size("Rate Limit Unseeded", 0, "782m", rate_average=0, rate_burst=0)
		cls.lab = _make_lab("test-lab-rate-limits")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		for size in (cls.tuned_size, cls.unseeded_size):
			frappe.delete_doc("Instance Size", size.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		clear_size_index()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		clear_size_index()

	def _bench(self, lab_size):
		frappe.db.set_value("Lab", self.lab.name, {"instance_size": lab_size, "enable_code_server": 1})
		bench = _fresh_bench(self, self.lab.name)
		bench.status = "Running"
		bench.container_ip = "172.30.0.22"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		return bench

	@contextmanager
	def _published(self, lab_size=None):
		"""One bench of `lab_size`, and the `http` block its deploy wrote."""
		bench = self._bench(lab_size or self.tuned_size.name)
		with _route_dir() as (published_ingress, target_dir):
			published_ingress.publish(bench.name, "benchpress.cloud")
			http = yaml.safe_load((target_dir / f"{bench.name}.yml").read_text())["http"]
			yield bench, http

	def test_the_assets_router_outranks_the_site_router(self):
		"""The bare host rule matches an `/assets` request too, so the split is only real while
		the assets router out-ranks it — and a lost split looks exactly like a working one."""
		with self._published() as (bench, http):
			assets = http["routers"][f"assets-{bench.name}"]["priority"]
			site = http["routers"][f"site-{bench.name}"]["priority"]

		self.assertGreater(assets, site)

	def test_the_assets_router_takes_the_paths_that_render_nothing(self):
		"""`/private/files` is deliberately absent — it needs a permission check, and it is not
		matched by `PathPrefix(/files)` anyway."""
		with self._published() as (bench, http):
			rule = http["routers"][f"assets-{bench.name}"]["rule"]

		self.assertEqual(
			rule,
			f"Host(`{bench.name}.benchpress.cloud`) && (PathPrefix(`/assets`) || PathPrefix(`/files`))",
		)
		self.assertNotIn("/private/files", rule)

	def test_both_routers_name_the_one_service(self):
		"""There is one bench behind both. A second service would be a second health check on
		the same container, and an assets router pointing anywhere else is a 502."""
		with self._published() as (bench, http):
			self.assertEqual(
				{http["routers"][name]["service"] for name in (f"site-{bench.name}", f"assets-{bench.name}")},
				{f"site-{bench.name}"},
			)
			self.assertEqual(set(http["services"]), {f"site-{bench.name}", f"ide-{bench.name}"})

	def test_each_router_carries_one_middleware_of_its_own_name(self):
		"""A limiter instance is per router, so a shared name would hide the doubling rather
		than remove it — and would make the two paths impossible to tune apart."""
		with self._published() as (bench, http):
			carried = {name: router["middlewares"] for name, router in http["routers"].items()}
			defined = set(http["middlewares"])

		self.assertEqual(
			carried,
			{
				f"site-{bench.name}": [f"{bench.name}-rl-site"],
				f"assets-{bench.name}": [f"{bench.name}-rl-assets"],
				f"ide-{bench.name}": [f"{bench.name}-rl-ide"],
			},
		)
		# Defined in the same file that references them: Traefik drops a router naming a
		# middleware it cannot resolve, and a dropped router is a bench nobody can reach.
		self.assertEqual(defined, {name for names in carried.values() for name in names})

	def test_the_assets_middleware_is_a_rate_limit_and_nothing_else(self):
		"""No `inFlightReq` here, ever: one tab pulls nine same-host assets, so any cap low
		enough to bind would 429 a single user loading their own page."""
		with self._published() as (bench, http):
			self.assertEqual(set(http["middlewares"][f"{bench.name}-rl-assets"]), {"rateLimit"})

	def test_every_rate_limit_buckets_on_the_address_cloudflare_saw(self):
		"""`depth` counts from the right, and a client-supplied `X-Forwarded-For` arrives to the
		left of the real address — so 2 is spoofable and the literal 1 is the security property."""
		with self._published() as (_bench, http):
			depths = [
				middleware["rateLimit"]["sourceCriterion"]["ipStrategy"]["depth"]
				for middleware in http["middlewares"].values()
			]

		self.assertEqual(depths, [1, 1, 1])

	def test_the_rate_numbers_come_from_the_tier(self):
		with self._published() as (bench, http):
			limit = http["middlewares"][f"{bench.name}-rl-site"]["rateLimit"]

		self.assertEqual((limit["average"], limit["burst"]), (7, 9))

	def test_an_unseeded_tier_gets_the_floor_rather_than_no_limit(self):
		"""Traefik reads `average: 0` as the brake off, so a row nobody seeded must not publish
		its zero — the failure would be an unguarded route that looks configured."""
		with self._published(self.unseeded_size.name) as (bench, http):
			limit = http["middlewares"][f"{bench.name}-rl-site"]["rateLimit"]

		self.assertEqual(
			(limit["average"], limit["burst"]),
			(ingress.DEFAULT_RATE_AVERAGE, ingress.DEFAULT_RATE_BURST),
		)

	def test_the_reconcile_writes_the_tier_numbers_the_deploy_wrote(self):
		"""The derivability assertion for the new values: the `*/5` pass has none of the deploy's
		context, so a rate it resolved differently rewrites this file every pass."""
		bench = self._bench(self.tuned_size.name)

		with _route_dir() as (published_ingress, target_dir):
			published_ingress.publish(bench.name, "benchpress.cloud")
			route = target_dir / f"{bench.name}.yml"
			deployed = route.read_bytes()
			mtime = route.stat().st_mtime_ns

			published_ingress.reconcile()

			self.assertEqual(route.read_bytes(), deployed)
			self.assertEqual(route.stat().st_mtime_ns, mtime)

		self.assertIn(b"average: 7", deployed)

	def test_the_fleet_read_still_resolves_everything_in_one_query(self):
		"""The rates are per tier, so a per-bench read for them would cost the `*/5` pass one
		query each — 300 a pass at the load profile this exists for."""
		self._bench(self.tuned_size.name)

		with _route_dir() as (published_ingress, _target_dir):
			with patch.object(
				published_ingress, "_fleet_rows", wraps=published_ingress._fleet_rows
			) as fleet_rows:
				published_ingress.reconcile()

		self.assertEqual(fleet_rows.call_count, 1)


class TestInFlightCap(IntegrationTestCase):
	"""The render router's `inFlightReq` and the clamp over it — see phase-2-inflight.md.

	The cap exists so one saturated bench queues its own requests instead of holding an
	unbounded share of the shared MariaDB connection pool.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.capped_size = _make_size("In Flight Capped", 1, "783m", inflight_limit=16)
		# `Instance Size` is admin-editable, so the realistic bad value is a typo'd row rather
		# than a hand-written route file — which the */5 reconcile overwrites anyway.
		cls.typo_size = _make_size("In Flight Typo", 1, "784m", inflight_limit=999)
		cls.unseeded_size = _make_size("In Flight Unseeded", 1, "785m", inflight_limit=0)
		cls.lab = _make_lab("test-lab-inflight")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		for size in (cls.capped_size, cls.typo_size, cls.unseeded_size):
			frappe.delete_doc("Instance Size", size.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		clear_size_index()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		clear_size_index()

	@contextmanager
	def _published(self, lab_size):
		"""One bench of `lab_size`, and the `http` block its deploy wrote."""
		frappe.db.set_value("Lab", self.lab.name, {"instance_size": lab_size, "enable_code_server": 1})
		bench = _fresh_bench(self, self.lab.name)
		bench.status = "Running"
		bench.container_ip = "172.30.0.23"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		with _route_dir() as (published_ingress, target_dir):
			published_ingress.publish(bench.name, "benchpress.cloud")
			yield bench, yaml.safe_load((target_dir / f"{bench.name}.yml").read_text())["http"]

	def test_the_cap_lands_on_the_render_router_and_nowhere_else(self):
		"""One tab pulls nine same-host assets, so a cap on `assets-` would 429 a single user;
		code-server holds one upgraded connection per session, so a cap on `ide-` counts
		sessions. The rate limit is listed first so a refused request takes no slot."""
		with self._published(self.capped_size.name) as (bench, http):
			carried = {name: router["middlewares"] for name, router in http["routers"].items()}
			# Traefik drops a router naming a middleware it cannot resolve, and a dropped
			# router is a bench nobody can reach.
			defined = set(http["middlewares"])

		self.assertEqual(
			carried,
			{
				f"site-{bench.name}": [f"{bench.name}-rl-site", f"{bench.name}-inflight"],
				f"assets-{bench.name}": [f"{bench.name}-rl-assets"],
				f"ide-{bench.name}": [f"{bench.name}-rl-ide"],
			},
		)
		self.assertEqual(defined, {name for names in carried.values() for name in names})

	def test_the_amount_is_the_tier_number(self):
		with self._published(self.capped_size.name) as (bench, http):
			cap = http["middlewares"][f"{bench.name}-inflight"]

		self.assertEqual(cap["inFlightReq"]["amount"], 16)

	def test_a_typod_tier_cannot_exceed_the_ceiling(self):
		"""The clamp is the whole reason the ceiling is a module constant: 151 shared database
		connections divided by 24 is about the number of saturated benches this host holds."""
		with self._published(self.typo_size.name) as (bench, http):
			amount = http["middlewares"][f"{bench.name}-inflight"]["inFlightReq"]["amount"]

		self.assertEqual(amount, 24)
		self.assertEqual(amount, ingress.INFLIGHT_CEILING)

	def test_an_unseeded_tier_gets_no_cap_rather_than_a_default(self):
		"""Unlike the rate numbers, which have a floor. A row nobody seeded is an operator who
		has not chosen yet, and imposing 4 on every bench the day this ships would be a
		capacity change nobody asked for."""
		with self._published(self.unseeded_size.name) as (bench, http):
			self.assertEqual(http["routers"][f"site-{bench.name}"]["middlewares"], [f"{bench.name}-rl-site"])
			self.assertNotIn(f"{bench.name}-inflight", http["middlewares"])

	def test_the_cap_carries_no_source_criterion_at_all(self):
		"""`site-<id>` matches exactly one host, so the router is already the bucket. A
		`sourceCriterion` would only split the one count across two limiter instances."""
		with self._published(self.capped_size.name) as (bench, http):
			cap = http["middlewares"][f"{bench.name}-inflight"]

		self.assertEqual(cap, {"inFlightReq": {"amount": 16}})


class TestWildcardAnchor(unittest.TestCase):
	"""`ensure_anchor` — the one place in this app that names a resolver.

	See specs/completed/wildcard-cert-routing/phase-1-resolver-free-routers.md.
	"""

	@contextmanager
	def _anchor_dir(self, mounted=True):
		"""`mounted=False` leaves the directory absent — the dev-checkout shape."""
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = _mounted(tmp) if mounted else Path(tmp) / "instances"
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
				yield target_dir

	def test_anchor_names_one_identity_set(self):
		"""`domains` is fixed, so the resolver is asked for exactly one identity set no
		matter which SNI arrives — a resolver without it issues per-SNI on demand."""
		with self._anchor_dir() as target_dir:
			self.assertTrue(ingress.ensure_anchor("benchpress.cloud"))

			files = sorted(p.name for p in target_dir.iterdir())
			self.assertEqual(files, ["wildcard-anchor.yml"])

			config = yaml.safe_load((target_dir / "wildcard-anchor.yml").read_text())
			router = config["http"]["routers"]["benchpress-wildcard-anchor"]
			self.assertEqual(router["tls"]["certResolver"], "letsencrypt")
			self.assertEqual(
				router["tls"]["domains"],
				[{"main": "benchpress.cloud", "sans": ["*.benchpress.cloud"]}],
			)
			# 0 is ignored by Traefik, so 1 is the floor — and every instance rule is
			# 40+ characters, so the anchor can never win a tie on rule length.
			self.assertEqual(router["priority"], 1)
			self.assertEqual(router["service"], "benchpress-wildcard-anchor")
			self.assertIn("benchpress-wildcard-anchor", config["http"]["services"])

	def test_anchor_leaves_no_temp_file_behind(self):
		"""The anchor is what keeps the certificate renewing, so a truncated read of it is
		worse than a truncated read of any bench route."""
		with self._anchor_dir() as target_dir:
			ingress.ensure_anchor("benchpress.cloud")

			self.assertEqual([p.name for p in target_dir.iterdir()], ["wildcard-anchor.yml"])

	def test_anchor_is_not_rewritten_when_unchanged(self):
		"""Traefik reloads on mtime, so a deploy that changes nothing must not touch it."""
		with self._anchor_dir() as target_dir:
			ingress.ensure_anchor("benchpress.cloud")
			anchor = target_dir / "wildcard-anchor.yml"
			mtime = anchor.stat().st_mtime_ns

			self.assertFalse(ingress.ensure_anchor("benchpress.cloud"))

			self.assertEqual(anchor.stat().st_mtime_ns, mtime)

	def test_anchor_is_rewritten_in_place_for_a_new_domain(self):
		"""A changed `base_domain` replaces the anchor rather than adding a second one —
		two anchors would be two identity sets against the weekly budget."""
		with self._anchor_dir() as target_dir:
			ingress.ensure_anchor("benchpress.cloud")

			self.assertTrue(ingress.ensure_anchor("example.com"))

			files = sorted(p.name for p in target_dir.iterdir())
			self.assertEqual(files, ["wildcard-anchor.yml"])
			config = yaml.safe_load((target_dir / "wildcard-anchor.yml").read_text())
			router = config["http"]["routers"]["benchpress-wildcard-anchor"]
			self.assertEqual(router["rule"], "Host(`tls-anchor.example.com`)")
			self.assertEqual(
				router["tls"]["domains"],
				[{"main": "example.com", "sans": ["*.example.com"]}],
			)

	def test_anchor_no_ops_without_a_public_domain(self):
		"""A dev checkout is byte-for-byte unaffected: skipped silently, not attempted
		and failed. Runs unmounted, so it also proves the return beats the guard."""
		for base_domain in (None, "", "localhost"):
			with (
				self.subTest(base_domain=base_domain),
				self._anchor_dir(mounted=False) as target_dir,
			):
				self.assertFalse(ingress.ensure_anchor(base_domain))

				self.assertFalse(target_dir.exists())


class TestRouteDirectoryGuard(unittest.TestCase):
	"""A routing write from a container without the mount fails loudly.

	See specs/in-progress/restart-free-dynamic-routing/phase-3-invariant-and-convergence.md.
	"""

	@contextmanager
	def _unmounted(self):
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = Path(tmp) / "dynamic"
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
				yield target_dir

	def test_writing_a_route_without_the_mount_raises_and_creates_nothing(self):
		"""Creating the directory is the defect being replaced: the file then lands in this
		container's own filesystem, which is the same outcome with none of the evidence."""
		with self._unmounted() as target_dir:
			with self.assertRaises(ingress.TraefikRouteDirectoryMissing):
				ingress.publish("inst-1", "benchpress.cloud")

			self.assertFalse(target_dir.exists())

	def test_the_anchor_write_is_guarded_too(self):
		"""Both writers go through `_atomic_write`, so the guard cannot drift between them."""
		with self._unmounted() as target_dir:
			with self.assertRaises(ingress.TraefikRouteDirectoryMissing):
				ingress.ensure_anchor("benchpress.cloud")

			self.assertFalse(target_dir.exists())

	def test_the_error_names_the_queue_that_has_the_mount(self):
		"""The whole value of a custom exception here: a bare `FileNotFoundError` leaves the
		reader to rediscover the mount topology from a traceback that shows none of it."""
		with self._unmounted() as _target_dir:
			with self.assertRaises(ingress.TraefikRouteDirectoryMissing) as raised:
				ingress.publish("inst-1", "benchpress.cloud")

		self.assertIn("queue-long", str(raised.exception))
		self.assertIn("enqueue_route_sync", str(raised.exception))


class TestDirectoryReads(unittest.TestCase):
	"""`published` / `protected_present` — the reads that keep the path in this module.

	A caller that learned the directory and the protected names could take the control
	plane off the internet through one off-by-one, so both are calls, not constants.
	"""

	@contextmanager
	def _dir_holding(self, *names):
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = _mounted(tmp)
			for name in names:
				(target_dir / name).write_text("")
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
				yield target_dir

	def test_published_names_instances_and_never_a_protected_file(self):
		with self._dir_holding("dynamic.yml", "wildcard-anchor.yml", "inst-1.yml"):
			self.assertEqual(ingress.published(), {"inst-1"})

	def test_published_is_empty_on_an_empty_directory(self):
		with self._dir_holding():
			self.assertEqual(ingress.published(), set())

	def test_protected_present_counts_both_files(self):
		with self._dir_holding("dynamic.yml", "wildcard-anchor.yml", "inst-1.yml"):
			self.assertEqual(ingress.protected_present(), 2)

	def test_protected_present_drops_to_one_when_the_control_plane_router_goes_missing(self):
		"""The only check in this app that would notice `dynamic.yml` disappearing."""
		with self._dir_holding("wildcard-anchor.yml"):
			self.assertEqual(ingress.protected_present(), 1)


class TestCertificateVerification(unittest.TestCase):
	"""`log_certificate_state` / `_certificate_error` — phase 2.

	The check reports, it never acts and never raises. No test here opens a socket: the
	unit under test is the reporting, and a test that needed a running Traefik would fail
	for reasons that have nothing to do with the code.

	See specs/completed/wildcard-cert-routing/phase-2-certificate-verification.md.
	"""

	def _pipeline(self):
		pipeline = MagicMock()
		pipeline.logged = []
		pipeline.log.side_effect = lambda line, *args, **kwargs: pipeline.logged.append(line)
		return pipeline

	def test_a_healthy_certificate_is_stated_by_name(self):
		"""Naming the wildcard is the point: it says the bench is served by the anchor's
		certificate rather than by one of its own."""
		pipeline = self._pipeline()
		with patch.object(ingress, "_certificate_error", autospec=True, return_value=None):
			ingress.log_certificate_state("inst-1", "benchpress.cloud", pipeline)

		self.assertEqual(
			pipeline.logged,
			["TLS ready for inst-1.benchpress.cloud on the *.benchpress.cloud wildcard"],
		)

	def test_a_certificate_problem_warns_and_does_not_raise(self):
		"""The whole contract. A check that raised would turn a cosmetic problem into a
		failed deploy, for a bench whose container is up and whose site exists."""
		pipeline = self._pipeline()
		with patch.object(
			ingress,
			"_certificate_error",
			autospec=True,
			return_value="certificate does not cover inst-1.benchpress.cloud (hostname mismatch)",
		):
			ingress.log_certificate_state("inst-1", "benchpress.cloud", pipeline)

		self.assertEqual(len(pipeline.logged), 1)
		self.assertIn("WARNING: certificate does not cover inst-1.benchpress.cloud", pipeline.logged[0])
		self.assertIn("the public URL will fail in a browser", pipeline.logged[0])

	def test_only_the_site_hostname_is_checked(self):
		"""The IDE hostname is one label under the same `base_domain`, so the same wildcard
		covers it — a second handshake would only re-prove the first."""
		with patch.object(ingress, "_certificate_error", autospec=True, return_value=None) as mock_check:
			ingress.log_certificate_state("inst-1", "benchpress.cloud", self._pipeline())

		mock_check.assert_called_once_with("inst-1.benchpress.cloud")

	def test_no_check_and_no_line_without_a_public_domain(self):
		"""A dev checkout is byte-for-byte unaffected — no socket, no log line. Matches
		`publish` and `ensure_anchor`."""
		for base_domain in (None, "", "localhost"):
			with self.subTest(base_domain=base_domain):
				pipeline = self._pipeline()
				with patch.object(ingress, "_certificate_error", autospec=True) as mock_check:
					ingress.log_certificate_state("inst-1", base_domain, pipeline)

				mock_check.assert_not_called()
				self.assertEqual(pipeline.logged, [])

	def test_an_unreachable_traefik_is_not_reported_as_a_bad_certificate(self):
		"""The two causes call for different actions, so they must stay apart in a log
		someone reads at 2am: one means fix the certificate, the other means Traefik is
		down — or that there is no Traefik, which is the dev-checkout case."""
		with patch.object(ingress.socket, "create_connection", autospec=True, side_effect=OSError("refused")):
			error = ingress._certificate_error("inst-1.benchpress.cloud")

		self.assertIn("could not reach Traefik to check inst-1.benchpress.cloud", error)
		self.assertNotIn("does not cover", error)

	def test_a_hostname_the_certificate_misses_is_named(self):
		"""The 526 this feature exists to prevent, caught at deploy time and named."""
		failure = ssl.SSLCertVerificationError("hostname mismatch")
		failure.verify_message = "Hostname mismatch, certificate is not valid for 'nope.example.com'"

		with patch.object(ingress.socket, "create_connection", autospec=True, side_effect=failure):
			error = ingress._certificate_error("nope.example.com")

		self.assertIn("certificate does not cover nope.example.com", error)
		self.assertIn("Hostname mismatch", error)

	def test_a_verification_error_without_a_verify_message_still_reports(self):
		"""`verify_message` is set by the C module on a real handshake failure and is absent
		otherwise, so reading it bare would raise out of the handler — reporting the
		exception itself keeps the failure a warning."""
		with patch.object(
			ingress.socket,
			"create_connection",
			autospec=True,
			side_effect=ssl.SSLCertVerificationError("no verify_message here"),
		):
			error = ingress._certificate_error("nope.example.com")

		self.assertIn("certificate does not cover nope.example.com", error)
		self.assertIn("no verify_message here", error)

	def test_a_usable_certificate_reports_nothing(self):
		"""None is the healthy answer — the caller logs the success line off the absence.

		The context is mocked alongside the socket because a real `SSLContext` handed a mock
		socket fails on the mock, not on the certificate.
		"""
		with (
			patch.object(ingress.socket, "create_connection", autospec=True),
			patch.object(ingress.ssl, "create_default_context", autospec=True),
		):
			self.assertIsNone(ingress._certificate_error("inst-1.benchpress.cloud"))


@contextmanager
def _route_dir(base_domain="benchpress.cloud"):
	"""A tmp route directory, with `base_domain` supplied rather than read from live settings.

	The settings doc is patched, never saved: saving it on a real host would re-anchor the
	certificate for whatever value a test happened to pick.
	"""
	with tempfile.TemporaryDirectory() as tmp:
		target_dir = Path(tmp) / "dynamic"
		target_dir.mkdir()
		with (
			patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir),
			patch("frappe.get_cached_doc", return_value=frappe._dict(base_domain=base_domain)),
		):
			yield ingress, target_dir


class TestRouteConvergenceSchedule(unittest.TestCase):
	"""The `*/5` convergence tick — see phase-3-invariant-and-convergence.md."""

	def test_the_tick_hands_the_pass_to_the_long_queue(self):
		from benchpress.ingress import enqueue_route_reconcile

		with patch("frappe.enqueue") as enqueue:
			enqueue_route_reconcile()

		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], "benchpress.ingress.reconcile")
		self.assertEqual(kwargs["queue"], "long")
		# Fixed, so a pass running longer than the interval does not queue behind itself.
		self.assertEqual(kwargs["job_id"], "route_reconcile")
		self.assertTrue(kwargs["deduplicate"])

	def test_the_cron_entry_is_the_enqueuer_and_never_the_pass(self):
		"""Frappe sends cron to `default`, which `queue-short` also consumes — and that
		container has no route mount, so the pass itself would raise every five minutes."""
		from benchpress.hooks import scheduler_events

		cron_methods = [method for methods in scheduler_events["cron"].values() for method in methods]

		self.assertIn(
			"benchpress.ingress.enqueue_route_reconcile",
			scheduler_events["cron"]["*/5 * * * *"],
		)
		self.assertNotIn("benchpress.ingress.reconcile", cron_methods)


class TestReconcileInstanceRoutes(IntegrationTestCase):
	"""`reconcile` — the route directory converges on the database.

	See specs/completed/wildcard-cert-routing/phase-3-route-convergence.md.
	"""

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
		with _route_dir() as (ingress, target_dir):
			orphan = self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")

			result = ingress.reconcile()

			self.assertFalse(orphan.exists())
			self.assertGreaterEqual(result["deleted"], 1)

	def test_a_bench_that_is_not_running_loses_its_route_file(self):
		"""A stopped bench's recorded IP is an address Docker has already handed back, so the
		file is not a dead link — it is the next bench's hostname collision."""
		for status in ("Stopped", "Draft", "Error"):
			with self.subTest(status=status):
				bench = self._bench(status, "172.30.0.11")
				with _route_dir() as (ingress, target_dir):
					route_file = self._seed(target_dir, f"{bench.name}.yml")

					ingress.reconcile()

					self.assertFalse(route_file.exists())

	def test_a_running_bench_route_is_rewritten_to_name_its_container(self):
		"""Convergence, not merely reaping: a file that survives must also be right. Seeded with
		an address backend so passing means the pass rewrote it to the container name."""
		bench = self._bench("Running", "172.30.0.12")

		with _route_dir() as (ingress, target_dir):
			self._seed(target_dir, f"{bench.name}.yml", "http://172.30.0.99:8000\n")

			result = ingress.reconcile()

			written_text = (target_dir / f"{bench.name}.yml").read_text()
			config = yaml.safe_load(written_text)
			backends = [
				server["url"]
				for service in config["http"]["services"].values()
				for server in service["loadBalancer"]["servers"]
			]
			self.assertIn(f"http://{bench.name}:8000", backends)
			self.assertNotRegex(written_text, IPV4_IN_TEXT)
			self.assertGreaterEqual(result["written"], 1)

	def test_the_control_plane_router_and_the_anchor_survive_a_full_sweep(self):
		"""The guard that stops this pass taking the platform off the internet. `dynamic.yml` is
		the control plane's own router and the anchor is every bench's certificate; a run that
		deletes every instance file must still leave both."""
		with _route_dir() as (ingress, target_dir):
			control_plane = self._seed(target_dir, "dynamic.yml", "control plane\n")
			ingress.ensure_anchor("benchpress.cloud")
			anchor = target_dir / "wildcard-anchor.yml"
			anchor_text = anchor.read_text()
			self._seed(target_dir, "16b283bccf6560ab1aa5f078d492d005.yml")
			self._seed(target_dir, "5dc12efd9c154796adae757adec1b2f3.yml")

			result = ingress.reconcile()

			self.assertEqual(control_plane.read_text(), "control plane\n")
			self.assertEqual(anchor.read_text(), anchor_text)
			self.assertEqual(result["kept"], 2)

	def test_a_run_always_leaves_the_certificate_anchored(self):
		"""The anchor is what holds the wildcard the resolver-free bench routers serve, so the
		pass writes it first rather than waiting for the next deploy."""
		with _route_dir() as (ingress, target_dir):
			result = ingress.reconcile()

			self.assertTrue(result["anchored"])
			config = yaml.safe_load((target_dir / "wildcard-anchor.yml").read_text())
			router = config["http"]["routers"]["benchpress-wildcard-anchor"]
			self.assertEqual(router["rule"], "Host(`tls-anchor.benchpress.cloud`)")

	def test_the_returned_counts_match_what_happened_on_disk(self):
		"""A reaper that reports what it attempted rather than what converged is how a directory
		drifts for weeks without anyone noticing."""
		bench = self._bench("Running", "172.30.0.13")

		with _route_dir() as (ingress, target_dir):
			self._seed(target_dir, "dynamic.yml", "control plane\n")
			self._seed(target_dir, f"{bench.name}.yml")
			self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")
			self._seed(target_dir, "5dc12efd9c154796adae757adec1b2f3.yml")

			result = ingress.reconcile()

			self.assertEqual(result["deleted"], 2)
			self.assertEqual(result["kept"], 2)
			self.assertEqual(result["written"], len(self._instance_files(target_dir)))
			self.assertIn(f"{bench.name}.yml", self._instance_files(target_dir))

	def test_a_second_run_deletes_nothing_and_touches_nothing(self):
		"""Idempotence is the read side agreeing with the write side. A pass that keeps finding
		things to delete is one that disagrees with the files it just wrote — and one that
		rewrites unchanged files is a Traefik reload every five minutes, since it reloads on
		mtime."""
		self._bench("Running", "172.30.0.14")

		with _route_dir() as (ingress, target_dir):
			self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")
			ingress.reconcile()
			before = {p.name: p.stat().st_mtime_ns for p in target_dir.iterdir()}

			result = ingress.reconcile()

			self.assertEqual(result["deleted"], 0)
			self.assertFalse(result["anchored"])
			self.assertEqual({p.name: p.stat().st_mtime_ns for p in target_dir.iterdir()}, before)

	def test_a_container_without_the_route_mount_reports_instead_of_raising(self):
		"""Only `queue-long` mounts the directory, so a by-hand run anywhere else used to do
		the bridge half and then raise out of `ensure_anchor`."""
		with tempfile.TemporaryDirectory() as tmp:
			with (
				patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", Path(tmp) / "dynamic"),
				patch("frappe.get_cached_doc", return_value=frappe._dict(base_domain="benchpress.cloud")),
				patch("benchpress.placement.repair", return_value={"attached": {}, "missing": {}}),
			):
				result = ingress.reconcile()

		# None, not 0: nothing was read, and zero counts are what a converged pass reports.
		self.assertEqual(
			result,
			{
				"anchored": None,
				"written": None,
				"deleted": None,
				"kept": None,
				"attached": {},
				"missing": {},
			},
		)

	def test_reconcile_writes_nothing_at_all_without_a_public_domain(self):
		"""A dev checkout must be byte-for-byte unaffected — and must not reap either, since a
		directory it never writes is not a directory it understands."""
		for base_domain in (None, "", "localhost"):
			with (
				self.subTest(base_domain=base_domain),
				_route_dir(base_domain) as (
					ingress,
					target_dir,
				),
			):
				survivor = self._seed(target_dir, "091131f54bcdfc7bc37cbc45763547fa.yml")

				result = ingress.reconcile()

				self.assertTrue(survivor.exists())
				self.assertEqual(
					result,
					{"anchored": False, "written": 0, "deleted": 0, "kept": 0, "attached": {}, "missing": {}},
				)


class TestSettingsReAnchor(IntegrationTestCase):
	"""`BenchPress Settings.on_update` hands the sweep to the worker that can do it.

	`on_update` is called directly on an unsaved document. Saving the real Single would write
	a domain to a live host, and the whole point of the controller is that it does not do the
	work itself — what needs asserting is which queue it hands it to.
	"""

	def _settings(self, previous_domain):
		settings = frappe.get_doc("BenchPress Settings")
		settings._doc_before_save = frappe._dict(base_domain=previous_domain)
		return settings

	def test_a_changed_base_domain_enqueues_the_sweep_on_the_long_queue(self):
		"""`queue-long` is the only worker that mounts the route directory. A sweep on any other
		queue writes into that container's own filesystem, and Traefik never sees it."""
		settings = self._settings("some-other-zone.example")

		with patch("frappe.enqueue") as enqueue:
			settings.on_update()

		enqueue.assert_called_once()
		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], "benchpress.ingress.reconcile")
		self.assertEqual(kwargs["queue"], "long")
		# The job re-reads `base_domain`, so it must not start before the new value is committed.
		self.assertTrue(kwargs["enqueue_after_commit"])

	def test_an_unrelated_settings_save_enqueues_nothing(self):
		"""A toggle or a timeout is not a reason to sweep the route directory."""
		settings = self._settings(frappe.get_cached_doc("BenchPress Settings").base_domain)

		with patch("frappe.enqueue") as enqueue:
			settings.on_update()

		enqueue.assert_not_called()


class TestSyncInstanceRoute(IntegrationTestCase):
	"""`sync_instance_route` — the route directory agrees with one bench's status.

	See specs/in-progress/restart-free-dynamic-routing/phase-2-status-driven-route-sync.md.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-sync-route")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _bench(self, status):
		bench = _fresh_bench(self, self.lab.name)
		bench.status = status
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		return bench

	def test_a_running_bench_gets_its_route_file(self):
		bench = self._bench("Running")

		with _route_dir() as (ingress, target_dir):
			result = ingress.sync_instance_route(bench.name)

			self.assertEqual(result, "written")
			self.assertTrue((target_dir / f"{bench.name}.yml").exists())

	def test_a_stopped_bench_loses_its_route_file(self):
		"""The live misroute closes here: a stopped bench's hostname must stop answering."""
		bench = self._bench("Stopped")

		with _route_dir() as (ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")
			route_file = target_dir / f"{bench.name}.yml"
			self.assertTrue(route_file.exists())

			result = ingress.sync_instance_route(bench.name)

			self.assertEqual(result, "deleted")
			self.assertFalse(route_file.exists())

	def test_a_bench_that_no_longer_exists_is_deleted_rather_than_raised_on(self):
		"""No status reads the same as `Stopped`. A sync that raised here would leave the
		hostname of a deleted bench answering, which is the state this phase exists to remove."""
		with _route_dir() as (ingress, target_dir):
			ingress.publish("gone-for-good", "benchpress.cloud")

			result = ingress.sync_instance_route("gone-for-good")

			self.assertEqual(result, "deleted")
			self.assertFalse((target_dir / "gone-for-good.yml").exists())

	def test_localhost_writes_nothing_and_deletes_nothing(self):
		"""A dev checkout has no route directory and must stay byte-for-byte unaffected."""
		bench = self._bench("Running")

		with _route_dir(base_domain="localhost") as (ingress, target_dir):
			result = ingress.sync_instance_route(bench.name)

			self.assertEqual(result, "skipped")
			self.assertEqual(list(target_dir.iterdir()), [])

	def test_localhost_leaves_an_existing_file_alone(self):
		bench = self._bench("Stopped")

		with _route_dir(base_domain="localhost") as (ingress, target_dir):
			seeded = target_dir / f"{bench.name}.yml"
			seeded.write_text("untouched\n")

			self.assertEqual(ingress.sync_instance_route(bench.name), "skipped")
			self.assertEqual(seeded.read_text(), "untouched\n")

	def test_the_written_route_names_the_container_and_no_address(self):
		"""Phase 1's property has to survive this path too, since it is now the common one."""
		bench = self._bench("Running")

		with _route_dir() as (ingress, target_dir):
			ingress.sync_instance_route(bench.name)
			written = (target_dir / f"{bench.name}.yml").read_text()

		self.assertIn(f"http://{bench.name}:8000", written)
		self.assertNotRegex(written, IPV4_IN_TEXT)


class TestRouteSyncTriggers(IntegrationTestCase):
	"""Every status transition hands the route write to `queue-long`.

	`queue-long` is the only worker that mounts the route directory. `backend` serves these
	requests and mounts it not at all, and `default` is consumed by `queue-short`, which has no
	mount either — so a sync on any other queue writes into that container's own filesystem and
	Traefik never sees it, with every check green. The queue argument is the property under test.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.lab = _make_lab("test-lab-route-sync-triggers")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Bench Instance", filters={"lab": cls.lab.name}, pluck="name"):
			frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
		cls.lab.delete(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _bench(self, status="Running"):
		bench = _fresh_bench(self, self.lab.name)
		bench.status = status
		bench.container_id = "container-route-sync"
		bench.save(ignore_permissions=True)
		frappe.db.commit()
		return bench

	def _assert_synced_on_long(self, enqueue, bench_name):
		enqueue.assert_called_once()
		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], "benchpress.ingress.sync_instance_route")
		self.assertEqual(kwargs["bench_name"], bench_name)
		self.assertEqual(kwargs["queue"], "long")
		# The job re-reads `status`, so it must not start before the new value is committed.
		self.assertTrue(kwargs["enqueue_after_commit"])

	@patch("benchpress.lifecycle.stop_container")
	def test_stop_enqueues_the_sync_on_the_long_queue(self, mock_stop):
		from benchpress.lifecycle import stopped

		bench = self._bench()

		with patch("frappe.enqueue") as enqueue:
			stopped(bench.name)

		self._assert_synced_on_long(enqueue, bench.name)

	def test_start_enqueues_the_sync_on_the_long_queue(self):
		from benchpress.api import bench_action

		bench = self._bench("Stopped")

		with patch("benchpress.lifecycle.start_container"), patch("frappe.enqueue") as enqueue:
			bench_action(bench.name, "start")

		self._assert_synced_on_long(enqueue, bench.name)

	def test_restart_enqueues_the_sync_on_the_long_queue(self):
		"""`docker restart` re-allocates the address, and the file may have been removed by a
		previous stop — a restart that skipped the sync would come back unrouted."""
		from benchpress.api import bench_action

		bench = self._bench()

		with patch("benchpress.lifecycle.restart_container"), patch("frappe.enqueue") as enqueue:
			bench_action(bench.name, "restart")

		self._assert_synced_on_long(enqueue, bench.name)

	def test_desk_start_enqueues_the_sync_on_the_long_queue(self):
		bench = self._bench("Stopped")

		with (
			patch("benchpress.lifecycle.start_container"),
			patch("frappe.msgprint"),
			patch("frappe.enqueue") as enqueue,
		):
			bench.enqueue_start()

		self._assert_synced_on_long(enqueue, bench.name)

	def test_two_transitions_in_quick_succession_deduplicate(self):
		"""A stop followed straight away by a start must not queue two writes racing each other
		for the same file — the job id is per bench and `deduplicate` collapses them."""
		from benchpress.ingress import enqueue_route_sync

		with patch("frappe.enqueue") as enqueue:
			enqueue_route_sync("inst-1")
			enqueue_route_sync("inst-1")

		job_ids = {call.kwargs["job_id"] for call in enqueue.call_args_list}
		self.assertEqual(job_ids, {"route_sync:inst-1"})
		self.assertTrue(all(call.kwargs["deduplicate"] for call in enqueue.call_args_list))

	def test_teardown_deletes_directly_and_enqueues_nothing(self):
		"""Teardown already runs on `queue-long`, and it must not depend on a second job
		surviving to remove live routing state."""
		from benchpress import lifecycle

		bench = self._bench()
		bench.container_id = None
		bench.save(ignore_permissions=True)

		with _route_dir() as (_ingress, target_dir):
			ingress.publish(bench.name, "benchpress.cloud")
			route_file = target_dir / f"{bench.name}.yml"

			with patch("frappe.enqueue") as enqueue:
				lifecycle.torn_down(bench)

			self.assertFalse(route_file.exists())
			enqueue.assert_not_called()
