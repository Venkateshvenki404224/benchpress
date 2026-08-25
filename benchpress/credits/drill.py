# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Setup and teardown for `scripts/admission_drill.py`, the concurrency drill.

Nothing here is whitelisted, and nothing here may become whitelisted: cleanup deletes with
`force=True` and has no business being reachable over HTTP. The harness reaches it through
`bench --site frontend execute benchpress.credits.drill.<fn>`.

The drill fires one caller at **N distinct labs**. `get_instance_id` is `md5(email + lab)`, so
N calls naming one lab all name the same bench - a same-lab drill would hold at the cap because
there was only ever one thing to admit, and would report a pass against a gate that does
nothing. Distinct labs are the whole point.
"""

import frappe
from frappe.utils import cint

from benchpress.credits import account, config

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"
LEDGER = "Credit Ledger Entry"

DRILL_USER = "admission-drill@example.com"
DRILL_ROLE = "BenchPress User"
LAB_PREFIX = "drill-"
DRILL_BALANCE = 100000.0


def setup(workers: int = 12, cap: int = 1) -> dict:
	"""Open the drill account, mint its labs and its token, and set the cap. Idempotent.

	Returns everything the harness needs, including `cap_field` and `cap_before` so it can put
	the site's own cap back: which field the limit comes from depends on whether credits are on,
	and the drill must not assume.
	"""
	workers = cint(workers)
	user = _ensure_user()
	labs = [_ensure_lab(index) for index in range(workers)]
	_fund(user)
	cap_field, cap_before = _set_cap(cap)
	frappe.db.commit()
	return {
		"user": user,
		"api_key": frappe.db.get_value("User", user, "api_key"),
		"api_secret": _api_secret(user),
		"labs": labs,
		"base_domain": frappe.db.get_single_value("BenchPress Settings", "base_domain"),
		"credits_enabled": bool(config.credits_enabled()),
		"cap_field": cap_field,
		"cap_before": cap_before,
		"cap": cint(cap),
	}


def ensure_drill_user() -> str:
	"""Open the drill user and its API keys on their own, and return the token as `key:secret`.

	Separate from `setup` so a caller can get the token without minting labs or moving the cap.
	"""
	user = _ensure_user()
	frappe.db.commit()
	return f"{frappe.db.get_value('User', user, 'api_key')}:{_api_secret(user)}"


def restore(cap_field: str, cap_before) -> dict:
	"""Put the site's own concurrency cap back."""
	frappe.db.set_single_value("Credit Settings", cap_field, cint(cap_before))
	frappe.clear_cache(doctype="Credit Settings")
	frappe.db.commit()
	return {cap_field: cint(cap_before)}


def report() -> dict:
	"""What the drill asserts on: the counter, and the rows the counter is meant to count."""
	return {
		"user": DRILL_USER,
		"active_instances": cint(frappe.db.get_value(ACCOUNT, DRILL_USER, "active_instances")),
		"admission_rows": frappe.db.count(ADMISSION, {"account": DRILL_USER}),
		"benches": frappe.db.count(BENCH, {"owner": DRILL_USER}),
	}


def stage_real_lab(image_tag: str, size: str = "Small") -> str:
	"""A drill lab whose image already exists, for the runs that need a container to appear.

	It carries the `drill-` prefix like every other drill lab, so `cleanup` tears down whatever
	it deployed rather than leaving a container behind.
	"""
	lab_id = f"{LAB_PREFIX}real"
	if not frappe.db.exists("Lab", lab_id):
		frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": "Admission drill (real image)",
				"frappe_version": "version-15",
				"image_tag": image_tag,
				"instance_size": size,
				"enable_code_server": 0,
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	return lab_id


def purge_deploy_jobs() -> dict:
	"""Cancel the deploy jobs the drill's own requests queued. Call before any worker restarts.

	`enqueue_after_commit=True` pushes to Redis when the request commits, so stopping the worker
	delays a deploy rather than preventing it. Restarting one at the end of a run would deploy
	every bench the drill just admitted, on a host with 18 GB free.
	"""
	from frappe.utils.background_jobs import get_job

	cancelled = []
	for bench in _drill_benches():
		job = get_job(f"deploy_bench:{bench}")
		if not job:
			continue
		try:
			job.cancel()
		except Exception:
			continue  # already running or already gone; either way it is not ours to stop
		cancelled.append(bench)
	return {"cancelled": len(cancelled)}


