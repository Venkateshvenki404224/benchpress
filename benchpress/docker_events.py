# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The Docker event stream, consumed rather than polled: a bench that dies is written down.

It observes and never acts — no stop, no restart, no route write; `deploy_manager` owns those.
"""

import queue
import threading
import time
from datetime import UTC, datetime

import frappe
from frappe import _
from frappe.utils import cint, convert_utc_to_system_timezone, now_datetime

from benchpress import docker_manager, notifications

MANAGED_LABEL = "benchpress.managed"
BENCH_NAME_LABEL = "benchpress.bench_name"

# Server-side, always. Without them the stream carries three `exec_*` events per healthcheck per
# bench, which the fleet multiplies.
EVENT_FILTERS = {
	"label": f"{MANAGED_LABEL}=true",
	"event": ["die", "oom"],
}

# Action prefix -> (event_type, severity). An action carries its state after a colon
# (`health_status: unhealthy`), so it is matched by prefix and never by equality.
INCIDENTS = {"oom": ("oom_killed", "error"), "die": ("bench_died", "error")}

SUBJECTS = {
	"bench_died": "Bench {0} stopped unexpectedly.",
	"oom_killed": "Bench {0} ran out of memory and was killed.",
}

# `stats_collector._update_bench_health` writes one of these before `_stop_if_dead` stops a bench,
# and nothing writes them to a bench that was stopped on request.
POLL_FOUND_IT_DEAD = ("Unhealthy", "Unknown")

DEFAULT_SETTLE_SECONDS = 15
TICK_SECONDS = 1
ERROR_BACKOFF = 30

HEARTBEAT_KEY = "benchpress:docker_events"
HEARTBEAT_EXPIRY = 120


def run() -> None:
	"""Service entry point. Never returns; the container's restart policy is the recovery."""
	while True:
		try:
			consume()
		except Exception:
			frappe.log_error(title="Docker events listener")
			time.sleep(ERROR_BACKOFF)


def consume() -> None:
	"""Stream events into a queue on a reader thread; settle and record them on this one.

	Returns when the reader dies, which is a daemon hiccup or a closed socket.
	"""
	inbox: queue.Queue = queue.Queue()
	pending: dict[str, dict] = {}
	stats = {"events_seen": 0, "orphans": 0, "connected_since": int(time.time())}

	stream = docker_manager.get_client().events(decode=True, filters=EVENT_FILTERS)
	try:
		reader = threading.Thread(target=_read_into, args=(stream, inbox), daemon=True)
		reader.start()
		while True:
			_drain(inbox, pending, stats)
			_start_fresh()
			_flush(pending, stats)
			heartbeat(pending, stats)
			time.sleep(TICK_SECONDS)
			# Checked last, so a reader that dies mid-tick still has its events drained.
			if not reader.is_alive():
				return
	finally:
		# Unblocks the reader. Without it a failed tick leaks a thread filling an orphaned queue.
		stream.close()


def _read_into(stream, inbox: queue.Queue) -> None:
	# frappe.local is thread-local: a write from here has no site, no connection and no user.
	for event in stream:
		inbox.put(event)


def _drain(inbox: queue.Queue, pending: dict, stats: dict) -> None:
	"""Park every queued event as one incident per bench, due after the settle window."""
	while True:
		try:
			event = inbox.get_nowait()
		except queue.Empty:
			return
		stats["events_seen"] += 1
		actor = event.get("Actor") or {}
		attributes = actor.get("Attributes") or {}
		bench = attributes.get(BENCH_NAME_LABEL)
		action = (event.get("Action") or "").split(":")[0].strip()
		if not bench or action not in INCIDENTS:
			continue

		# One incident per bench collapses the `oom`/`die` pair — 122 ms apart — into the one
		# incident it is, and `oom` wins the kind: exit 137 alone is not evidence of an OOM.
		incident = pending.get(bench)
		if incident is None:
			incident = pending[bench] = {"due": time.time() + settle_seconds()}
		if action == "oom" or "kind" not in incident:
			kind, severity = INCIDENTS[action]
			incident.update(kind=kind, severity=severity, action=event.get("Action"), at=event.get("time"))
		if attributes.get("exitCode"):
			incident["exit_code"] = cint(attributes["exitCode"])
		incident.setdefault("exit_code", 0)
		incident.setdefault(
			"detail", f"container {actor.get('ID', '')[:12]} image {attributes.get('image', '')}"
		)


