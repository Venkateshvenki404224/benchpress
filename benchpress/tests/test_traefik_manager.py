# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from benchpress.traefik_manager import compute_bench_labels

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
		self.assertEqual(labels["traefik.http.routers.abc123.entrypoints"], "web")
		self.assertEqual(labels["traefik.http.routers.abc123.service"], "abc123-svc")
		self.assertEqual(labels["traefik.http.services.abc123-svc.loadbalancer.server.port"], "8000")
