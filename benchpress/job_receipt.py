"""Independent async-job verification ledger — mint-before-enqueue, checker owns status.

Converged with other agents on Moltbook (post `dbc7c272-...`, "how to verify async job
completion") across many threads (fairline, johnnybucks, starnose_ai, synapseguide,
hermessol) and logged as a settled pattern in
~/kb/concepts/moltbook-engineering-learning-loop.md (2026-09-30 entry, retrofit tracked in
Hive TASK-00149/00235/00139).

The five-part shape this DocType exists to enforce:
1. Mint a `logical_id` here BEFORE calling `frappe.enqueue`, independent of RQ's own
   `job_id`. This row is what a caller trusts — never the queue library's job object.
2. The worker writes ONLY the artifact (with `logical_id` embedded in it). It must never
   call `mark_completed` on its own row — a worker self-reporting its own success inherits
   the exact unreliability class this ledger exists to replace (fairline's caution on this
   exact post: "a status write that succeeds while the artifact write fails produces a
   green row on a failed job").
3. A separate reader/checker calls `mark_completed(logical_id)` only after it has read the
   artifact back BY THE MINTED ID (identity check, not just existence check).
4. `mark_unknown_if_overdue` — absence by deadline is UNKNOWN, never FAILED. FAILED is
   reserved for an actually-observed failure signal.
5. Callers running a recurring checker should write a heartbeat row of their own (not part
   of this DocType) so a checker that silently stopped is distinguishable from one that
   correctly found nothing pending.

policy_hash (added 2026-10-08, Hive TASK-03652):
   Callers may pass `policy_hash` to `mint()` — a SHA-256 hex digest of whatever
   dispatch-time facts authorized the job (e.g. bench status, grant scope, config
   snapshot). When a job reaches Unknown or Failed and a retry is considered,
   `requeue_or_remediate()` compares the caller's CURRENT policy hash against the one
   frozen at mint time: same → "requeue" (safe to retry the original effect); different →
   "remediate" (the authorization context has changed; the caller must re-derive what to
   do rather than blindly replaying).  Closes the requeue-carries-a-stale-grant gap
   identified on Moltbook (M56, neo_konsi_s2bw, TASK-00184/TASK-00208).

   `requeue_or_remediate` also distinguishes "no baseline to compare" from "policy
   definitely changed": a receipt minted before `policy_hash` existed (minted_hash is
   None) checked against a caller that now HAS a hash returns "unknown", not
   "remediate" — collapsing "we don't know if policy changed" into "policy changed" was
   a silent correctness bug on every pre-migration row (Moltbook umiXBT, post
   5a411cda-84aa-42a7-97b3-ca3e118b2507, comment bc8ef958; Hive TASK-03700/TASK-03704).
   The caller must treat "unknown" as its own disposition — a bounded manual/
   reconciliation path, never auto-requeue and never auto-remediate on a guess.
"""

from __future__ import annotations

import frappe
from frappe.desk.form.assign_to import add as assign_to_add
from frappe.utils import add_to_date, now_datetime

DOCTYPE = "Job Receipt"

# How long a reconciliation obligation gets before it is itself overdue. Separate from
# OVERDUE_GRACE_MINUTES below: that constant decides when a Pending row becomes Unknown; this
# one decides how long a human has to resolve an Unknown row once it exists. Named on Moltbook
# (umiXBT, post 5a411cda-84aa-42a7-97b3-ca3e118b2507, comment 03cbb6d7): "an unknown disposition
# must create a reconciliation obligation with an owner and deadline, so a future caller cannot
# silently collapse it back into either automatic action."
RECONCILE_SLA_HOURS = 24

# How long a Pending receipt is given before the sweep below calls it Unknown. No single
# caller's job runtime is authoritative here (reconcile.run, health checks, and future
# callers all differ), so this is a deliberately generous ceiling rather than a per-caller
# deadline — a receipt still Pending after half an hour has either lost its worker or its
# artifact-read, and either way "we don't know" is the correct and only honest answer.
OVERDUE_GRACE_MINUTES = 30

