# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import importlib
import json
import pkgutil
from unittest.mock import MagicMock, patch

import frappe
import frappe.client
from frappe.tests import IntegrationTestCase

import benchpress
from benchpress import api, contact, waitlist
from benchpress.benchpress.doctype.bench_instance import get_instance_id

GUEST_WAITLIST_EMAIL = "authz-guest-waitlist@example.com"
GUEST_CONTACT_EMAIL = "authz-guest-contact@example.com"


def _delete_waitlist_entry(email):
	frappe.set_user("Administrator")
	if frappe.db.exists("Waitlist Entry", email):
		frappe.delete_doc("Waitlist Entry", email, force=True, ignore_permissions=True)


def _delete_contact_messages(email):
	frappe.set_user("Administrator")
	for name in frappe.get_all("Contact Message", filters={"email": email}, pluck="name"):
		frappe.delete_doc("Contact Message", name, force=True, ignore_permissions=True)


def _guest_endpoints() -> set[str]:
	"""Every `allow_guest` method this app registers."""
	_import_every_module()
	return {
		f"{method.__module__}.{method.__name__}"
		for method in frappe.guest_methods
		if method.__module__.startswith("benchpress.")
	}


def _import_every_module() -> None:
	for module in pkgutil.walk_packages(benchpress.__path__, prefix="benchpress."):
		try:
			importlib.import_module(module.name)
		except Exception:
			continue  # a module that cannot be imported cannot be serving guests either


def _ensure_user(email, first_name, role=None):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"roles": [{"role": role}] if role else [],
			}
		).insert(ignore_permissions=True)
	return email


def _ensure_lab(lab_id):
	if frappe.db.exists("Lab", lab_id):
		frappe.delete_doc("Lab", lab_id, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "Lab",
			"lab_id": lab_id,
			"title": f"Authz {lab_id}",
			"frappe_version": "version-15",
			"image_tag": "benchpress/test:latest",
		}
	).insert(ignore_permissions=True)


