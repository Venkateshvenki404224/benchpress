# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The one pass that compares reality against the database, in both directions.

Every other sweep converges from a row outwards and so cannot see a thing that has no row.
"""

from datetime import UTC, datetime, timedelta

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import cint, now_datetime

from benchpress import docker_manager, ingress, job_receipt, mariadb_manager, placement

# Matches `admission_repair.CLAIM_GRACE_MINUTES`, and for the same reason: `_deploy_bench` creates
# the container before it writes `container_id`, so every deploy passes through a state that looks
# exactly like an orphan.
DEFAULT_GRACE_MINUTES = 15

# Docker reports the full id and a row may hold either form; twelve characters is the form both
# share, so a live bench is never named an orphan over a difference in notation.
ID_KEY_LENGTH = 12

# Frappe's own age sweep holds `Deploy Log` at seven days. This is the second bound, for the bench
# that is redeployed in a loop and reaches thousands of rows inside one of them.
DEFAULT_DEPLOY_LOG_CAP = 50


def configured_grace_minutes() -> int:
	"""The window a container is never an orphan in, or 15 when nothing has set one."""
	return _setting("orphan_grace_minutes", DEFAULT_GRACE_MINUTES)


def configured_deploy_log_cap() -> int:
	"""Deploy Log rows kept per bench, or 50 when nothing has set one."""
	return _setting("deploy_log_cap", DEFAULT_DEPLOY_LOG_CAP)


def enqueue_run() -> None:
	"""Convergence cron: hand the whole pass to `queue-long`.

	Mints the Job Receipt row BEFORE calling `frappe.enqueue`, same mint-before-enqueue /
	checker-owns-status pattern already in production for `enqueue_route_sync` and
	`enqueue_health_check`. `logical_id` is timestamp-suffixed, not bench- or action-keyed —
	same reasoning as `enqueue_health_check`: this cron fires every five minutes and each run
	converges against *current* state (every helper below re-reads live Docker/DB/filesystem
	state rather than trusting a prior pass's report), so it is a one-shot independent check,
	not a retry of a previous tick that needs to collide into the same row. RQ's own
	`job_id="route_reconcile"` + `deduplicate=True` already collapses overlapping *enqueue*
	calls; this receipt only needs to answer "did the most recently claimed pass finish",
	never "did this exact invocation finish".
	"""
	# Scheduled jobs land on `default`, which `queue-short` also consumes — and that worker has
	# neither the Docker socket nor the route mount. So the cron entry is this and never `run`.
	logical_id = f"route_reconcile:{now_datetime().isoformat()}"
	job_receipt.mint(logical_id, expected_effect="fleet converged: routes/orphans/databases/deploy logs")
	frappe.enqueue(
		"benchpress.reconcile.run",
		queue="long",
		job_id="route_reconcile",
		logical_id=logical_id,
		deduplicate=True,
	)


def run(logical_id: str | None = None) -> dict:
	"""Converge the fleet, reporting a count for each of six steps rather than a bare success.

	By hand: `bench --site frontend execute benchpress.reconcile.run`.

	`logical_id`, when given, is the Job Receipt row minted BEFORE this job was enqueued (see
	`enqueue_run`). This function only performs the convergence steps; it never flips its own
	receipt to Completed — that is `_claim_reconcile_receipt`'s job, called below only after
	every step has actually returned, so a raise partway through this function correctly leaves
	the row Pending rather than claiming a pass that never finished.
	"""
	# Bridges first: a bench that cannot reach MariaDB is broken on a dev checkout too, where
	# there is no routing at all.
	bridges = placement.repair()
	routes = _converge_routes()
	containers = _reap_orphan_containers()
	databases = _report_orphan_databases()
	deploy_records = _trim_deploy_records()
	result = {
		"bridges": bridges,
		"routes": routes,
		"containers": containers,
		"databases": databases,
		"deploy_records": deploy_records,
		"verified": _verify_reaped(containers["removed"]),
	}
	if logical_id:
		_claim_reconcile_receipt(logical_id)
	return result


def _claim_reconcile_receipt(logical_id: str) -> None:
	"""Claim the receipt only once every convergence step has returned without raising.

	Unlike `mariadb_manager._claim_health_check_receipt`, there is no independent live re-check
	here beyond "did `run()` reach its final line" — the six steps above are themselves each
	already a live-state convergence (not a self-report of a prior claim), so reaching this
	point already means the daemon/DB/filesystem were read fresh this pass. What this receipt
	still guards against is a worker dying mid-pass (killed, OOM) with no raise at all: that
	leaves the row Pending, correctly distinguishable from a pass that actually completed.
	"""
	job_receipt.mark_completed(logical_id)


def compare(rows: list[dict], containers: list[dict], *, grace_minutes: int | None = None) -> dict:
	"""Name the drift both ways. It reads neither side — both arrive as arguments.

	`grace_minutes` defaults to the configured window, which is the only thing this reads.
	"""
	window = configured_grace_minutes() if grace_minutes is None else grace_minutes
	cutoff = datetime.now(UTC) - timedelta(minutes=window)

	claimed = {_id_key(row.get("container_id")) for row in rows if row.get("container_id")}
	live = {_id_key(container.get("id")) for container in containers if container.get("id")}

	orphans, in_grace = [], []
	for container in containers:
		if _id_key(container.get("id")) in claimed:
			continue
		if _older_than(container.get("created"), cutoff):
			orphans.append(container)
		else:
			in_grace.append(container)

	missing = [row for row in rows if row.get("container_id") and _id_key(row["container_id"]) not in live]

	return {"orphan_containers": orphans, "in_grace": in_grace, "missing_containers": missing}


def _converge_routes() -> dict:
	"""Make the Traefik route directory agree with the database."""
	# The directory path and the protected filenames stay in `ingress`. One off-by-one here would
	# take the control plane off the internet, or every bench's certificate with it.
	base_domain = frappe.get_cached_doc("BenchPress Settings").base_domain
	if not base_domain or base_domain == "localhost":
		# A dev checkout has no route directory and must stay byte-for-byte unaffected.
		return {"anchored": False, "written": 0, "deleted": 0, "kept": 0}

	# Record before the gate, not after it. `ensure_anchor` below is the only other recurring
	# caller of `record_directory_state`, so returning here without recording left the one host
	# this reports on — a bench whose worker has no route mount — with no report at all, and the
	# diagnostics row blaming a healthy scheduler instead of the missing mount.
	if not ingress.record_directory_state()["mounted"]:
		# None rather than 0, because the directory was never read and zero counts would read as
		# a converged pass.
		return {"anchored": None, "written": None, "deleted": None, "kept": None}

	anchored = ingress.ensure_anchor(base_domain)
	routable = ingress.routable()
	for instance_id, (ide, limits) in routable.items():
		ingress.publish(instance_id, base_domain, ide=ide, limits=limits)

	stale = ingress.published() - routable.keys()
	for instance_id in stale:
		ingress.withdraw(instance_id)

	return {
		"anchored": anchored,
		"written": len(routable),
		"deleted": len(stale),
		"kept": ingress.protected_present(),
	}


def _reap_orphan_containers() -> dict:
	"""Remove every managed container past the grace window that no row claims."""
	# `list_benches` filters on `benchpress.managed=true` at the daemon, so a container this app
	# did not create is never a candidate. That label is the whole authority for the removal.
	drift = compare(_bench_rows(), docker_manager.list_benches())
	removed = [container["id"] for container in drift["orphan_containers"]]
	for container_id in removed:
		_remove(container_id)
	return {
		"orphans": len(removed),
		# The ids a removal was *issued* for. Whether they are gone is `_verify_reaped`'s answer.
		"removed": removed,
		"in_grace": len(drift["in_grace"]),
		"missing_rows": len(drift["missing_containers"]),
	}


def _verify_reaped(issued: list[str]) -> dict:
	"""Ask the daemon whether the removals took, re-issue the ones that did not, and report."""
	# The step the pass exists for: a reaper that reports what it issued rather than what is gone
	# is how a container keeps running underneath a report saying "converged".
	if not issued:
		return {"rechecked": 0, "reissued": 0, "reaped": 0, "still_present": []}

	still = _present(issued)
	for container_id in still:
		_remove(container_id)
	remaining = _present(still)
	if remaining:
		frappe.log_error(
			title="BenchPress reconcile could not remove an orphan container",
			message="\n".join(remaining),
		)
		frappe.db.commit()  # nosemgrep -- a background pass has no request boundary to commit at

	return {
		"rechecked": len(issued),
		"reissued": len(still),
		"reaped": len(issued) - len(remaining),
		"still_present": remaining,
	}


def _report_orphan_databases() -> dict:
	"""Count and name the schemas no row claims, per server. Nothing here drops one."""
	# Reporting is the decision, not an omission: a `DROP` on a bench mid-deploy is a tenant's
	# whole data with no undo, and `torn_down` now says when the drop it owns failed.
	claimed = _claimed_databases()
	schemas = 0
	unclaimed = {}
	for server in _database_servers():
		names = _site_databases(server)
		schemas += len(names)
		orphans = sorted(name for name in names if name not in claimed)
		if orphans:
			unclaimed[server] = orphans
	return {
		"schemas": schemas,
		"orphans": sum(len(names) for names in unclaimed.values()),
		"names": unclaimed,
	}


def _trim_deploy_records() -> dict:
	"""Hold each bench to the newest `cap` Deploy Log rows, on top of Frappe's 7-day age sweep."""
	cap = configured_deploy_log_cap()
	deleted = 0
	over = _benches_over_cap(cap)
	for row in over:
		stale = frappe.get_all(
			"Deploy Log",
			filters={"bench": row.bench},
			pluck="name",
			order_by="timestamp desc, creation desc",
			offset=cap,
			limit=row.rows - cap,
		)
		if not stale:
			continue
		frappe.db.delete("Deploy Log", {"name": ("in", stale)})
		deleted += len(stale)
	if deleted:
		frappe.db.commit()  # nosemgrep -- a background pass has no request boundary to commit at
	return {"benches": len(over), "deleted": deleted, "cap": cap}


def _benches_over_cap(cap: int) -> list[dict]:
	"""Benches holding more than `cap` Deploy Log rows, and how many each holds."""
	log = frappe.qb.DocType("Deploy Log")
	return (
		frappe.qb.from_(log)
		.select(log.bench, Count(log.name).as_("rows"))
		.where(log.bench.isnotnull())
		.groupby(log.bench)
		.having(Count(log.name) > cap)
		.run(as_dict=True)
	)


def _bench_rows() -> list[dict]:
	return frappe.get_all("Bench Instance", fields=["name", "container_id", "status"])


def _database_servers() -> list[str]:
	return frappe.get_all("Database Server", pluck="name")


def _claimed_databases() -> set[str]:
	"""Every schema a row accounts for. A bench holds its site name before its `Bench Site` exists."""
	names = frappe.get_all("Bench Site", pluck="site_name") + frappe.get_all(
		"Bench Instance", pluck="site_name"
	)
	bench_databases = frappe.get_all("Bench Database", pluck="db_name", parent_doctype="Bench Instance")
	return {mariadb_manager.get_database_name(name) for name in names if name} | set(bench_databases)


def _site_databases(server: str) -> list[str]:
	"""One server's schemas, or none when it cannot be reached — a read must not end the pass."""
	try:
		return mariadb_manager.list_site_databases(server)
	except Exception as exc:
		frappe.logger("benchpress").warning(f"could not list databases on {server}: {exc}")
		return []


def _present(container_ids: list[str]) -> list[str]:
	"""Which of these the daemon still lists — read from the daemon, never from the removal's report."""
	live = {_id_key(container["id"]) for container in docker_manager.list_benches()}
	return [container_id for container_id in container_ids if _id_key(container_id) in live]


def _remove(container_id: str) -> None:
	"""Issue one removal. Never raises: one container the daemon refuses must not end the pass."""
	try:
		docker_manager.remove_container(container_id)
	except Exception as exc:
		frappe.logger("benchpress").warning(f"orphan {_id_key(container_id)} not removed: {exc}")


def _setting(fieldname: str, fallback: int) -> int:
	"""`.get` rather than attribute access: a Single holds only the fields somebody has saved."""
	return cint(frappe.get_cached_doc("BenchPress Settings").get(fieldname)) or fallback


def _id_key(container_id) -> str:
	return (container_id or "")[:ID_KEY_LENGTH]


def _older_than(created, cutoff: datetime) -> bool:
	"""Whether a container is old enough to be judged. A container of unknown age never is."""
	return bool(created) and created < cutoff