# requeue_or_remediate()'s own return values, distinct from the DocType's `status` field.
REQUEUE_DISPOSITION_REQUEUE = "requeue"
REQUEUE_DISPOSITION_REMEDIATE = "remediate"
REQUEUE_DISPOSITION_UNKNOWN = "unknown"


def mint(logical_id: str, expected_effect: str, policy_hash: str | None = None) -> None:
	"""Open the ledger row BEFORE the enqueue call. Idempotent on `logical_id`.

	Called by the producer, in the same transaction as the `frappe.enqueue` call that
	follows it — if the enqueue itself raises, the row still records what was attempted,
	which is the entire point: the row must not depend on the enqueue call succeeding.

	`policy_hash`, when supplied, is a caller-computed SHA-256 hex digest of the
	dispatch-time authorization inputs (e.g. bench status, grant scope).  A later
	call to `requeue_or_remediate()` uses it to decide whether a retry is safe.
	"""
	if frappe.db.exists(DOCTYPE, {"logical_id": logical_id}):
		return
	doc = frappe.new_doc(DOCTYPE)
	doc.logical_id = logical_id
	doc.expected_effect = expected_effect
	doc.status = "Pending"
	doc.minted_at = now_datetime()
	if policy_hash is not None:
		doc.policy_hash = policy_hash
	doc.insert(ignore_permissions=True)


def mark_completed(logical_id: str) -> None:
	"""Called ONLY by the independent checker, after it has read the artifact back by id.

	Never call this from inside the worker job itself — see module docstring, point 2.
	"""
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.status == "Completed":
		return  # idempotent: a checker re-run after its own successful write is a no-op
	doc.status = "Completed"
	doc.claimed_at = now_datetime()
	doc.completed_at = now_datetime()
	doc.save(ignore_permissions=True)


def mark_unknown_if_overdue(logical_id: str) -> str:
	"""Flip Pending -> Unknown once the expected window has passed with no artifact found.

	Returns the resulting status. Never writes Failed here — Failed is reserved for an
	actually-observed failure signal (an error artifact, a dead worker record), which this
	function has no way to see; it only knows "not found yet by this deadline".

	The transition itself also opens the reconciliation obligation (see
	`_open_reconciliation_obligation`) — an Unknown row with nobody assigned to look at it is
	indistinguishable from one nobody noticed, which is the exact silent-collapse umiXBT named.
	"""
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.status == "Pending":
		doc.status = "Unknown"
		doc.save(ignore_permissions=True)
		_open_reconciliation_obligation(doc)
	return doc.status


def _open_reconciliation_obligation(doc) -> None:
	"""Assign a ToDo (owner + deadline) the moment a receipt lands in Unknown.

	Deliberately a `ToDo` via `assign_to.add` rather than a bare field on `Job Receipt` —
	`frappe.desk.form.assign_to` is the one path that produces a real, assignee-filtered,
	due-date-bearing row Desk's own "My Assignments" view surfaces, which is what makes the
	obligation visible instead of a status value nobody is ever shown. The caller (`mark_unknown_if_overdue`)
	only invokes this once, on the Pending->Unknown transition itself, so this never double-assigns
	on a re-run against an already-Unknown row — the guard below exists so a direct call against
	the wrong status fails loudly instead of silently assigning twice.
	"""
	if doc.status != "Unknown":
		raise ValueError("_open_reconciliation_obligation called on a non-Unknown receipt")
	owners = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
	)
	owner = owners[0] if owners else "Administrator"
	assign_to_add(
		{
			"doctype": DOCTYPE,
			"name": doc.name,
			"assign_to": [owner],
			"description": (
				f"Job Receipt {doc.name} ({doc.logical_id}) landed Unknown: "
				f"{doc.expected_effect}. Confirm by deadline whether the effect happened; "
				"do not auto-requeue or auto-remediate on a guess."
			),
			"date": add_to_date(now_datetime(), hours=RECONCILE_SLA_HOURS),
		}
	)


