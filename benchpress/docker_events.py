# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The Docker event stream, consumed rather than polled: a bench that dies or goes quiet is written down.

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
	"event": ["die", "oom", "health_status"],
}

# Action, with its state kept, -> (event_type, severity).
INCIDENTS = {
	"die": ("bench_died", "error"),
	"oom": ("oom_killed", "error"),
	"health_status:unhealthy": ("bench_unhealthy", "error"),
	"health_status:healthy": ("bench_healthy", "info"),
}

# Which incident wins when two arrive for one bench inside the settle window. An OOM outranks the
# `die` 122 ms behind it, and a death outranks a health verdict: a site that stopped answering on
# its way out is one incident, and the death is the half the owner has to be told about.
PRECEDENCE = ("bench_healthy", "bench_unhealthy", "bench_died", "oom_killed")

# The `container_health` a verdict writes, which is how the field becomes fresh in seconds
# instead of after a poll interval.
HEALTH_VERDICTS = {"bench_unhealthy": "Unhealthy", "bench_healthy": "Healthy"}

# Derived, so an incident recorded by `reconcile` cannot disagree with the same one off the stream.
SEVERITY = dict(INCIDENTS.values())

SUBJECTS = {
	"bench_died": "Bench {0} stopped unexpectedly.",
	"oom_killed": "Bench {0} ran out of memory and was killed.",
	"bench_unhealthy": "Bench {0} has stopped answering on its site.",
	"bench_healthy": "Bench {0} is answering again.",
}

# `stats_collector._update_bench_health` writes one of these before `_stop_if_dead` stops a bench,
# and nothing writes them to a bench that was stopped on request.
POLL_FOUND_IT_DEAD = ("Unhealthy", "Unknown")

DEFAULT_SETTLE_SECONDS = 15
TICK_SECONDS = 1
ERROR_BACKOFF = 30

HEARTBEAT_KEY = "benchpress:docker_events"
# Ticks of grace before the heartbeat is no longer believed, and how long it outlives that so a
# stale beat can still name its own age. Both derived from the tick: a shorter tick must not
# quietly become a shorter patience.
HEARTBEAT_STALE_TICKS = 60
HEARTBEAT_STALE_SECONDS = TICK_SECONDS * HEARTBEAT_STALE_TICKS
HEARTBEAT_EXPIRY = HEARTBEAT_STALE_SECONDS * 2


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
		# After the reader, not before: anything that changes while the pass runs is then already
		# on the stream rather than in the gap between the two.
		reconcile()
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
		named = _incident_for(event.get("Action") or "")
		if not bench or not named:
			continue
		kind, severity = named

		# One incident per bench collapses the `oom`/`die` pair — 122 ms apart — into the one
		# incident it is, and `PRECEDENCE` decides which of them it is reported as: exit 137
		# alone is not evidence of an OOM.
		incident = pending.get(bench)
		if incident is None:
			incident = pending[bench] = {"due": time.time() + settle_seconds()}
		if _outranks(kind, incident.get("kind")):
			incident.update(kind=kind, severity=severity, action=event.get("Action"), at=event.get("time"))
		if attributes.get("exitCode"):
			incident["exit_code"] = cint(attributes["exitCode"])
		incident.setdefault("exit_code", 0)
		incident.setdefault(
			"detail", f"container {actor.get('ID', '')[:12]} image {attributes.get('image', '')}"
		)


def _incident_for(action: str) -> tuple[str, str] | None:
	"""The (event_type, severity) an action names, or None for an action not worth a row.

	Matched on the action's state when it carries one and on the action alone otherwise:
	`health_status: unhealthy` keeps its state after a colon and a space, so a lookup on
	`health_status` matches neither verdict.
	"""
	head, _colon, state = action.partition(":")
	head, state = head.strip(), state.strip()
	return INCIDENTS.get(f"{head}:{state}") or INCIDENTS.get(head)


def _outranks(kind: str, parked: str | None) -> bool:
	"""Whether this incident replaces the one already parked for the bench."""
	return parked is None or PRECEDENCE.index(kind) > PRECEDENCE.index(parked)


def _flush(pending: dict, stats: dict) -> None:
	"""Record every incident whose settle window has closed, and forget the rest."""
	due = [name for name, incident in pending.items() if incident["due"] <= time.time()]
	for bench_name in due:
		incident = pending.pop(bench_name)
		row = frappe.db.get_value("Bench Instance", bench_name, ["status", "container_health"], as_dict=True)
		if not row:
			stats["orphans"] += 1
			continue
		if incident["kind"] in HEALTH_VERDICTS:
			_settle_health(bench_name, row, incident)
		elif _unasked_for(row):
			record(bench_name, incident)
	frappe.db.commit()  # nosemgrep -- no request boundary here, and the next tick rolls back


