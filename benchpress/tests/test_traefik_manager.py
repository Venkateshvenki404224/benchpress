# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.traefik_manager import _render_traefik_config, compute_bench_labels

BENCH = frappe._dict(bench_name="abc123")
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

	def test_traefik_labels_with_base_domain(self):
		labels = compute_bench_labels(BENCH, LAB, frappe._dict(base_domain="lab.test"))
		self.assertEqual(labels["traefik.enable"], "true")
		self.assertEqual(labels["traefik.docker.network"], "benchpress")
		self.assertEqual(labels["traefik.http.routers.abc123.rule"], "Host(`abc123.lab.test`)")
		self.assertEqual(labels["traefik.http.routers.abc123.entrypoints"], "websecure")
		self.assertEqual(labels["traefik.http.routers.abc123.tls"], "true")
		self.assertEqual(labels["traefik.http.routers.abc123.tls.certresolver"], "letsencrypt")
		self.assertEqual(labels["traefik.http.routers.abc123.service"], "abc123-svc")
		self.assertEqual(labels["traefik.http.services.abc123-svc.loadbalancer.server.port"], "8000")


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
