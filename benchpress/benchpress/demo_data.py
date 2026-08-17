# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Demo records so the desk workspace widgets read real numbers instead of six zeros.

Run by hand — deliberately not wired into hooks.py, it is a developer convenience:

    bench --site frontend execute benchpress.benchpress.demo_data.create_demo_data

Two constraints shape this module:

- `Bench Instance.status` is `read_only`, so the field never survives an insert. Every seeded
  bench is inserted first and its status written afterwards with `db_set`.
- It must never create a `VPN Peer`. `VPNPeer.validate` claims an address out of the live pool
  and `after_insert` enqueues a wg-agent reconcile that rewrites the WireGuard interface. The two
  VPN number cards therefore read whatever peers `install.py` and real usage created.
"""

import frappe
from frappe.utils.data import add_to_date, now_datetime

MARKER_LAB_ID = "demo-crm"

FRAPPE_VERSION = "version-16"
DEMO_APP = {
	"app_name": "erpnext",
	"app_label": "ERPNext",
	"git_url": "https://github.com/frappe/erpnext",
	"branch": FRAPPE_VERSION,
}

LAB_SPECS = (
	{"lab_id": MARKER_LAB_ID, "title": "CRM Demo", "status": "Ready"},
	{"lab_id": "demo-hrms", "title": "HR Demo", "status": "Building"},
	{"lab_id": "demo-legacy", "title": "Legacy Upgrade", "status": "Error"},
)

BENCH_STATUSES = ("Running", "Running", "Error")
SITE_NAMES = ("crm", "people")

# (days ago, logs written that day). Deploys arrive in bursts, so the Deploy Activity chart draws
# a curve with peaks and quiet days instead of a flat line of ones.
DEPLOY_BURSTS = ((28, 3), (24, 2), (19, 4), (12, 3), (7, 5), (2, 3))
DEPLOY_LOG_COUNT = sum(count for _days_ago, count in DEPLOY_BURSTS)

BUILD_LOG_COUNT = 6
LOG_WINDOW_DAYS = 30
LOG_TYPES = ("info", "success", "error")

# How long a seeded run took, in seconds. A deploy is minutes and an image build
# is longer; the spread keeps the durations from reading as one repeated value.
DEPLOY_SECONDS = (96, 142, 78, 210, 118)
BUILD_SECONDS = (359, 244, 512, 187, 421)


class DemoDataSeeder:
	"""Builds one self-consistent slice of BenchPress records with `frappe.new_doc`.

	Every record goes through the controller so validations and naming hooks run — a Lab named
	by `lab_id`, a Bench Instance named by `get_instance_id(session user, lab)`.
	"""

	def __init__(self):
		self.labs = []
		self.benches = []

	def run(self):
		self.seed_labs()
		self.seed_benches()
		self.seed_sites()
		self.seed_deploy_logs()
		self.seed_build_logs()

	def seed_labs(self):
		self.labs = [self._insert_lab(spec) for spec in LAB_SPECS]

	def _insert_lab(self, spec):
		lab = frappe.new_doc("Lab")
		lab.update(spec)
		lab.frappe_version = FRAPPE_VERSION
		lab.description = f"Demo lab in status {spec['status']}."
		lab.append("apps", DEMO_APP)
		lab.insert()
		return lab.name

	def seed_benches(self):
		self.benches = [
			self._insert_bench(lab, status) for lab, status in zip(self.labs, BENCH_STATUSES, strict=True)
		]

	def _insert_bench(self, lab, status):
		"""One bench per lab: `bench_name` is a hash of (session user, lab), so two benches on the
		same lab would collide on the same name."""
		bench = frappe.new_doc("Bench Instance")
		bench.lab = lab
		bench.insert()
		bench.db_set("status", status)
		return bench.name

	def seed_sites(self):
		for site_name, bench in zip(SITE_NAMES, self.benches, strict=False):
			site = frappe.new_doc("Bench Site")
			site.update({"site_name": site_name, "bench": bench, "status": "Active"})
			site.insert()

	def seed_deploy_logs(self):
		index = 0
		for days_ago, burst_size in DEPLOY_BURSTS:
			for _ in range(burst_size):
				self._insert_deploy_log(index, days_ago)
				index += 1

	def _insert_deploy_log(self, index, days_ago):
		log = frappe.new_doc("Deploy Log")
		log.bench = self.benches[index % len(self.benches)]
		log.log_type = LOG_TYPES[index % len(LOG_TYPES)]
		log.message = f"Demo deploy step {index + 1}."
		log.timestamp = self._days_ago(days_ago)
		log.insert()
		self._settle(log, DEPLOY_SECONDS[index % len(DEPLOY_SECONDS)])

	def seed_build_logs(self):
		for index in range(BUILD_LOG_COUNT):
			log = frappe.new_doc("Build Log")
			log.lab = self.labs[index % len(self.labs)]
			log.log_type = LOG_TYPES[index % len(LOG_TYPES)]
			log.message = f"Demo build step {index + 1}."
			log.timestamp = self._days_ago(index * LOG_WINDOW_DAYS // BUILD_LOG_COUNT)
			log.insert()
			self._settle(log, BUILD_SECONDS[index % len(BUILD_SECONDS)])

	def _settle(self, log, seconds):
		"""Give the run a believable length.

		A run's duration is read as `modified - timestamp` — the timestamp is
		when it started, `modified` the write that settled its outcome. Seeding
		only the backdated timestamp leaves `modified` at seeding time, so every
		demo run claimed to have taken as long as it was old: a three-week-old
		build reported "504h" wherever a duration is shown.
		"""
		frappe.db.set_value(
			log.doctype,
			log.name,
			"modified",
			add_to_date(log.timestamp, seconds=seconds),
			update_modified=False,
		)

	def _days_ago(self, days):
		return add_to_date(now_datetime(), days=-days)


def create_demo_data():
	"""Seed the demo records once. Re-running is a no-op — the marker Lab short-circuits it."""
	if frappe.db.exists("Lab", MARKER_LAB_ID):
		print(f"Demo data already present (Lab {MARKER_LAB_ID}) — nothing to create.")
		return

	DemoDataSeeder().run()
	print(
		f"Seeded {len(LAB_SPECS)} labs, {len(BENCH_STATUSES)} benches, {len(SITE_NAMES)} sites, "
		f"{DEPLOY_LOG_COUNT} deploy logs and {BUILD_LOG_COUNT} build logs. No VPN Peer was created."
	)