def _settle_health(bench_name: str, row, incident: dict) -> None:
	"""Freshen the health field from Docker's verdict, and record the transition if it is news."""
	# A verdict about a bench the platform is no longer running is neither news nor a field worth
	# writing: `lifecycle` owns the field across a stop and a start.
	if row.status != "Running":
		return
	frappe.db.set_value(
		"Bench Instance",
		bench_name,
		{"container_health": HEALTH_VERDICTS[incident["kind"]], "last_health_check": now_datetime()},
		update_modified=False,
	)
	if not _is_news(incident["kind"], bench_name):
		return
	record(bench_name, incident)


def _is_news(kind: str, bench_name: str) -> bool:
	"""Whether an incident is worth a row: recovery counts only after a failure was recorded."""
	# The first verdict a deploy produces is `starting -> healthy`, and a row for every deploy is
	# noise rather than news.
	return kind != "bench_healthy" or _last_event(bench_name) == "bench_unhealthy"


def _last_event(bench_name: str) -> str | None:
	"""The event type most recently recorded for a bench, or None when it has none."""
	return frappe.db.get_value(
		"Bench Event", {"bench": bench_name}, "event_type", order_by="occurred_at desc"
	)


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


def enqueue_reconcile() -> None:
	"""Convergence cron: hand the pass to `queue-long`, the worker that has the Docker socket."""
	# The enqueuer, never `reconcile` itself — see the rule above `scheduler_events` in `hooks.py`.
	frappe.enqueue(
		"benchpress.docker_events.reconcile",
		queue="long",
		job_id="docker_events_reconcile",
		deduplicate=True,
	)


def reconcile() -> dict:
	"""Re-read health for every Running bench; the event buffer is too shallow to replay.

	Returns `{checked, changed, recorded}`: a pass that reported only "ran" is how drift goes
	unnoticed.
	"""
	# The daemon keeps 255 events — 74 seconds on this host, and less once every bench carries a
	# healthcheck — so `since=<disconnect>` is a head start and never a guarantee.
	_start_fresh()
	counts = {"checked": 0, "changed": 0, "recorded": 0}
	for bench in _benches_to_reconcile():
		counts["checked"] += 1
		health = docker_manager.get_container_health(bench.container_id)
		if health != bench.container_health:
			counts["changed"] += 1
			frappe.db.set_value(
				"Bench Instance",
				bench.name,
				{"container_health": health, "last_health_check": now_datetime()},
				update_modified=False,
			)
		kind = _drifted_to(bench.container_id, health)
		if _is_drift(kind, bench.name):
			record(bench.name, _drift_incident(kind, bench.container_health, health))
			counts["recorded"] += 1
	frappe.db.commit()  # nosemgrep -- a background pass has no request boundary to commit at
	return counts


def _benches_to_reconcile() -> list[dict]:
	"""The benches the platform believes are running, which is the only set worth an opinion."""
	# Unbounded, unlike the stats poll: an inspect is a millisecond against 1.7 s for a stats
	# sample. A bench stopped while the listener was blind is excluded by `status`, which is what
	# keeps an intentional stop from producing an event.
	return frappe.get_all(
		"Bench Instance",
		filters={"status": "Running", "container_id": ["is", "set"]},
		fields=["name", "container_id", "container_health"],
	)


def _is_drift(kind: str, bench_name: str) -> bool:
	"""Whether a reconciled state differs from the last thing said about the bench."""
	# Against the last event, never against `container_health`: `stats_collector` writes that
	# field too and records nothing, so a poll winning the race would silence the pass entirely.
	return _last_event(bench_name) != kind and _is_news(kind, bench_name)


def _drifted_to(container_id: str, health: str) -> str:
	"""The incident a health change amounts to, once the container is asked whether it is still up."""
	if health == "Healthy":
		return "bench_healthy"
	# `container_is_down` is the discriminator rather than the health label: `get_container_health`
	# answers Unhealthy both for a site that stopped replying and for a container that exited.
	return "bench_died" if docker_manager.container_is_down(container_id) else "bench_unhealthy"


def _drift_incident(kind: str, before: str, after: str) -> dict:
	"""An incident found by re-reading state rather than by an event, stamped at the pass."""
	return {
		"kind": kind,
		"severity": SEVERITY[kind],
		"detail": f"found by reconcile: health {before or 'unset'} -> {after}",
	}


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