def _ensure_owned_bench(owner, lab):
	name = get_instance_id(owner, lab.name)
	if frappe.db.exists("Bench Instance", name):
		frappe.delete_doc("Bench Instance", name, force=True, ignore_permissions=True)
	frappe.set_user(owner)
	try:
		return frappe.get_doc(
			{
				"doctype": "Bench Instance",
				"lab": lab.name,
				"frappe_version": lab.frappe_version,
				"status": "Running",
				"runtime": "sysbox",
				"container_id": "authz-container",
				"code_server_url": "http://localhost:8443",
				"code_server_password": "cs-secret",
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class TestApiAuthorization(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.user_a = _ensure_user("authz-user-a@example.com", "Authz UserA", "BenchPress User")
		cls.user_b = _ensure_user("authz-user-b@example.com", "Authz UserB", "BenchPress User")
		cls.admin_user = _ensure_user("authz-admin@example.com", "Authz Admin", "BenchPress Admin")
		cls.norole_user = _ensure_user("authz-norole@example.com", "Authz NoRole")
		cls.lab = _ensure_lab("authz-lab")
		cls.bench = _ensure_owned_bench(cls.user_a, cls.lab)
		cls.build_log = frappe.get_doc(
			{
				"doctype": "Build Log",
				"lab": cls.lab.name,
				"log_type": "error",
				"message": "authz fixture build line",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		cls.deploy_log = frappe.get_doc(
			{
				"doctype": "Deploy Log",
				"bench": cls.bench.name,
				"log_type": "info",
				"message": "authz fixture log line",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.delete_doc("Deploy Log", cls.deploy_log.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Build Log", cls.build_log.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Bench Instance", cls.bench.name, force=True, ignore_permissions=True)
		frappe.delete_doc("Lab", cls.lab.name, force=True, ignore_permissions=True)
		for email in (cls.user_a, cls.user_b, cls.admin_user, cls.norole_user):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def assert_denied(self, action):
		with self.assertRaises(frappe.PermissionError):
			action()

	# --- Guest / unauthenticated rejected ------------------------------------

	def test_guest_denied_from_admin_only_endpoints(self):
		frappe.set_user("Guest")
		self.assert_denied(lambda: api.create_lab_from_template("frappe", "authz-guest"))
		self.assert_denied(lambda: api.build_lab_image(self.lab.name))
		self.assert_denied(lambda: api.prewarm_catalog())
		self.assert_denied(lambda: api.run_diagnostics())
		self.assert_denied(lambda: api.preflight_runtime("sysbox"))

	def test_guest_denied_from_overview_endpoints(self):
		frappe.set_user("Guest")
		self.assert_denied(api.get_overview)
		self.assert_denied(api.get_vpn_status)

	def test_guest_denied_from_bench_scoped_endpoints(self):
		frappe.set_user("Guest")
		bench = self.bench.name
		self.assert_denied(lambda: api.bench_action(bench, "start"))
		self.assert_denied(lambda: api.get_deploy_logs(bench))
		self.assert_denied(lambda: api.get_code_server_credentials(bench))
		self.assert_denied(lambda: api.get_bench_credentials(bench))
		self.assert_denied(lambda: api.restart_code_server(bench))
		self.assert_denied(lambda: api.renew_bench(bench, "any-plan", "authz-guest-req"))

	def test_only_the_three_public_form_doors_are_open_to_guests(self):
		self.assertEqual(
			_guest_endpoints(),
			{
				"benchpress.waitlist.join",
				"benchpress.signup.sign_up",
				"benchpress.contact.submit",
			},
		)

	def test_guest_can_reach_the_waitlist(self):
		frappe.set_user("Guest")
		self.addCleanup(_delete_waitlist_entry, GUEST_WAITLIST_EMAIL)
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True

		self.assertTrue(waitlist.join(GUEST_WAITLIST_EMAIL)["joined"])

	def test_guest_can_reach_the_contact_form(self):
		frappe.set_user("Guest")
		self.addCleanup(_delete_contact_messages, GUEST_CONTACT_EMAIL)
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True

		self.assertTrue(contact.submit("Authz Guest", GUEST_CONTACT_EMAIL, "hello")["sent"])

	def test_guest_denied_from_approving_the_waitlist(self):
		frappe.set_user("Guest")
		self.assert_denied(lambda: waitlist.approve([GUEST_WAITLIST_EMAIL]))

	def test_guest_denied_from_rejecting_the_waitlist(self):
		frappe.set_user("Guest")
		self.assert_denied(lambda: waitlist.reject([GUEST_WAITLIST_EMAIL]))

	def test_guest_denied_from_the_contact_admin_endpoints(self):
		frappe.set_user("Guest")
		self.assert_denied(lambda: contact.mark_answered(["nonexistent"]))

	def test_non_admin_denied_from_reading_contact_messages(self):
		frappe.set_user(self.user_a)
		self.assertFalse(frappe.has_permission("Contact Message", "read"))

	# --- Wrong-role (BenchPress User) blocked from admin-only endpoints -------

	def test_non_admin_denied_from_create_lab_from_template(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.create_lab_from_template("frappe", "authz-user"))

	def test_non_admin_denied_from_build_lab_image(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.build_lab_image(self.lab.name))

	def test_non_admin_denied_from_prewarm_catalog(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.prewarm_catalog())

	def test_non_admin_denied_from_run_diagnostics(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.run_diagnostics())

	def test_non_admin_denied_from_preflight_runtime(self):
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.preflight_runtime("sysbox"))

	def test_an_admin_reaches_preflight_runtime(self):
		frappe.set_user("Administrator")
		with patch("benchpress.docker_manager.get_client") as mock_client:
			self.assertTrue(api.preflight_runtime("sysbox")["ok"])
		self.assertEqual(mock_client.return_value.containers.run.call_args.kwargs["runtime"], "sysbox-runc")

	def test_owner_denied_from_deleting_own_bench(self):
		# user_a passes require_bench_access on its own bench, but delete is admin-only.
		frappe.set_user(self.user_a)
		self.assert_denied(lambda: api.bench_action(self.bench.name, "delete"))

	# --- Cross-user isolation (user_b against user_a's bench) -----------------

	def test_owner_denied_from_lowering_their_own_benchs_runtime(self):
		# `if_owner` write is granted on Bench Instance; only permlevel stops this.
		frappe.set_user(self.user_a)
		self.assert_denied(
			lambda: frappe.client.set_value("Bench Instance", self.bench.name, "runtime", "runc")
		)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Bench Instance", self.bench.name, "runtime"), "sysbox")

	def test_owner_can_still_see_their_benchs_runtime(self):
		frappe.set_user(self.user_a)
		mine = [b for b in api.get_benches() if b["name"] == self.bench.name]
		self.assertEqual([b["runtime"] for b in mine], ["sysbox"])

	def test_cross_user_denied_from_get_deploy_logs(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.get_deploy_logs(self.bench.name))

	def test_cross_user_denied_from_bench_action(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.bench_action(self.bench.name, "start"))

	def test_cross_user_denied_from_renew_bench(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.renew_bench(self.bench.name, "any-plan", "authz-cross-req"))

	def test_cross_user_denied_from_get_code_server_credentials(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.get_code_server_credentials(self.bench.name))

	def test_cross_user_denied_from_restart_code_server(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.restart_code_server(self.bench.name))

	def test_cross_user_denied_from_get_bench_credentials(self):
		frappe.set_user(self.user_b)
		self.assert_denied(lambda: api.get_bench_credentials(self.bench.name))

	def test_get_benches_hides_other_users_bench(self):
		frappe.set_user(self.user_b)
		names = [bench["name"] for bench in api.get_benches()]
		self.assertNotIn(self.bench.name, names)

	def test_get_lab_hides_another_users_bench_health(self):
		frappe.set_user(self.user_b)
		self.assertIsNone(api.get_lab(self.lab.name)["bench"])
		self.assertEqual(api.get_lab(self.lab.name)["sites"], [])

		frappe.set_user(self.user_a)
		self.assertEqual(api.get_lab(self.lab.name)["bench"]["name"], self.bench.name)

	def test_get_lab_denied_to_a_user_without_an_app_role(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.get_lab(self.lab.name))

	def test_get_labs_hides_another_users_deployment(self):
		frappe.set_user(self.user_b)
		row = self._lab_row(api.get_labs())
		self.assertIsNone(row["deployed_as"])
		self.assertEqual(row["bench_count"], 0)

	def test_get_labs_shows_the_owner_their_own_deployment(self):
		frappe.set_user(self.user_a)
		row = self._lab_row(api.get_labs())
		self.assertEqual(row["deployed_as"]["bench"], self.bench.name)
		self.assertEqual(row["bench_count"], 1)

	def _lab_row(self, labs):
		row = next((lab for lab in labs if lab["name"] == self.lab.name), None)
		self.assertIsNotNone(row, "the fixture lab is readable by every app user")
		return row

	# --- History is scoped, and Build Log has no query condition to do it -----

	def test_build_history_shows_a_user_their_own_builds_and_nobody_elses(self):
		"""`cls.build_log` is the Administrator's; the one inserted here is user_a's."""
		own_build = self._insert_build_log_as(self.user_a)

		frappe.set_user(self.user_a)
		names = [row["name"] for row in api.get_build_history()["rows"]]
		self.assertIn(own_build, names, "the owner cannot see their own build")
		self.assertNotIn(self.build_log.name, names, "Build Log is leaking across users")

	def test_build_history_shows_an_admin_every_build(self):
		frappe.set_user(self.admin_user)
		names = [row["name"] for row in api.get_build_history()["rows"]]
		self.assertIn(self.build_log.name, names)

	def test_deploy_history_hides_another_users_runs(self):
		frappe.set_user(self.user_b)
		names = [row["name"] for row in api.get_deploy_history()["rows"]]
		self.assertNotIn(self.deploy_log.name, names)

		frappe.set_user(self.user_a)
		names = [row["name"] for row in api.get_deploy_history()["rows"]]
		self.assertIn(self.deploy_log.name, names)

	def test_roleless_denied_from_history(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_build_history)
		self.assert_denied(api.get_deploy_history)

	def test_non_admin_denied_from_get_lab_form_options(self):
		frappe.set_user(self.user_a)
		self.assert_denied(api.get_lab_form_options)

		frappe.set_user(self.admin_user)
		self.assertIn("frappe_versions", api.get_lab_form_options())

	def _insert_build_log_as(self, owner):
		frappe.set_user(owner)
		try:
			log = frappe.get_doc(
				{
					"doctype": "Build Log",
					"lab": self.lab.name,
					"log_type": "success",
					"message": "=== Build complete: benchpress/authz-lab:latest ===",
					"timestamp": frappe.utils.now_datetime(),
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")
		self.addCleanup(frappe.delete_doc, "Build Log", log.name, force=True, ignore_permissions=True)
		return log.name

	# --- Role-less user blocked by require_app_user (issue #88) ---------------

	def test_roleless_denied_from_create_bench(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.create_bench("{}"))

	def test_roleless_denied_from_add_device(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.add_device("authz-dev", "laptop"))

	def test_roleless_denied_from_remove_device(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.remove_device("authz-dev"))

	def test_roleless_denied_from_list_devices(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.list_devices())

	def test_roleless_denied_from_get_device_wg_config(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.get_device_wg_config("authz-dev"))

	def test_roleless_denied_from_the_credit_endpoints(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_credit_summary)
		self.assert_denied(api.get_credit_statement)

	def test_roleless_denied_from_the_purchase_endpoints(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_purchase_options)
		self.assert_denied(lambda: api.buy_credits("Starter"))

	# --- The credit gate must never answer a permission question -------------

	def test_the_credit_gate_never_precedes_an_endpoints_own_guard(self):
		# `requires_admission` wraps these endpoints and runs before their `require_app_user()`.
		self.with_credits_armed()
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.create_bench(json.dumps({"lab": self.lab.name})))
		self.assert_denied(lambda: api.add_device("authz-dev", "Laptop"))
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Credit Account", self.norole_user))

	def test_a_guest_meets_the_same_wall_with_credits_armed(self):
		self.with_credits_armed()
		frappe.set_user("Guest")
		self.assert_denied(lambda: api.build_lab_image(self.lab.name))
		self.assert_denied(lambda: api.create_bench(json.dumps({"lab": self.lab.name})))

	def test_an_app_user_still_reaches_the_endpoint_with_credits_armed(self):
		self.with_credits_armed()
		frappe.set_user(self.user_a)
		with patch("frappe.enqueue"):
			self.assertEqual(api.create_bench(json.dumps({"lab": self.lab.name}))["status"], "Deploying")

	def with_credits_armed(self):
		# This class commits its fixtures, so anything left pending here becomes durable too.
		frappe.db.set_single_value("BenchPress Settings", "enable_credits", 1)
		frappe.clear_cache(doctype="BenchPress Settings")
		self.addCleanup(self.forget_credit_rows)
		self.addCleanup(frappe.clear_cache, doctype="BenchPress Settings")
		self.addCleanup(frappe.db.set_single_value, "BenchPress Settings", "enable_credits", 0)

	def forget_credit_rows(self):
		for user in (self.user_a, self.user_b, self.admin_user, self.norole_user):
			frappe.db.delete("Credit Ledger Entry", {"account": user})
			frappe.db.delete("Credit Account", {"user": user})

	def test_a_credit_statement_is_only_ever_the_callers_own(self):
		frappe.set_user(self.user_a)
		self.assertEqual(api.get_credit_statement()["rows"], [])
		self.assertIn("enabled", api.get_credit_summary())

	def test_roleless_denied_from_get_labs(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_labs)

	def test_roleless_denied_from_get_lab(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.get_lab(self.lab.name))

	def test_roleless_denied_from_get_lab_templates(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_lab_templates)

	def test_roleless_denied_from_get_benches(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_benches)

	def test_roleless_denied_from_get_bench_credentials(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(lambda: api.get_bench_credentials(self.bench.name))

	def test_roleless_denied_from_get_overview(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_overview)

	def test_roleless_denied_from_get_vpn_status(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_vpn_status)

	def test_roleless_denied_from_run_connection_test(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.run_connection_test)

	def test_roleless_denied_from_get_device_types(self):
		frappe.set_user(self.norole_user)
		self.assert_denied(api.get_device_types)

	# --- Overview is scoped to the caller ------------------------------------

	def test_overview_shows_a_user_only_their_own_environments(self):
		frappe.set_user(self.user_b)
		names = [row["name"] for row in api.get_overview()["environments"]]
		self.assertNotIn(self.bench.name, names)

		frappe.set_user(self.user_a)
		names = [row["name"] for row in api.get_overview()["environments"]]
		self.assertIn(self.bench.name, names)

	def test_overview_withholds_infrastructure_from_a_user(self):
		frappe.set_user(self.user_a)
		self.assertIsNone(api.get_overview()["infrastructure"])

		frappe.set_user(self.admin_user)
		with patch("benchpress.diagnostics.run_diagnostics", return_value=[]):
			self.assertEqual(api.get_overview()["infrastructure"], [])

	def test_overview_activity_never_leaks_build_logs_to_a_user(self):
		# Build Log has no permission query condition, so the feed must exclude it itself.
		frappe.set_user(self.user_a)
		activity = api.get_overview()["activity"]
		self.assertTrue(activity, "user_a's own deploy log should still appear")
		for event in activity:
			self.assertNotIn("lab", event)

		frappe.set_user(self.admin_user)
		with patch("benchpress.diagnostics.run_diagnostics", return_value=[]):
			admin_activity = api.get_overview()["activity"]
		self.assertTrue(any("lab" in event for event in admin_activity))

	def test_overview_activity_hides_another_users_deploys(self):
		frappe.set_user(self.user_b)
		activity = api.get_overview()["activity"]
		self.assertFalse([event for event in activity if event.get("bench") == self.bench.name])

	def test_overview_activity_hides_another_users_bench_events(self):
		frappe.set_user("Administrator")
		event = frappe.get_doc(
			{
				"doctype": "Bench Event",
				"bench": self.bench.name,
				"event_type": "bench_died",
				"severity": "error",
				"occurred_at": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bench Event", event.name, force=True, ignore_permissions=True)

		frappe.set_user(self.user_a)
		mine = [row for row in api.get_overview()["activity"] if "stopped unexpectedly" in row["message"]]
		self.assertTrue(mine, "the bench's own owner must see it")
		self.assertEqual(mine[0]["log_type"], "error")

		frappe.set_user(self.user_b)
		theirs = api.get_overview()["activity"]
		self.assertFalse([row for row in theirs if "stopped unexpectedly" in row["message"]])

	def test_app_user_allowed_to_read_vpn_status(self):
		frappe.set_user(self.user_a)
		status = api.get_vpn_status()
		self.assertFalse(status["connected"])
		self.assertEqual(status["peer_count"], 0)

	# --- The connection test is the user's, and only theirs ------------------

	def test_app_user_may_run_the_connection_test_for_their_own_peer(self):
		frappe.set_user(self.user_a)
		checks = api.run_connection_test()

		self.assertEqual(
			[check["check"] for check in checks],
			["vpn_server", "device_registered", "peer_active", "handshake"],
		)
		# No device of their own, so the test says so instead of throwing.
		self.assertEqual(checks[1]["status"], "Error")

	def test_connection_test_never_leaks_the_admin_only_checks(self):
		frappe.set_user(self.user_a)
		with patch("benchpress.diagnostics.run_diagnostics") as run_diagnostics:
			checks = api.run_connection_test()

		# The infrastructure probes are admin-only; the user path must not run them.
		run_diagnostics.assert_not_called()
		leaked = {"docker_socket", "docker_network", "mariadb", "redis"}
		self.assertFalse(leaked & {check["check"] for check in checks})

	def test_connection_test_reports_only_the_callers_own_devices(self):
		other_device = {
			"name": "PEER-OTHER",
			"device_name": "Someone else's laptop",
			"last_handshake": None,
		}
		frappe.set_user(self.user_b)
		with patch("benchpress.connection_test.list_devices", return_value=[other_device]) as list_devices:
			checks = api.run_connection_test()

		# The device list is the owner-scoped wrapper, never a raw peer query.
		list_devices.assert_called_once_with()
		self.assertIn("Someone else's laptop", checks[3]["hint"])

	def test_app_user_denied_another_users_peer_status(self):
		from benchpress.vpn_adapter import get_device_peer_status

		peer = MagicMock()
		peer.owner_user = self.user_a
		frappe.set_user(self.user_b)
		with patch("benchpress.vpn_adapter.frappe.get_doc", return_value=peer):
			self.assert_denied(lambda: get_device_peer_status("PEER-OTHER"))

	# --- Positive controls: require_app_user permits a BenchPress User --------

	def test_app_user_allowed_to_create_bench(self):
		frappe.set_user(self.user_a)
		try:
			with patch("frappe.enqueue") as enqueue:
				result = api.create_bench(frappe.as_json({"lab": self.lab.name}))
			enqueue.assert_called_once()
			self.assertEqual(result["name"], self.bench.name)
		finally:
			# create_bench flips the shared bench fixture to Deploying; restore it.
			frappe.set_user("Administrator")
			frappe.db.set_value("Bench Instance", self.bench.name, "status", "Running")
			frappe.db.commit()

	def test_creating_a_site_is_not_a_capability_this_api_offers(self):
		# `frappe.client.insert` is whitelisted, so a leftover `create` DocPerm is a second door.
		self.assertFalse(hasattr(api, "create_site"))
		self.assertNotIn("create_site", {method.__name__ for method in frappe.whitelisted})
		frappe.set_user(self.user_a)
		self.assertFalse(frappe.has_permission("Bench Site", "create"))

	def test_app_user_allowed_to_add_device(self):
		frappe.set_user(self.user_a)
		with patch("benchpress.vpn_adapter.register_device", return_value={"name": "authz-dev"}) as register:
			result = api.add_device("authz-dev", "laptop")
		register.assert_called_once()
		self.assertEqual(result, {"name": "authz-dev"})

	def test_app_user_allowed_to_remove_device(self):
		frappe.set_user(self.user_a)
		with patch("benchpress.vpn_adapter.unregister_device") as unregister:
			result = api.remove_device("authz-dev")
		unregister.assert_called_once()
		self.assertEqual(result, {"status": "removed"})

	def test_app_user_allowed_to_list_devices(self):
		frappe.set_user(self.user_a)
		self.assertIsInstance(api.list_devices(), list)

	def test_app_user_allowed_to_get_device_wg_config(self):
		frappe.set_user(self.user_a)
		with patch("benchpress.vpn_adapter.get_device_config", return_value="[Interface]") as get_config:
			result = api.get_device_wg_config("authz-dev")
		get_config.assert_called_once()
		self.assertEqual(result, "[Interface]")

	def test_app_user_allowed_to_get_labs(self):
		frappe.set_user(self.user_a)
		self.assertIn(self.lab.name, [lab["name"] for lab in api.get_labs()])

	def test_app_user_allowed_to_get_lab(self):
		frappe.set_user(self.user_a)
		self.assertEqual(api.get_lab(self.lab.name)["lab_id"], self.lab.lab_id)

	def test_app_user_allowed_to_get_lab_templates(self):
		frappe.set_user(self.user_a)
		self.assertIsInstance(api.get_lab_templates(), list)

	# --- Positive controls: the guards permit the legitimate caller ----------

	def test_owner_reads_own_bench_credentials(self):
		frappe.set_user(self.user_a)
		creds = api.get_code_server_credentials(self.bench.name)
		self.assertEqual(creds["password"], "cs-secret")

	def test_owner_sees_own_bench_in_get_benches(self):
		frappe.set_user(self.user_a)
		names = [bench["name"] for bench in api.get_benches()]
		self.assertIn(self.bench.name, names)

	def test_owner_reads_own_deploy_logs(self):
		frappe.set_user(self.user_a)
		logs = api.get_deploy_logs(self.bench.name)
		self.assertIn(self.deploy_log.name, [log["name"] for log in logs])
		for key in ("name", "message", "log_type", "timestamp"):
			self.assertIn(key, logs[0])

	def test_get_benches_omits_password_fields(self):
		# Regression check for issue #91: the decrypt loop must not come back.
		frappe.set_user(self.user_a)
		for bench in api.get_benches():
			for field in ("ssh_password", "admin_password", "code_server_password"):
				self.assertNotIn(field, bench)

	def test_owner_reads_own_bench_credentials_via_get_bench_credentials(self):
		frappe.set_user(self.user_a)
		creds = api.get_bench_credentials(self.bench.name)
		self.assertEqual(creds["code_server_password"], "cs-secret")
		self.assertIn("ssh_password", creds)
		self.assertIn("admin_password", creds)

	def test_admin_allowed_to_create_lab_from_template(self):
		frappe.set_user(self.admin_user)
		with patch("benchpress.lab_templates.create_lab_from_template", return_value="LAB-authz") as create:
			result = api.create_lab_from_template("frappe", "authz-admin")
		create.assert_called_once()
		self.assertEqual(result, {"name": "LAB-authz", "status": "Draft"})

	def test_admin_allowed_to_prewarm_the_catalog(self):
		frappe.set_user(self.admin_user)
		with patch("frappe.enqueue") as enqueue:
			self.assertEqual(api.prewarm_catalog()["status"], "Queued")
		enqueue.assert_called_once()

	def test_admin_allowed_to_run_diagnostics(self):
		frappe.set_user(self.admin_user)
		with patch("benchpress.diagnostics.run_diagnostics", return_value=[]):
			self.assertEqual(api.run_diagnostics(), [])
