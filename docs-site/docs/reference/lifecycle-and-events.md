---
title: Lifecycle and events
description: The bench states and their transitions, the Docker event listener,
  Bench Event incidents, the stats collector, and the eleven scheduled jobs that
  correct the database.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Lifecycle and events

What changes a bench without anybody clicking anything.

**Who this is for.** Somebody wondering why a row changed, or adding a job that
changes one.

**Before you start.** BenchPress converges. A click is a request, not a
guarantee, and several passes run behind it to make the database agree with
Docker. Read [Deploy pipeline](/docs/reference/deploy-pipeline) for the click
path first.

## The five bench states

`Bench Instance.status` holds one of five values.

|State|Means|Reached from|
|--|--|--|
|`Draft`|the row exists, nothing was ever deployed|created by `create_bench`|
|`Deploying`|a deploy job is running|`Draft`, `Stopped`, `Error`, `Running`|
|`Running`|the container is up and the site answers|step 11 of a deploy, or a start|
|`Stopped`|the container exists and is not running|a stop, a lease expiry, or a balance sweep|
|`Error`|the deploy failed|any failed step|

Two more fields carry state of their own.

|Field|Values|Set by|
|--|--|--|
|`container_health`|`Healthy`, `Unhealthy`, `Unknown`, or empty|the event listener and the stats collector|
|`lease_state`|`Active`, `Stopping`, `Failed`, or empty|the lease warden and the drain sweep|

`lease_state` is only written while credits are on. It is separate from `status`
because a bench can be `Running` and already claimed for a stop.

## The transitions

`benchpress/lifecycle.py` owns every transition, and each one carries side
effects that must not be skipped.

|Function|Moves a bench to|Also does|
|--|--|--|
|`running(bench)`|`Running`|records the start time|
|`stopped(name)`|`Stopped`|deactivates the bench's sites|
|`errored(bench, ...)`|`Error`|writes the failure into the Deploy Log|
|`torn_down(bench)`|the row is deleted|removes the container, the VPN peer, the site database and the route file, then releases the admission claim|

Call these rather than setting `status` directly. A bench stopped by a direct
write leaves its sites active, and a bench deleted by a direct write leaks a
container, a tunnel address and a route.

`torn_down` records each removal that failed rather than aborting. A teardown
that gets halfway is worse than one that reports which half it finished.

## Incidents

`benchpress/docker_events.py` consumes the Docker event stream instead of
polling it. It observes and never acts. No stop, no restart, no route write.
`deploy_manager` owns those.

The stream is filtered server side, on the BenchPress label and on three
actions. Without the filter it carries three `exec_*` events for each health
check on each bench, multiplied by the fleet.

|Docker action|Becomes|Severity|
|--|--|--|
|`die`|`bench_died`|error|
|`oom`|`oom_killed`|error|
|`health_status: unhealthy`|`bench_unhealthy`|error|
|`health_status: healthy`|`bench_healthy`|info|

