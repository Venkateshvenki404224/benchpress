# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Names the drift between the database and reality. Nothing here removes anything."""

from datetime import UTC, datetime, timedelta

import frappe
from frappe.utils import cint

# Matches `admission_repair.CLAIM_GRACE_MINUTES`, and for the same reason: `_deploy_bench` creates
# the container before it writes `container_id`, so every deploy passes through a state that looks
# exactly like an orphan.
DEFAULT_GRACE_MINUTES = 15

# Docker reports the full id and a row may hold either form; twelve characters is the form both
# share, so a live bench is never named an orphan over a difference in notation.
ID_KEY_LENGTH = 12


def configured_grace_minutes() -> int:
	"""The window a container is never an orphan in, or 15 when nothing has set one."""
	settings = frappe.get_cached_doc("BenchPress Settings")
	return cint(settings.get("orphan_grace_minutes")) or DEFAULT_GRACE_MINUTES


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


def _id_key(container_id) -> str:
	return (container_id or "")[:ID_KEY_LENGTH]


def _older_than(created, cutoff: datetime) -> bool:
	"""Whether a container is old enough to be judged. A container of unknown age never is."""
	return bool(created) and created < cutoff
