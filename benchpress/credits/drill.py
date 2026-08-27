# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Setup and teardown for `scripts/admission_drill.py`, the admission drill.

Nothing here is whitelisted, and nothing here may become whitelisted: cleanup deletes with
`force=True` and has no business being reachable over HTTP. The harness reaches it through
`bench --site frontend execute benchpress.credits.drill.<fn>`.

The drill fires one caller at **N distinct labs**. `get_instance_id` is `md5(email + lab)`, so
N calls naming one lab all name the same bench - a same-lab drill would hold at the cap because
there was only ever one thing to admit, and would report a pass against a gate that does
nothing. Distinct labs are the whole point.

There are three modes. `cap` moves the concurrency limit and funds the account past anything it
could be refused for; `credits` lifts the limit and funds it with exactly three leases;
`site-name` lifts the limit, funds it the same way as `cap`, and points every request at one
site name. Each one has to be able to fail for its own reason and no other.
"""

import frappe
from frappe.utils import cint, flt

from benchpress import lifecycle
from benchpress.credits import account, config

ACCOUNT = "Credit Account"
ADMISSION = "Bench Admission"
BENCH = "Bench Instance"
LEDGER = "Credit Ledger Entry"
SITE = "Bench Site"

DRILL_USER = "admission-drill@example.com"
DRILL_ROLE = "BenchPress User"
LAB_PREFIX = "drill-"

# The one name `site-name` mode makes every request ask for. A bare label, because
# `site_names.qualify` adds the domain and rejects anything carrying its own.
SITE_LABEL = "drill-site"

# A mode that measures anything other than the count has to lift the count, or it would pass by
# refusing on the cap instead of on what it came to measure.
UNCAPPED_MODES = ("credits", "site-name")

# Every drill lab prices its own lease, so what a drill admission costs does not depend on which
# plan the site happens to default to. `credits` mode divides a balance by this and expects the
# quotient.
LEASE_PRICE = 1.0

# `cap` mode measures the concurrency claim, so its account is funded past anything it could be
# refused for. `credits` mode measures the hold, so its account affords exactly three of them.
CAP_MODE_BALANCE = 100000.0
CREDIT_MODE_BALANCE = 3.0


def setup(workers: int = 12, cap: int = 1, mode: str = "cap") -> dict:
	"""Open the drill account, mint its labs and its token, and set the cap. Idempotent.

	Returns everything the harness needs, including `cap_field` and `cap_before` so it can put
	the site's own cap back: which field the limit comes from depends on whether credits are on,
	and the drill must not assume.

	`credits` and `site-name` modes lift the cap to unlimited, because a run that measures
	anything else must not be able to pass by refusing on the count instead.
	"""
	workers = cint(workers)
	user = _ensure_user()
	labs = [_ensure_lab(index) for index in range(workers)]
	balance = CREDIT_MODE_BALANCE if mode == "credits" else CAP_MODE_BALANCE
	_fund(user, balance)
	cap = 0 if mode in UNCAPPED_MODES else cint(cap)
	cap_field, cap_before = _set_cap(cap)
	base_domain = frappe.db.get_single_value("BenchPress Settings", "base_domain")
	frappe.db.commit()  # nosemgrep -- the drill's workers are separate processes and cannot see uncommitted fixtures
	return {
		"user": user,
		"api_key": frappe.db.get_value("User", user, "api_key"),
		"api_secret": _api_secret(user),
		"labs": labs,
		"base_domain": base_domain,
		"site_label": SITE_LABEL if mode == "site-name" else None,
		"site_name": f"{SITE_LABEL}.{base_domain}" if mode == "site-name" else None,
		"credits_enabled": bool(config.credits_enabled()),
		"cap_field": cap_field,
		"cap_before": cap_before,
		"cap": cap,
		"mode": mode,
		"balance": balance,
		"lease_price": LEASE_PRICE,
	}


def ensure_drill_user() -> str:
	"""Open the drill user and its API keys on their own, and return the token as `key:secret`.

	Separate from `setup` so a caller can get the token without minting labs or moving the cap.
	"""
	user = _ensure_user()
	frappe.db.commit()  # nosemgrep -- the token has to exist for a process that is not this one
	return f"{frappe.db.get_value('User', user, 'api_key')}:{_api_secret(user)}"


def restore(cap_field: str, cap_before) -> dict:
	"""Put the site's own concurrency cap back."""
	frappe.db.set_single_value("Credit Settings", cap_field, cint(cap_before))
	frappe.clear_cache(doctype="Credit Settings")
	frappe.db.commit()  # nosemgrep -- the cap must go back even if the caller dies mid-request
	return {cap_field: cint(cap_before)}