Each one is written as a [Bench Event](/docs/reference/data-model#bench-event).

**Two incidents inside the settle window become one.** The window is
`bench_event_settle_seconds`, 15 seconds by default. An OOM outranks the `die`
that follows it by milliseconds, and a death outranks a health verdict.

The precedence is fixed: `bench_healthy`, `bench_unhealthy`, `bench_died`,
`oom_killed`, lowest first. A site that stopped answering on its way out is one
incident, and the death is the half the owner has to be told about.

A health verdict also writes `container_health` on the bench, so that field is
fresh in seconds rather than after a poll interval.

The listener writes a heartbeat every second. After 60 ticks with no beat the
heartbeat is no longer believed, and the `*/5` reconcile pass is what keeps
convergence going. A listener that stays down degrades BenchPress to what it
was before the listener existed, not to silence.

## The stats collector

`benchpress/stats_collector.py` runs on the `*/1` cron and samples CPU, memory
and health for each running bench.

It polls at most 50 benches in one pass, set by `stats_poll_max_benches`. The
call costs about two seconds on the Docker socket for each container, so the cap
is what keeps the job inside its window.

The collector also stops a bench it finds dead, which is the one thing on this
page that acts rather than records.

## The scheduled jobs

Eleven jobs. [Diagnostics](/docs/operator/diagnostics#the-scheduled-jobs)
carries the full table with each schedule, read off a live host. This page says
what each one is for.

### Every minute

The scheduler tick on this host is four minutes, so `*/1` fires every four. The
entry stays `*/1` so shortening the tick needs no edit.

|Job|Does|
|--|--|
|`stats_collector.enqueue_stats_sweep`|samples CPU, memory and health|

### Every five minutes

Six jobs. Each is a net under a faster path, not the primary path.

|Job|Corrects|
|--|--|
|`reconcile.enqueue_run`|the database against Docker, in both directions|
|`docker_events.enqueue_reconcile`|whatever the event listener missed while it was down|
|`mariadb_manager.enqueue_health_check`|the shared database server's health|
|`credits.drain.sweep_expired_leases`|leases the warden did not claim in time|
|`credits.sweep.enforce_limits`|who has run out of balance|
|`credits.admission_repair.reconcile_admissions`|claim counts that drifted|

Three of these need `queue-long`. `reconcile.enqueue_run` and
`docker_events.enqueue_reconcile` need the Docker socket, and the route
convergence needs the Traefik mount. `queue-short` has neither.

`drain.sweep_expired_leases` makes no Docker call, so it is safe on either
worker. It is the net under the lease warden, not the primary path. The
scheduler tick is four minutes here, so no cron entry can promise better than
that. The warden claims within seconds, and both use the same conditional
claim, so running together cannot stop a bench twice.

`enforce_limits` is deliberately not on the `*/1` cron. That job spends about
two seconds for each container on the Docker socket, and a decision queued
behind Docker input and output arrives late.

### Daily and weekly

|Job|Does|
|--|--|
|`mariadb_manager.enqueue_backup`|dumps every bench site, at 02:00|
|`credits.reaper.reap_stopped_instances`|removes containers stopped for too long|
|`image_cache.enqueue_prewarm_catalog`|builds an image for a catalog template that has none|
|`image_cache.enqueue_sweep`|removes images no lab points at|

## What the reconcile pass does

`benchpress/reconcile.py` is the only pass that looks in both directions. Every
other sweep converges outwards from a row, so it cannot see a thing that has no
row.

|Check|Finds|
|--|--|
|Route convergence|a running bench with no route file, or a route file with no bench|
|Orphan containers|a BenchPress container no row points at|
|Reap verification|a container that was told to go and did not|
|Orphan databases|a site database no bench claims|
|Deploy record trimming|a bench whose Deploy Logs passed the cap|

**A deploy looks exactly like an orphan while it runs.** `_deploy_bench` creates
the container before it writes `container_id`, so every deploy passes through
that state. The 15 minute grace window from `orphan_grace_minutes` is what keeps
the pass from reaping a live deploy.

Container ids are compared on their first twelve characters. Docker reports the
full id and a row may hold either form, so a live bench is never called an
orphan over a difference in notation.

Deploy Logs are capped at 50 for each bench, on top of Frappe's own seven day
sweep. The cap is the second bound, for the bench redeployed in a loop that
reaches thousands of rows inside a week.

## Verify

Read a bench's recent incidents:

```bash
bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'Bench Event','fields':['bench','event_type','severity','occurred_at'],'limit_page_length':10}"
```

Confirm the jobs are not stopped:

```bash
bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'Scheduled Job Type','fields':['method','stopped'],'limit_page_length':0}"
```

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A bench outlives its lease|The stop worker is down, so the claim is made and never runs|Check the worker containers, not the job table|
|No incident for a bench that died|The event listener is down|It restarts on its own. The `*/5` pass catches up|
|`container_health` is stale|The listener is down and the stats collector is capped at 50|Raise `stats_poll_max_benches`, or fix the listener|
|A container exists with no row|An orphan, if it is older than the grace window|The reconcile pass removes it|
|A live deploy was reaped|The grace window is shorter than the deploy|Raise `orphan_grace_minutes`|
|Nothing converges at all|The scheduler is not running|Every job here is a scheduled job. Start the scheduler|
|A stopped bench keeps its sites active|Somebody wrote `status` directly|Call `lifecycle.stopped` instead|
|Two stops for one expiry|Not possible. Both paths use the same conditional claim|Look for two benches|

## Reference

|Fact|Value|
|--|--|
|Bench states|`Draft`, `Deploying`, `Running`, `Stopped`, `Error`|
|Incident types|`bench_died`, `oom_killed`, `bench_unhealthy`, `bench_healthy`|
|Settle window|`bench_event_settle_seconds`, 15 seconds|
|Listener tick|1 second|
|Heartbeat stale after|60 ticks|
|Listener error backoff|30 seconds|
|Stats poll cap|`stats_poll_max_benches`, 50|
|Orphan grace|`orphan_grace_minutes`, 15 minutes|
|Deploy log cap|`deploy_log_cap`, 50 for each bench|
|Log retention|7 days|

## Related

* [Deploy pipeline](/docs/reference/deploy-pipeline) — the click path these jobs correct.
* [Data model](/docs/reference/data-model#bench-event) — the row an incident becomes.
* [Diagnostics](/docs/operator/diagnostics) — the job table, and what diagnostics does not cover.
* [Settings reference](/docs/operator/settings-reference) — every number named above.