def sweep_overdue_pending() -> dict:
	"""Scheduled caller for `mark_unknown_if_overdue` — the gap named on Moltbook

	(umiXBT/midearthguild, post `5a411cda-84aa-42a7-97b3-ca3e118b2507`) and tracked as
	Hive TASK-03454/TASK-03719: `mark_unknown_if_overdue` existed and was tested, but had
	zero production callers, so a Pending receipt whose worker died or whose checker never
	ran stayed Pending forever — indistinguishable from "still running" no matter how much
	time passed. This is the independent reader that makes the Unknown transition actually
	happen on a clock instead of only on demand.

	Scans every receipt still `Pending` whose `minted_at` is older than
	`OVERDUE_GRACE_MINUTES` and flips each to Unknown via `mark_unknown_if_overdue` (which
	is itself idempotent and leaves anything already Completed/Failed alone). Returns a
	count rather than a bare success so the caller/cron log shows whether this pass found
	anything, same convention as `reconcile.run`.
	"""
	cutoff = add_to_date(now_datetime(), minutes=-OVERDUE_GRACE_MINUTES)
	overdue_ids = frappe.get_all(
		DOCTYPE,
		filters={"status": "Pending", "minted_at": ("<", cutoff)},
		pluck="logical_id",
	)
	flipped = []
	for logical_id in overdue_ids:
		if mark_unknown_if_overdue(logical_id) == "Unknown":
			flipped.append(logical_id)
	return {"checked": len(overdue_ids), "flipped_to_unknown": flipped}


def mark_failed(logical_id: str, reason: str) -> None:
	"""Called only when a worker crash or dead-worker record is actually observed."""
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)
	doc.status = "Failed"
	doc.save(ignore_permissions=True)
	frappe.log_error(title="Job Receipt failed", message=f"{logical_id}: {reason}")


def requeue_or_remediate(logical_id: str, current_policy_hash: str | None = None) -> str:
	"""Decide whether a non-terminal job should be requeued or escalated for remediation.

	Intended for Unknown or Failed receipts where the caller is considering a retry.
	Returns one of:
	  "requeue"    — policy hash matches (or neither side has one); safe to enqueue the
	                 original effect again unchanged.
	  "remediate"  — policy hash has changed; the authorization context that produced this
	                 job no longer holds, so a blind retry would carry a stale grant.  The
	                 caller must re-derive the intended action before enqueuing anything.
	  "unknown"    — the minted receipt predates `policy_hash` (no baseline was recorded),
	                 so there is nothing to compare the caller's current hash against.
	                 This is NOT evidence that policy changed, nor that it didn't — the
	                 caller must route this to manual/reconciliation review rather than
	                 guessing either "requeue" or "remediate".

	If the receipt is still Pending or already Completed this function raises
	`ValueError` — there is nothing to retry in those states.

	Raises `frappe.DoesNotExistError` if `logical_id` was never minted.
	"""
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)

	if doc.status not in ("Unknown", "Failed"):
		raise ValueError(
			f"requeue_or_remediate called on a {doc.status!r} receipt — "
			"only Unknown or Failed receipts are candidates for retry"
		)

	minted_hash = doc.policy_hash or None

	if minted_hash is None and current_policy_hash is None:
		return REQUEUE_DISPOSITION_REQUEUE

	if minted_hash is None and current_policy_hash is not None:
		# No baseline was recorded at mint time (pre-`policy_hash` receipt). We cannot
		# tell "policy changed" from "we never captured a baseline" — that is a
		# migration-era data gap, not a policy decision, so it must not silently
		# inherit "remediate"'s semantics.
		return REQUEUE_DISPOSITION_UNKNOWN

	if minted_hash == current_policy_hash:
		return REQUEUE_DISPOSITION_REQUEUE

	return REQUEUE_DISPOSITION_REMEDIATE
