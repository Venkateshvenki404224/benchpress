# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.traefik_manager import (
	_apr1_crypt,
	_render_traefik_config,
	compute_bench_labels,
	make_basicauth_users,
	routing_enabled,
)

BENCH = frappe._dict(bench_name="abc123", is_public=1)
PRIVATE_BENCH = frappe._dict(
	bench_name="abc123", is_public=0, public_username="lab", public_password="secret123"
)
LAB = frappe._dict(lab_id="crm-lab")


class TestComputeBenchLabels(IntegrationTestCase):
	def test_base_labels_always_present(self):
		labels = compute_bench_labels(BENCH, LAB, frappe._dict(base_domain=""))
		self.assertEqual(labels["benchpress.managed"], "true")
		self.assertEqual(labels["benchpress.bench_name"], "abc123")
		self.assertEqual(labels["benchpress.lab"], "crm-lab")

	def test_no_traefik_labels_without_base_domain(self):
		labels = compute_bench_labels(BENCH, LAB, frappe._dict(base_domain=""))
		self.assertFalse(any(k.startswith("traefik.") for k in labels))

	def test_no_traefik_labels_when_master_switch_off(self):
		labels = compute_bench_labels(
			BENCH, LAB, frappe._dict(base_domain="lab.test", enable_public_routing=0)
		)
		self.assertFalse(any(k.startswith("traefik.") for k in labels))

	def test_traefik_labels_with_base_domain(self):
		labels = compute_bench_labels(
			BENCH, LAB, frappe._dict(base_domain="lab.test", enable_public_routing=1)
		)
		self.assertEqual(labels["traefik.enable"], "true")
		self.assertEqual(labels["traefik.docker.network"], "benchpress")
		self.assertEqual(labels["traefik.http.routers.abc123.rule"], "Host(`abc123.lab.test`)")
		self.assertEqual(labels["traefik.http.routers.abc123.entrypoints"], "websecure")
		self.assertEqual(labels["traefik.http.routers.abc123.tls"], "true")
		self.assertEqual(labels["traefik.http.routers.abc123.tls.certresolver"], "letsencrypt")
		self.assertEqual(labels["traefik.http.routers.abc123.service"], "abc123-svc")
		self.assertEqual(labels["traefik.http.services.abc123-svc.loadbalancer.server.port"], "8000")

	def test_public_bench_has_no_basicauth_middleware(self):
		labels = compute_bench_labels(
			BENCH, LAB, frappe._dict(base_domain="lab.test", enable_public_routing=1)
		)
		self.assertNotIn("traefik.http.routers.abc123.middlewares", labels)
		self.assertFalse(any(".basicauth." in k for k in labels))

	def test_private_bench_adds_basicauth_middleware(self):
		labels = compute_bench_labels(
			PRIVATE_BENCH, LAB, frappe._dict(base_domain="lab.test", enable_public_routing=1)
		)
		self.assertEqual(labels["traefik.http.routers.abc123.middlewares"], "abc123-auth")
		users = labels["traefik.http.middlewares.abc123-auth.basicauth.users"]
		self.assertTrue(users.startswith("lab:$apr1$"))


class TestMakeBasicauthUsers(IntegrationTestCase):
	def test_apr1_entry_format_and_verifies(self):
		entry = make_basicauth_users("lab", "s3cret-pw")
		user, hashed = entry.split(":", 1)
		self.assertEqual(user, "lab")
		self.assertTrue(hashed.startswith("$apr1$"))
		salt = hashed.split("$")[2]
		self.assertEqual(_apr1_crypt("s3cret-pw", salt), hashed)

	def test_salt_is_randomised(self):
		self.assertNotEqual(make_basicauth_users("lab", "pw"), make_basicauth_users("lab", "pw"))

	def test_apr1_matches_openssl_reference(self):
		self.assertEqual(_apr1_crypt("secret123", "abcdEFGH"), "$apr1$abcdEFGH$GCLJFBcJTZzLNXVmhLkb91")


class TestRenderTraefikConfig(IntegrationTestCase):
	def test_staging_ca_by_default(self):
		config = _render_traefik_config(frappe._dict(le_use_staging=1, acme_email="ops@lab.test"))
		self.assertIn("acme-staging-v02.api.letsencrypt.org/directory", config)
		self.assertIn('email: "ops@lab.test"', config)
		self.assertIn("entryPoint:\n          to: websecure", config)

	def test_production_ca_when_staging_disabled(self):
		config = _render_traefik_config(frappe._dict(le_use_staging=0, acme_email="ops@lab.test"))
		self.assertIn("acme-v02.api.letsencrypt.org/directory", config)
		self.assertNotIn("staging", config)

	def test_blank_email_when_unset(self):
		config = _render_traefik_config(frappe._dict(le_use_staging=1, acme_email=None))
		self.assertIn('email: ""', config)


class TestRoutingEnabled(IntegrationTestCase):
	def test_requires_switch_and_domain(self):
		self.assertTrue(routing_enabled(frappe._dict(enable_public_routing=1, base_domain="lab.test")))
		self.assertFalse(routing_enabled(frappe._dict(enable_public_routing=0, base_domain="lab.test")))
		self.assertFalse(routing_enabled(frappe._dict(enable_public_routing=1, base_domain="")))
		self.assertFalse(routing_enabled(frappe._dict(enable_public_routing=0, base_domain="")))
