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
"""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

DOCTYPE = "Job Receipt"


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
	"""
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.status == "Pending":
		doc.status = "Unknown"
		doc.save(ignore_permissions=True)
	return doc.status


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
		return "requeue"

	if minted_hash == current_policy_hash:
		return "requeue"

	return "remediate"