def cleanup() -> dict:
	"""Remove everything the drill made, filtered by the drill user and the `drill-` labs.

	Never by status and never by owner alone: this runs on a host serving real tenants, and a
	filter that reads "everything this user owns" is one typo away from being everything.
	"""
	labs = frappe.get_all("Lab", filters={"lab_id": ("like", f"{LAB_PREFIX}%")}, pluck="name")
	benches = _drill_benches()
	for bench in benches:
		_delete_bench(bench)
	frappe.db.delete(ADMISSION, {"account": DRILL_USER})
	for lab in labs:
		frappe.delete_doc("Lab", lab, force=True, ignore_permissions=True)
	frappe.db.delete(LEDGER, {"account": DRILL_USER})
	frappe.db.delete(ACCOUNT, {"user": DRILL_USER})
	frappe.db.commit()
	return {
		"benches": len(benches),
		"labs": len(labs),
		"active_instances": cint(frappe.db.get_value(ACCOUNT, DRILL_USER, "active_instances")),
		"admission_rows": frappe.db.count(ADMISSION, {"account": DRILL_USER}),
	}


def _drill_benches() -> list[str]:
	labs = frappe.get_all("Lab", filters={"lab_id": ("like", f"{LAB_PREFIX}%")}, pluck="name")
	if not labs:
		return []
	return frappe.get_all(BENCH, filters={"owner": DRILL_USER, "lab": ("in", labs)}, pluck="name")


def _delete_bench(bench_name: str) -> None:
	from benchpress.deploy_manager import teardown_bench
	from benchpress.vpn_adapter import remove_bench_peer

	bench = frappe.get_doc(BENCH, bench_name)
	if bench.container_id:
		try:
			teardown_bench(bench)
			remove_bench_peer(bench)
		except Exception:
			# Best-effort, and named rather than swallowed: a drill container the harness cannot
			# reach is an operator's problem, not a silent leak.
			frappe.logger("benchpress").warning(f"drill: could not tear down {bench_name}")
	for site in frappe.get_all("Bench Site", filters={"bench": bench_name}, pluck="name"):
		frappe.delete_doc("Bench Site", site, force=True, ignore_permissions=True)
	frappe.delete_doc(BENCH, bench_name, force=True, ignore_permissions=True)


def _ensure_user() -> str:
	if not frappe.db.exists("User", DRILL_USER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": DRILL_USER,
				"first_name": "Admission",
				"last_name": "Drill",
				"send_welcome_email": 0,
				"roles": [{"role": DRILL_ROLE}],
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", DRILL_USER)
	if DRILL_ROLE not in {row.role for row in user.roles}:
		user.append("roles", {"role": DRILL_ROLE})
	user.api_key = user.api_key or frappe.generate_hash(length=15)
	if not _api_secret(user.name):
		user.api_secret = frappe.generate_hash(length=15)
	user.save(ignore_permissions=True)
	return user.name


def _api_secret(user: str) -> str | None:
	# Absent rather than an exception: the row exists before its key does.
	return frappe.utils.password.get_decrypted_password("User", user, "api_secret", raise_exception=False)


def _ensure_lab(index: int) -> str:
	lab_id = f"{LAB_PREFIX}{index}"
	if frappe.db.exists("Lab", lab_id):
		return lab_id
	return (
		frappe.get_doc(
			{
				"doctype": "Lab",
				"lab_id": lab_id,
				"title": f"Admission drill {index}",
				"frappe_version": "version-15",
				# A tag that exists nowhere: with deploys disabled nothing reads it, and with
				# them enabled a pull failure is a far cheaper mistake than a real build.
				"image_tag": "benchpress/admission-drill:latest",
				"instance_size": config.default_size().name if config.default_size() else None,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _fund(user: str) -> None:
	"""Enough credits that nothing is refused for the wrong reason. Set, not granted.

	The drill measures the concurrency claim. A shortfall refusal would fail it for a reason
	that has nothing to do with what is being measured, and a real grant would leave money on a
	live site's ledger.
	"""
	account.ensure_account(user)
	frappe.db.set_value(ACCOUNT, user, "balance", DRILL_BALANCE, update_modified=False)


def _set_cap(cap: int) -> tuple[str, int]:
	field = "max_concurrent_free" if config.credits_enabled() else "max_concurrent_uncredited"
	before = cint(frappe.db.get_single_value("Credit Settings", field))
	frappe.db.set_single_value("Credit Settings", field, cint(cap))
	frappe.clear_cache(doctype="Credit Settings")
	return field, before
