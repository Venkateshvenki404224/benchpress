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

# sweep_overdue_reconciliation() severity tiers, keyed on `reconciliation_lapse_count`
# AFTER this escalation increments it (so the first lapse is lapse_count==1, not 0).
# Named as a real, unbuilt gap by spiritofthefleet (post d1670e43, reply to own comment
# f3751d86): "the sweep currently treats every lapse identically... so it genuinely
# cannot yet tell a one-time slip from an ignored pattern." Hive TASK-10899.
RECONCILE_SEVERITY_WARN_AT = 2  # second lapse: still routine, but worth a visible flag
RECONCILE_SEVERITY_CRITICAL_AT = 4  # fourth+ lapse: ignored pattern, not a one-time slip


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
				f"{doc.expected_effect}. Baseline policy_hash recorded at mint: "
				f"{'yes' if doc.policy_hash else 'no'}. Confirm by deadline whether the "
				"effect happened; do not auto-requeue or auto-remediate on a guess. "
				"(This flags only whether a comparison baseline exists, not the eventual "
				"requeue/remediate/unknown verdict — that depends on requeue_or_remediate's "
				"current_policy_hash, which is not known at this point in time.)"
			),
			"date": add_to_date(now_datetime(), hours=RECONCILE_SLA_HOURS),
		}
	)


def _reconciliation_severity(lapse_count: int) -> str:
	"""Map a post-increment lapse count to a severity label.

	Pure function (no frappe calls) so it's trivially unit-testable and so the
	threshold logic can be reused by a future measurement/reporting pass without
	re-deriving it from the sweep's own side effects.
	"""
	if lapse_count >= RECONCILE_SEVERITY_CRITICAL_AT:
		return "critical"
	if lapse_count >= RECONCILE_SEVERITY_WARN_AT:
		return "warn"
	return "routine"


def sweep_overdue_reconciliation() -> dict:
	"""Unknown-side mirror of `sweep_overdue_pending` — closes the gap named on Moltbook

	(spiritofthefleet, reply to own comment `f3751d86` on post
	`d1670e43-bb36-40f6-8c3b-a127be4de77f`): `_open_reconciliation_obligation` writes a real
	owner + `RECONCILE_SLA_HOURS` deadline onto a `ToDo` the moment a receipt flips
	Pending -> Unknown, but nothing in the codebase ever read that deadline back. A lapsed
	`ToDo.date` with no sweep behind it is the exact same silent-collapse failure a deadline
	is supposed to prevent — a human has to notice an unprompted timestamp, which nobody is
	guaranteed to do.

	Scans every `Job Receipt` still `Unknown` whose open `ToDo` deadline (`date`) has
	already passed, and — deliberately, per umiXBT's original "never auto-requeue or
	auto-remediate on a guess" instruction baked into the ToDo description itself — does
	NOT auto-resolve the receipt. It only re-escalates: bumps a fresh `ToDo` with a new
	deadline and a note that the prior one lapsed unresolved, so an ignored obligation
	compounds into a louder one instead of silently expiring. Returns a count, same
	convention as `sweep_overdue_pending`.

	Severity tiering (Hive TASK-10899, spiritofthefleet's second named gap: "the sweep
	currently treats every lapse identically... so it genuinely cannot yet tell a
	one-time slip from an ignored pattern"): each re-escalation increments
	`reconciliation_lapse_count` on the receipt itself (durable, survives restarts,
	unlike a counter kept only in this function's call stack) and the fresh ToDo's
	description is tagged with the resulting severity (`routine`/`warn`/`critical`
	per `_reconciliation_severity`), so a human triaging the assignment list can tell
	a first-time slip from a row that keeps coming back without opening each ToDo.
	This still does not resolve spiritofthefleet's OTHER named gap (no measurement of
	false-positive rate vs. genuine signal) — see `measure_reconciliation_false_positive_rate`.
	"""
	now = now_datetime()
	overdue_unknown = frappe.get_all(
		DOCTYPE,
		filters={"status": "Unknown"},
		fields=["name", "logical_id", "expected_effect", "reconciliation_lapse_count"],
	)
	escalated = []
	for row in overdue_unknown:
		open_todos = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": DOCTYPE,
				"reference_name": row["name"],
				"status": "Open",
				"date": ("<", now),
			},
			fields=["name", "allocated_to", "date"],
		)
		if not open_todos:
			continue  # either no obligation was ever opened, or it isn't overdue yet
		lapse_count = (row.get("reconciliation_lapse_count") or 0) + 1
		severity = _reconciliation_severity(lapse_count)
		frappe.db.set_value(DOCTYPE, row["name"], "reconciliation_lapse_count", lapse_count)
		for todo in open_todos:
			frappe.db.set_value("ToDo", todo["name"], "status", "Cancelled")
			assign_to_add(
				{
					"doctype": DOCTYPE,
					"name": row["name"],
					"assign_to": [todo["allocated_to"]] if todo["allocated_to"] else ["Administrator"],
					"description": (
						f"[{severity}] Job Receipt {row['name']} ({row['logical_id']}) has been Unknown "
						f"past its reconciliation deadline ({todo['date']}) with no resolution. "
						f"This is lapse #{lapse_count} on this receipt. "
						f"Re-escalating: {row['expected_effect']}. Still do not auto-requeue or "
						"auto-remediate on a guess — this exists to make the lapse visible, not "
						"to decide the disposition."
					),
					"date": add_to_date(now, hours=RECONCILE_SLA_HOURS),
				}
			)
		escalated.append(row["logical_id"])
	return {"checked": len(overdue_unknown), "re_escalated": escalated}


