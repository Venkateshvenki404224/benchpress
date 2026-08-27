# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count

from benchpress import addressing, image_cache, lab_detail, lab_templates, labs, lifecycle, site_names
from benchpress.benchpress.doctype.bench_instance.bench_instance import DEPLOY_JOB_TIMEOUT

# Every field the renew path decides from, read once under the row lock.
RENEW_FIELDS = [
	"name",
	"owner",
	"lab",
	"status",
	"container_id",
	"modified",
	"lease_state",
	"expires_at_ts",
]
from benchpress.credits import account, config, lease, metering, payments
from benchpress.credits.guard import (
	build_charge,
	cap_builds_per_day,
	cap_devices,
	instance_lease_cost,
	payload_lease_cost,
	require_balance,
	requires_admission,
)
from benchpress.permissions import (
	get_bench_owner_filter,
	is_admin,
	require_admin,
	require_app_user,
	require_bench_access,
)


@frappe.whitelist()
def get_labs() -> list[dict]:
	require_app_user()
	return labs.get_labs()


@frappe.whitelist()
def get_lab(name: str) -> dict:
	require_app_user()
	return lab_detail.get_lab(name)


@frappe.whitelist()
def server_time() -> dict:
	"""The clock every countdown in the SPA corrects against.

	Epoch milliseconds, so nothing has to parse a naive datetime string — `new Date("2026-08-25
	03:10:17")` reads as browser-local in V8 and has historically been `Invalid Date` in Safari.
	"""
	require_app_user()
	return {"server_now_ms": lease.now_ms()}


@frappe.whitelist()
def get_lab_form_options() -> dict:
	"""The Lab enum and defaults the New lab form builds itself from."""
	require_admin()
	return labs.get_lab_form_options()


@frappe.whitelist()
def get_lab_templates() -> list[dict]:
	require_app_user()
	return lab_templates.get_catalog()


@frappe.whitelist()
def create_lab_from_template(template: str, lab_id: str | None = None, title: str | None = None) -> dict:
	require_admin()
	name = lab_templates.create_lab_from_template(template, lab_id, title)
	return {"name": name, "status": "Draft"}


@frappe.whitelist()
@requires_admission(cost=build_charge, caps=(cap_builds_per_day,))
def build_lab_image(lab_name: str) -> dict:
	require_admin()
	frappe.enqueue(
		"benchpress.deploy_manager.build_lab",
		lab_name=lab_name,
		queue="long",
		timeout=10800,
	)
	return {"name": lab_name, "status": "Building"}


@frappe.whitelist()
def build_lab_golden(lab_name: str) -> dict:
	"""Queue the golden build for one lab, appending it to the image the lab already has."""
	require_admin()
	lab = frappe.get_doc("Lab", lab_name)
	tag, hit = image_cache.resolve(lab)
	if lab.status != "Ready" or not hit or lab.image_tag != tag:
		frappe.throw(_("No built image for lab '{0}'. Build it first from the Lab record.").format(lab.title))
	frappe.enqueue(
		"benchpress.golden.build_golden_job",
		lab_name=lab_name,
		user=frappe.session.user,
		queue="long",
		timeout=image_cache.BUILD_TIMEOUT,
		job_id=f"golden:{lab_name}",
		deduplicate=True,
	)
	return {"name": lab_name, "status": "Queued"}


@frappe.whitelist()
def prewarm_catalog() -> dict:
	"""Build the shared image for every catalog template that has none yet.

	Returns as soon as the work is queued: the builds themselves take minutes each and run on
	`queue-long`, the only worker that can reach the Docker socket.
	"""
	require_admin()
	return image_cache.enqueue_prewarm_catalog()


@frappe.whitelist()
def get_benches() -> list[dict]:
	require_app_user()
	benches = frappe.get_list(
		"Bench Instance",
		filters=get_bench_owner_filter(),
		fields=[
			"name",
			"bench_name",
			"lab",
			"frappe_version",
			"domain",
			"status",
			"container_id",
			"container_ip",
			"runtime",
			"wg_ip",
			"cpu_usage",
			"memory_usage",
			"container_health",
			"last_health_check",
			"started_at",
			"ssh_username",
			"code_server_url",
			"public_url",
		],
		order_by="creation desc",
	)

	names = [bench["name"] for bench in benches]
	apps = _counts_by_bench("Bench App", "parent", names)
	sites = _counts_by_bench("Bench Site", "bench", names)
	for bench in benches:
		bench["app_count"] = apps.get(bench["name"], 0)
		bench["site_count"] = sites.get(bench["name"], 0)
		bench["addresses"] = addressing.addresses_for(bench)

	return benches


