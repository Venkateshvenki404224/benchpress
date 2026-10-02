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
"""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

DOCTYPE = "Job Receipt"


def mint(logical_id: str, expected_effect: str) -> None:
	"""Open the ledger row BEFORE the enqueue call. Idempotent on `logical_id`.

	Called by the producer, in the same transaction as the `frappe.enqueue` call that
	follows it — if the enqueue itself raises, the row still records what was attempted,
	which is the entire point: the row must not depend on the enqueue call succeeding.
	"""
	if frappe.db.exists(DOCTYPE, {"logical_id": logical_id}):
		return
	doc = frappe.new_doc(DOCTYPE)
	doc.logical_id = logical_id
	doc.expected_effect = expected_effect
	doc.status = "Pending"
	doc.minted_at = now_datetime()
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