def measure_reconciliation_false_positive_rate(since: str | None = None) -> dict:
	"""Report whether the reconciliation sweep is mostly noise or mostly signal.

	Names, not silently assumes, the measurement gap spiritofthefleet flagged
	alongside severity tiering (Hive TASK-10899): "there is no measurement anywhere
	of how many overdue-Unknown rows the sweep would have caught historically vs.
	how many were already resolved by a human who just never closed the ToDo."

	Walks every `Job Receipt` that has ever lapsed at least once
	(`reconciliation_lapse_count > 0`) and buckets it:
	  - "resolved_without_escalation": status is Completed/Failed despite having
	    lapsed — a human acted on the underlying job even though the specific ToDo
	    chain was never formally closed. This is the "mostly noise" case: the sweep
	    fired, but the real work was already done through a different channel.
	  - "still_unresolved": status is still Unknown — the sweep is the only thing
	    keeping the obligation visible; this is the "mostly signal" case.
	Returns raw counts and a ratio, not a verdict — the caller (a human reviewing
	the sweep's real-world value) decides what ratio is acceptable; this function's
	job is to make that ratio visible instead of a historically unmeasured prior.

	`since` is accepted for a future creation-date filter and currently unused —
	named explicitly rather than silently ignored, so a caller doesn't assume
	filtering already works.
	"""
	lapsed = frappe.get_all(
		DOCTYPE,
		filters={"reconciliation_lapse_count": (">", 0)},
		fields=["name", "logical_id", "status", "reconciliation_lapse_count"],
	)
	resolved_without_escalation = [r for r in lapsed if r["status"] in ("Completed", "Failed")]
	still_unresolved = [r for r in lapsed if r["status"] == "Unknown"]
	total = len(lapsed)
	return {
		"total_ever_lapsed": total,
		"resolved_without_escalation": len(resolved_without_escalation),
		"still_unresolved": len(still_unresolved),
		"resolved_without_escalation_rate": (len(resolved_without_escalation) / total if total else None),
	}


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


REASON_CODES = ("worker_crash", "artifact_mismatch", "policy_stale", "timeout")


def mark_failed(logical_id: str, reason: str, reason_code: str | None = None) -> None:
	"""Called only when a worker crash or dead-worker record is actually observed.

	`reason` is the free-form human narrative and still goes to `frappe.log_error` only —
	it is not queryable. `reason_code` (closed vocabulary: REASON_CODES) is the machine-
	readable classification and is written in the SAME `doc.save()` call that sets
	status="Failed", so a later programmatic reader never has to reconcile "why" from a
	second source (application logs) after the fact. Proposed/discussed on Moltbook
	(Lucifer_V, post 1d909dd0, comment 2df8a36f) — logged in
	~/kb/concepts/moltbook-engineering-learning-loop.md, Hive TASK-11193.

	`reason_code` is optional on this call for backward compatibility with existing
	callers that haven't been updated yet; passing an unrecognized value raises.
	"""
	if reason_code is not None and reason_code not in REASON_CODES:
		raise ValueError(f"reason_code must be one of {REASON_CODES!r}, got {reason_code!r}")
	name = frappe.db.get_value(DOCTYPE, {"logical_id": logical_id}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"No Job Receipt minted for logical_id={logical_id!r}")
	doc = frappe.get_doc(DOCTYPE, name)
	doc.status = "Failed"
	if reason_code is not None:
		doc.reason_code = reason_code
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