def _flush(pending: dict, stats: dict) -> None:
	"""Record every incident whose settle window has closed, and forget the rest."""
	due = [name for name, incident in pending.items() if incident["due"] <= time.time()]
	for bench_name in due:
		incident = pending.pop(bench_name)
		row = frappe.db.get_value("Bench Instance", bench_name, ["status", "container_health"], as_dict=True)
		if not row:
			stats["orphans"] += 1
			continue
		if not _unasked_for(row):
			continue
		record(bench_name, incident)
	frappe.db.commit()


def _unasked_for(row) -> bool:
	"""Whether a settled death is one the platform did not ask for."""
	# Read only after the settle window: `stop_bench` stops the container and commits `Stopped`
	# afterwards, so at event time an ordinary stop still reads `Running`.
	if row.status == "Running":
		return True
	# The stats poll is the other writer of `Stopped`, and it writes it for exactly the benches
	# that died — recording the health it found on the way. A stop the platform asked for keeps
	# the health the bench had while it was serving, which is why the field discriminates.
	return row.status == "Stopped" and row.container_health in POLL_FOUND_IT_DEAD


def record(bench_name: str, incident: dict) -> None:
	"""Write the incident down, then tell the bench's owner. The row survives a failed notice."""
	frappe.get_doc(
		{
			"doctype": "Bench Event",
			"bench": bench_name,
			"event_type": incident["kind"],
			"severity": incident["severity"],
			"occurred_at": _stamp(incident.get("at")),
			"docker_action": incident.get("action"),
			"exit_code": incident.get("exit_code") or 0,
			"detail": incident.get("detail"),
		}
	).insert(ignore_permissions=True)

	owner = frappe.db.get_value("Bench Instance", bench_name, "owner")
	if owner:
		notifications.notify_owner(
			owner,
			_(SUBJECTS[incident["kind"]]).format(bench_name),
			"Bench Instance",
			bench_name,
		)


def _stamp(at):
	"""The daemon's event time in the site's timezone, or now when the event carried none."""
	if not at:
		return now_datetime()
	utc = datetime.fromtimestamp(cint(at), tz=UTC)
	return convert_utc_to_system_timezone(utc).replace(tzinfo=None)


def _start_fresh() -> None:
	"""Drop what a request would have dropped between one request and the next."""
	# `frappe.local` never resets in a process this long-lived: without the rollback the
	# connection keeps reading `status` from the snapshot it opened with.
	frappe.db.rollback()
	frappe.local.cache.clear()
	frappe.db.value_cache.clear()  # cleared, never replaced: it is a defaultdict


def settle_seconds() -> int:
	"""How long an incident waits before the database is asked about it."""
	# `.get`, not an attribute: a Single field has no row in `tabSingles` until the settings are
	# saved once, and an AttributeError here costs the connection and the event on it.
	settings = frappe.get_cached_doc("BenchPress Settings")
	return cint(settings.get("bench_event_settle_seconds")) or DEFAULT_SETTLE_SECONDS


def heartbeat(pending: dict, stats: dict) -> None:
	frappe.cache().set_value(
		HEARTBEAT_KEY,
		{
			"ts": int(time.time()),
			"connected_since": stats["connected_since"],
			"events_seen": stats["events_seen"],
			"orphans": stats["orphans"],
			"pending": len(pending),
		},
		expires_in_sec=HEARTBEAT_EXPIRY,
	)


def heartbeat_value() -> dict | None:
	"""What the listener last published plus its `age`, or None when nothing published."""
	published = frappe.cache().get_value(HEARTBEAT_KEY)
	if not published:
		return None
	return {**published, "age": int(time.time()) - cint(published.get("ts"))}