def report(site_name: str | None = None) -> dict:
	"""What the drill asserts on: the counter, and the rows the counter is meant to count.

	`site_name` is the contended name in `site-name` mode, and the two counts it adds are how
	many rows and how many instances believe they own it. Both must read 1.
	"""
	row = frappe.db.get_value(
		ACCOUNT, DRILL_USER, ["active_instances", "reserved_credits", "balance"], as_dict=True
	)
	return {
		"user": DRILL_USER,
		"named_sites": frappe.db.count(SITE, {"site_name": site_name}) if site_name else 0,
		"named_benches": frappe.db.count(BENCH, {"site_name": site_name}) if site_name else 0,
		"active_instances": cint(row.active_instances) if row else 0,
		"reserved_credits": flt(row.reserved_credits) if row else 0.0,
		"balance": flt(row.balance) if row else 0.0,
		"admission_rows": frappe.db.count(ADMISSION, {"account": DRILL_USER}),
		"held_credits": flt(_held_total()),
		"benches": frappe.db.count(BENCH, {"owner": DRILL_USER}),
	}


def _held_total() -> float:
	rows = frappe.get_all(ADMISSION, filters={"account": DRILL_USER}, pluck="held_credits")
	return sum(flt(held) for held in rows)


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
	frappe.db.commit()  # nosemgrep -- the workers deploy against this lab from their own processes
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
	frappe.db.commit()  # nosemgrep -- cleanup on a host serving real tenants must be durable
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
	from benchpress.vpn_adapter import remove_bench_peer

	bench = frappe.get_doc(BENCH, bench_name)
	if bench.container_id:
		try:
			lifecycle.torn_down(bench)
			remove_bench_peer(bench)
		except Exception:
			# Best-effort, and named rather than swallowed: a drill container the harness cannot
			# reach is an operator's problem, not a silent leak.
			frappe.logger("benchpress").warning(f"drill: could not tear down {bench_name}")
	for site in frappe.get_all(SITE, filters={"bench": bench_name}, pluck="name"):
		frappe.delete_doc(SITE, site, force=True, ignore_permissions=True)
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
	"""One drill lab, priced at `LEASE_PRICE`. Re-priced on every run, because a lab outlives one."""
	lab_id = f"{LAB_PREFIX}{index}"
	if frappe.db.exists("Lab", lab_id):
		frappe.db.set_value("Lab", lab_id, "deploy_credits", LEASE_PRICE, update_modified=False)
		frappe.clear_document_cache("Lab", lab_id)
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
				"deploy_credits": LEASE_PRICE,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _fund(user: str, balance: float) -> None:
	"""Set the drill account to exactly `balance`, holding nothing. Set, not granted.

	Set rather than granted because a real grant would leave money on a live site's ledger, and
	exactly rather than at least because `credits` mode divides this figure by the lease price
	and expects the quotient. The claims and the aggregates go with it: a previous run that was
	not cleaned up would otherwise start this one with credits already reserved.
	"""
	account.ensure_account(user)
	frappe.db.delete(ADMISSION, {"account": user})
	frappe.db.set_value(
		ACCOUNT,
		user,
		{"balance": flt(balance), "active_instances": 0, "reserved_credits": 0.0},
		update_modified=False,
	)


def _set_cap(cap: int) -> tuple[str, int]:
	field = "max_concurrent_free" if config.credits_enabled() else "max_concurrent_uncredited"
	before = cint(frappe.db.get_single_value("Credit Settings", field))
	frappe.db.set_single_value("Credit Settings", field, cint(cap))
	frappe.clear_cache(doctype="Credit Settings")
	return field, before
