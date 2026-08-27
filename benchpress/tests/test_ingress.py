# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import re
import ssl
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from benchpress import ingress

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


class TestPublish(unittest.TestCase):
	"""Pure-function tests, no container/DB — the URL helpers moved to test_addressing.py."""

	def test_publish_writes_router_and_service(self):
		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
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
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
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
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
				ingress.publish("inst-1", "benchpress.cloud")
				written_text = (Path(tmp) / "instances" / "inst-1.yml").read_text()

		self.assertNotIn("certResolver", written_text)
		# Two separate `{}` literals, so PyYAML emits the mapping twice rather than an
		# anchor/alias pair that Traefik would have to resolve.
		self.assertEqual(written_text.count("tls: {}"), 2)

	def test_instance_route_names_the_container_and_no_address(self):
		"""The property this phase exists to create. Both services name the container, which
		Docker's embedded DNS resolves, so no lifecycle transition can make the file stale."""
		with tempfile.TemporaryDirectory() as tmp:
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", _mounted(tmp)):
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
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
				ingress.publish("inst-1", "benchpress.cloud")
				ingress.publish("inst-1", "benchpress.cloud")

			# iterdir, so a leftover dotfile temp counts against this.
			self.assertEqual([p.name for p in target_dir.iterdir()], ["inst-1.yml"])

	def test_an_unchanged_route_is_not_rewritten(self):
		"""Traefik reloads on mtime, and the convergence cron rewrites every running bench's
		route every five minutes — so an identical write has to be a no-op."""
		with tempfile.TemporaryDirectory() as tmp:
			target_dir = _mounted(tmp)
			with patch.object(ingress, "TRAEFIK_DYNAMIC_DIR", target_dir):
				ingress.publish("inst-1", "benchpress.cloud")
				mtime = (target_dir / "inst-1.yml").stat().st_mtime_ns

				ingress.publish("inst-1", "benchpress.cloud")

				self.assertEqual((target_dir / "inst-1.yml").stat().st_mtime_ns, mtime)


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