def _counts_by_bench(doctype: str, column: str, bench_names: list[str]) -> dict[str, int]:
	"""Rows per bench, grouped in one query.

	Counted one bench at a time before, so an admin's list cost two queries per row — and every
	deploy now writes a `Bench Site`, so that table is no longer small enough to ignore.
	"""
	if not bench_names:
		return {}
	table = DocType(doctype)
	rows = (
		frappe.qb.from_(table)
		.select(table[column].as_("bench"), Count("*").as_("total"))
		.where(table[column].isin(bench_names))
		.groupby(table[column])
		.run(as_dict=True)
	)
	return {row.bench: row.total for row in rows}


@frappe.whitelist()
@requires_admission(cost=payload_lease_cost)
def create_bench(data: str) -> dict:
	require_app_user()
	from benchpress.benchpress.doctype.bench_instance import get_instance_id

	data = frappe.parse_json(data)

	lab_name = data.get("lab")
	if not lab_name:
		frappe.throw(_("Lab is required to create a bench."))

	lab = frappe.get_cached_doc("Lab", lab_name)
	requested_site_name = data.get("site_name") or data.get("site")

	site_name = site_names.qualify(requested_site_name)
	instance_id = get_instance_id(frappe.session.user, lab_name)
	if frappe.db.exists("Bench Instance", instance_id):
		doc = _redeploy_instance(instance_id, site_name)
	else:
		try:
			doc = _new_instance(lab, data, site_name)
		except frappe.DuplicateEntryError:
			# A call for the same (user, lab) that arrived first already named this bench.
			# `get_instance_id` is deterministic, so the branch was always meant to be idempotent.
			frappe.clear_last_message()
			doc = _redeploy_instance(instance_id, site_name)

	site_names.claim(doc)

	frappe.enqueue(
		"benchpress.lifecycle.deploy_bench",
		bench_name=doc.name,
		queue="long",
		timeout=DEPLOY_JOB_TIMEOUT,
		job_id=f"deploy_bench:{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)

	return {"name": doc.name, "status": "Deploying"}


def _redeploy_instance(instance_id: str, site_name: str | None):
	doc = frappe.get_doc("Bench Instance", instance_id)
	if site_name and site_name != doc.site_name:
		_assert_site_name_changeable(doc)
		doc.site_name = site_name
	doc.status = "Deploying"
	doc.save()
	return doc


def _new_instance(lab, data: dict, site_name: str | None):
	doc = frappe.get_doc(
		{
			"doctype": "Bench Instance",
			"bench_name": data.get("bench_name"),
			"lab": lab.name,
			"frappe_version": lab.frappe_version,
			"domain": data.get("domain"),
			"site_name": site_name,
			"status": "Draft",
		}
	)
	for app in lab.apps:
		doc.append(
			"apps",
			{
				"app_name": app.app_name,
				"app_label": app.app_label,
				"git_url": app.git_url,
				"branch": app.branch,
			},
		)
	return doc.insert()


def _assert_site_name_changeable(doc) -> None:
	"""Refuse to rename a bench whose current name might still own a live database.

	`Draft` is the only status that guarantees no live site exists under `doc.site_name`:
	either nothing was ever deployed, or `teardown_bench` ran and actually dropped the
	database before resetting status. `stop_bench` marks the instance `Stopped` and
	deactivates its `Bench Site` rows WITHOUT dropping the database (only `teardown_bench`
	does that) — so `Stopped` must still block a rename, or the old database would be
	silently orphaned. The caller stops/deletes the instance first to rename it.
	"""
	if doc.status != "Draft":
		frappe.throw(
			_(
				"'{0}' is already deployed as '{1}'. Stop or delete this instance before choosing "
				"a different site name."
			).format(doc.name, doc.site_name)
		)


@frappe.whitelist()
def bench_action(bench_name: str, action: str) -> dict:
	require_bench_access(bench_name)
	if action == "delete" and not is_admin():
		frappe.throw(_("Only admins can delete bench instances."), frappe.PermissionError)

	bench = frappe.get_doc("Bench Instance", bench_name)

	if action == "delete":
		return _delete_bench(bench)
	if action == "stop":
		return _stop_bench(bench)

	if action not in ("start", "restart"):
		frappe.throw(_("Invalid action: {0}").format(action))

	return _start_bench(bench, action)


@requires_admission(cost=instance_lease_cost)
def _start_bench(bench, action: str) -> dict:
	"""Bring a deployed container back up, behind the same gate every other start carries.

	This is the start path the SPA uses, so it is where the cap and the hold have to be. Stopping
	and deleting stay outside the gate: stopping is what a refused caller is being told to do.
	"""
	_require_container(bench)
	lifecycle.running(bench, action=action)
	return {"name": bench.name, "status": bench.status}


def _require_container(bench) -> None:
	"""Refuse a container action on an instance that has no container.

	A `Draft` instance has never been deployed and a reaped one has had its container removed,
	so handing Docker an empty id raises its own error at the user, naming nothing they can act
	on. `Bench Instance.enqueue_start` makes the same check; one message covers every action
	because the remedy is the same one.
	"""
	if not bench.container_id:
		frappe.throw(_("This instance has no container — deploy it first."))


def _stop_bench(bench) -> dict:
	"""Stop through `deploy_manager.stop_bench`, the one path that also deactivates the sites."""
	from benchpress.deploy_manager import stop_bench

	_require_container(bench)
	stop_bench(bench.name)
	return {"name": bench.name, "status": "Stopped"}


def _delete_bench(bench) -> dict:
	"""Remove an instance and everything it owns, then the row itself.

	Container, volume, site database and metering session go through
	`deploy_manager.teardown_bench`, the one teardown path, where every removal is
	best-effort. Only what it does not cover is left here.
	"""
	from benchpress.deploy_manager import teardown_bench
	from benchpress.vpn_adapter import remove_bench_peer

	teardown_bench(bench)
	# Before the instance: it reads the `Bench Site` rows, which `BenchInstance.on_trash` removes.
	_drop_bench_site_databases(bench)
	remove_bench_peer(bench)
	frappe.delete_doc("Bench Instance", bench.name, force=True)
	frappe.db.commit()
	return {"status": "deleted"}


def _drop_bench_site_databases(bench) -> None:
	"""Drop the database behind every site on this bench, one failure at a time."""
	if not bench.database_server:
		return
	from benchpress.mariadb_manager import drop_site_database

	# `get_all`, not `get_list`: a teardown has to be exhaustive, and `Bench Site` is read
	# `if_owner`, so an admin deleting somebody else's instance would silently skip their sites
	# and leave the databases behind.
	sites = frappe.get_all("Bench Site", filters={"bench": bench.name}, fields=["site_name"])
	for name in {site.site_name for site in sites if site.site_name}:
		try:
			drop_site_database(bench.database_server, name)
		except Exception:
			frappe.log_error(title=f"Failed to drop DB for {name}", message=frappe.get_traceback())


@frappe.whitelist()
def get_deploy_logs(bench_name: str) -> list[dict]:
	require_bench_access(bench_name)
	return frappe.get_list(
		"Deploy Log",
		filters={"bench": bench_name},
		fields=["name", "message", "log_type", "timestamp"],
		order_by="timestamp desc",
		limit_page_length=20,
	)


@frappe.whitelist()
def get_build_history() -> dict:
	"""Image-build runs. Scoped in `run_history`: Build Log has no query condition."""
	from benchpress.run_history import get_build_history as _get_build_history

	return _get_build_history()


@frappe.whitelist()
def get_deploy_history() -> dict:
	from benchpress.run_history import get_deploy_history as _get_deploy_history

	return _get_deploy_history()


@frappe.whitelist()
@requires_admission(caps=(cap_devices,))
def add_device(device_name: str, device_type: str, public_key: str | None = None) -> dict:
	require_app_user()
	from benchpress.vpn_adapter import register_device

	return register_device(device_name, device_type, public_key or None)


@frappe.whitelist()
def remove_device(device_name: str) -> dict:
	require_app_user()
	from benchpress.vpn_adapter import unregister_device

	unregister_device(device_name)
	return {"status": "removed"}


@frappe.whitelist()
def list_devices() -> list[dict]:
	require_app_user()
	from benchpress.vpn_adapter import list_devices as _list

	return _list()


@frappe.whitelist()
def get_device_types() -> list[str]:
	"""The device types register_device accepts, so no screen hand-types them."""
	require_app_user()
	from benchpress.vpn_adapter import DEVICE_TYPES

	return DEVICE_TYPES


@frappe.whitelist()
def get_device_wg_config(device_name: str) -> str:
	require_app_user()
	from benchpress.vpn_adapter import get_device_config

	return get_device_config(device_name)


@frappe.whitelist()
def get_user_context() -> dict:
	"""Who the caller is, and whether credits exist at all.

	The switch is exposed here rather than through an endpoint of its own so the SPA learns it in
	the call it already makes on boot, and every credit surface hides behind the same gate the API
	enforces.
	"""
	return {
		"is_admin": is_admin(),
		"user": frappe.session.user,
		"roles": frappe.get_roles(frappe.session.user),
		"credits": account.summary(frappe.session.user),
	}


@frappe.whitelist()
def get_credit_summary() -> dict:
	"""The balance chip's refresh: one indexed read, no ledger scan."""
	require_app_user()
	return account.summary(frappe.session.user)


@frappe.whitelist()
def get_credit_statement(limit_start: int = 0, limit_page_length: int = 20) -> dict:
	"""One page of the caller's own ledger. Never another user's — the filter is the session."""
	require_app_user()
	return account.statement(frappe.session.user, limit_start, limit_page_length)


@frappe.whitelist()
def get_purchase_options() -> dict:
	"""What is for sale, and whether a gateway exists to sell it."""
	require_app_user()
	return payments.purchase_options()


@frappe.whitelist()
def buy_credits(pack: str) -> dict:
	"""Open a Razorpay order for a credit pack. The price is the pack's, never the caller's."""
	require_app_user()
	return payments.buy_credits(pack)


@frappe.whitelist()
def get_lease_plans() -> list[dict]:
	"""The duration catalog the renew dialog offers, in display order."""
	require_app_user()
	return lease.active_plans()


@frappe.whitelist()
def renew_bench(bench_name: str, plan: str, request_id: str) -> dict:
	"""Buy one more lease window, extending from the deadline the caller already had.

	`request_id` is required and has no default: three tabs of impatient clicking is the ordinary
	case, and a key the server invents for a caller who sent none is not an idempotency key.

	Everything after the lock is ordered so that a refusal cannot debit — the guards run first,
	the charge last. Raises `ValidationError` when the sweep already claimed the row, when the
	plan would push the lease past the lab's ceiling, or when the grace window has closed.
	"""
	require_bench_access(bench_name)
	if not config.credits_enabled():
		frappe.throw(_("Credits are switched off on this site, so there is nothing to renew."))
	if not frappe.utils.cstr(request_id).strip():
		frappe.throw(_("A renewal needs a request id."))

	# The lock the stop job takes in `lease.confirm_expiry`, held until this transaction commits:
	# a renew and the sweep trying to end the same lease serialise here instead of racing. Every
	# decision below reads from this row and not from a cached document — under REPEATABLE READ
	# only the locking read is guaranteed to see a stop that committed a moment ago.
	bench = frappe.db.get_value("Bench Instance", bench_name, RENEW_FIELDS, as_dict=True, for_update=True)
	if bench.lease_state == lease.STOPPING:
		frappe.throw(_("This bench is already stopping. Start it again once it has, then renew."))

	# Before the replay check, not after it: that check locks the gap this account's ledger row
	# lands in, and a renewal that reaches the gap before the account row deadlocks against one
	# that took them the other way round.
	account.lock(bench.owner)
	if account.request_posted(bench.owner, request_id):
		return _lease_state(bench, charged=0.0)

	lab = frappe.get_cached_doc("Lab", bench.lab)
	chosen = _lease_plan(plan)
	_assert_within_ceiling(bench, lab, chosen)
	stopped = bench.status == "Stopped"
	if stopped:
		_assert_inside_grace(bench)
	require_balance(bench.owner, lease.cost_of(lab, chosen))

	charged = metering.charge_lease(bench, lab, chosen, request_id=request_id)
	lease.extend(bench, chosen)
	if stopped:
		_restart_in_grace(bench)
	lease.announce_renewed(bench)
	frappe.db.commit()  # nosemgrep -- releases the row lock, and the push is hung off this commit
	return _lease_state(bench, charged=charged)


def _lease_plan(plan: str) -> dict:
	row = frappe.db.get_value("Lease Plan", {"name": plan, "is_active": 1}, lease.PLAN_FIELDS, as_dict=True)
	if not row:
		frappe.throw(_("That lease duration is not on sale."))
	return row


def _assert_within_ceiling(bench, lab, plan) -> None:
	"""Refuse rather than clip: a silent clip charges the full price for less time."""
	ceiling = lease.ceiling_seconds(lab)
	if not ceiling:
		return
	if lease.remaining(bench) + frappe.utils.cint(plan.minutes) * 60 > ceiling:
		frappe.throw(
			_("A lease on this lab cannot run longer than {0} minutes in total.").format(
				frappe.utils.cint(lab.max_lease_minutes)
			)
		)


def _assert_inside_grace(bench) -> None:
	"""A stopped bench keeps its container until the reaper takes it. After that, only a redeploy."""
	grace_ends = lease.grace_ends_at(bench)
	if not bench.container_id or (grace_ends is not None and grace_ends <= lease.now_ts()):
		frappe.throw(_("This bench has been torn down. Redeploy it to start a new lease."))


def _restart_in_grace(bench) -> None:
	"""Start the container the bench still has. Expiry only stopped it, so this is not a rebuild.

	`bench` is the locked row read rather than a document, so the transition runs on a loaded
	one and the status it wrote is reflected back for the caller's response.
	"""
	doc = frappe.get_doc("Bench Instance", bench.name)
	lifecycle.running(doc)
	bench.status = doc.status


def _lease_state(bench, charged: float) -> dict:
	return {
		"name": bench.name,
		"status": bench.status,
		"expires_at_ts": frappe.utils.cint(bench.expires_at_ts),
		"grace_ends_at_ts": lease.grace_ends_at(bench) if bench.status == "Stopped" else None,
		"server_now_ms": lease.now_ms(),
		"charged": charged,
	}


@frappe.whitelist()
def get_code_server_credentials(bench_name: str) -> dict:
	require_bench_access(bench_name)
	bench = frappe.get_cached_doc("Bench Instance", bench_name)
	if bench.status != "Running":
		frappe.throw(_("Bench must be running to access code-server"))
	if not bench.code_server_url:
		frappe.throw(_("Code-server is not enabled for this lab"))
	from frappe.utils.password import get_decrypted_password

	password = get_decrypted_password("Bench Instance", bench_name, "code_server_password")
	return {"url": bench.code_server_url, "password": password}


@frappe.whitelist()
def get_bench_credentials(bench_name: str) -> dict:
	require_bench_access(bench_name)
	from frappe.utils.password import get_decrypted_password

	credentials = {}
	for field in ("ssh_password", "admin_password", "code_server_password"):
		try:
			credentials[field] = get_decrypted_password("Bench Instance", bench_name, field)
		except frappe.exceptions.ValidationError:
			credentials[field] = None
	return credentials


@frappe.whitelist()
def restart_code_server(bench_name: str) -> dict:
	require_bench_access(bench_name)
	bench = frappe.get_cached_doc("Bench Instance", bench_name)
	if bench.status != "Running" or not bench.container_id:
		frappe.throw(_("Bench must be running"))
	from benchpress.docker_manager import exec_in_container

	exit_code, output = exec_in_container(
		bench.container_id,
		"bash /opt/benchpress/scripts/restart.sh",
		user="root",
	)
	if exit_code != 0:
		frappe.throw(_("restart failed: {0}").format(output))
	return {"ok": True}


@frappe.whitelist()
def get_overview() -> dict:
	require_app_user()
	from benchpress.overview import get_overview as _get_overview

	return _get_overview()


@frappe.whitelist()
def get_vpn_status() -> dict:
	require_app_user()
	from benchpress.vpn_adapter import get_device_vpn_status

	return get_device_vpn_status()


@frappe.whitelist()
def run_connection_test() -> list[dict]:
	"""The user-facing tunnel test: their own peer, never the shared infrastructure."""
	require_app_user()
	from benchpress.connection_test import run_connection_test as _run_connection_test

	return _run_connection_test()


@frappe.whitelist()
def run_diagnostics() -> list[dict]:
	require_admin()
	from benchpress.diagnostics import run_diagnostics as _run_diagnostics

	return _run_diagnostics()


@frappe.whitelist()
def preflight_runtime(runtime: str) -> dict:
	"""Prove a runtime works, which `run_diagnostics` cannot: this one creates a container."""
	require_admin()
	from benchpress.docker_manager import preflight_runtime as _preflight_runtime

	return _preflight_runtime(runtime)
