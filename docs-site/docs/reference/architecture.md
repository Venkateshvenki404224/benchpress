---
title: Architecture
description: The moving parts of BenchPress — the control plane, the bench
  containers, the shared infrastructure, and which Python module owns each
  concern.
lastModified: "2026-08-30T17:48:34+05:30"
lastAuthor: Venkatesh
---
# Architecture

What the system is made of, and which module you open when a question is about
one of the parts.

**Who this is for.** Somebody about to change the code, or about to guess which
file a behavior lives in.

**Before you start.** BenchPress is a Frappe app. It runs inside a bench of its
own, and it deploys other benches as Docker containers. Keep the two apart while
you read. This page calls the first one the **control plane** and the second one
a **bench**.

## The three layers

|Layer|What it is|Runs as|
|--|--|--|
|Control plane|the BenchPress app, its database, its workers and the SPA|the parent `benchpress_devops` Docker Compose stack|
|Shared infrastructure|one MariaDB, one Traefik, one WireGuard server|long-lived containers beside the control plane|
|Benches|one container for each deployed bench instance|created and destroyed on demand|

The control plane never runs a bench's code. It creates the container, writes
files into it, and records what happened. Every bench keeps its site database in
the shared MariaDB, not in a database of its own.

## The request path

A click in the browser reaches Docker through five hops.

1. The Vue 3 single-page app calls a whitelisted method over `/api/method/`.
2. The method checks permissions, then reads or writes DocTypes.
3. Work that takes more than a moment is put on a queue instead of run inline.
4. A worker picks the job up and calls `docker_manager`.
5. `docker_manager` talks to the Docker socket.

Only `backend` and `queue-long` carry the Docker socket and the Traefik route
mount. A job that needs either must run on `queue-long`. A deploy started on the
wrong worker fails on the route mount.

## Which module owns what

One concern for each module. The table is the whole `benchpress/` package.

|Module|Owns|
|--|--|
|`api.py`|the whitelisted surface the SPA calls|
|`lifecycle.py`|the bench state transitions, and the side effects each one must not forget|
|`deploy_pipeline.py`|the eleven deploy steps, and how a run reports them|
|`deploy_manager.py`|image builds, and the deploy work that is not a state change|
|`docker_manager.py`|every call to the Docker socket|
|`placement.py`|which bench bridge a new container joins|
|`addressing.py`|every address a bench answers on|
|`ingress.py`|every write to the Traefik route directory|
|`vpn_adapter.py`|the only seam into the `vpn_management` app|
|`mariadb_manager.py`|the shared database server, its health check and its backup|
|`site_names.py`|the site name as an allocation, claimed and released|
|`image_cache.py`|one image for each lab, tagged by the lab's own identity|
|`golden.py`|a lab's finished site, baked into the lab image as a dump|
|`reconcile.py`|the pass that compares Docker against the database, both ways|
|`docker_events.py`|the Docker event stream, and the incidents it records|
|`stats_collector.py`|CPU, memory and health, sampled for each running bench|
|`permissions.py`|the role helpers and the six query conditions|
|`overview.py`, `labs.py`, `lab_detail.py`, `run_history.py`|one screen each, assembled in a fixed number of queries|
|`waitlist.py`, `signup.py`|the two doors open to a guest|
|`diagnostics.py`|twelve read-only environment checks|
|`notifications.py`|one desk alert and one email to a document owner|
|`indexes.py`|composite indexes the DocType JSON cannot declare|
|`request_cache.py`|a value memoised for one request, never in a module global|
|`connection_test.py`|the tunnel test behind "A site will not open?"|
|`vpn_access.py`|the VPN roles a BenchPress Admin needs|
|`lab_templates.py`|the catalog of ready-made templates|
|`install.py`|what a fresh install seeds|

## The credits package

Everything commercial sits under `benchpress/credits/`. It is off by default.
`enable_credits` ships as `0`, and with it off no module below charges anybody.

|Module|Owns|
|--|--|
|`guard.py`|one decorator that refuses an action before work is queued|
|`admission.py`|the concurrency and credit decision, taken as a write that can fail|
|`admission_repair.py`|the repair pass, because a claim is denormalized twice|
|`lease.py`|what a deploy buys, when it runs out, and who may end it|
|`warden.py`|a long-lived loop that claims a due lease within seconds|
|`drain.py`|whether expiries land, and how late they were|
|`sweep.py`|whose running instances must stop, and who is warned first|
|`account.py`|one-off debits and credits, the accounting core|
|`metering.py`|the three lifecycle sites that bill|
|`payments.py`|a Razorpay order, settled into the ledger exactly once|
|`reaper.py`|stopped is free, but not forever|
|`config.py`|the single read path for every commercial number|
|`onboarding.py`|what happens between "signed up" and "can deploy"|
|`notify.py`|what the sweep and the reaper say, and where|
|`seed.py`|prices a fresh install can show|

## Where behavior hides

Three places hold behavior that the obvious file does not show. Check all three
before you conclude a save does nothing extra.

|Place|Holds|
|--|--|
|`hooks.py`|permission query conditions, document events, scheduled jobs, overrides|
|DocType controllers|`validate`, `autoname`, `before_insert`, and the doc-level methods|
|The `vpn_management` app|every peer, every tunnel address, and the device records|

Devices are not a BenchPress DocType. A device is a `VPN Peer` in
`vpn_management`. See [Data model](/docs/reference/data-model#devices-are-vpn-peers).

## The frontend

A Vue 3 single-page app in `frontend/`, built with frappe-ui, vue-router and
Tailwind. It is served from the same origin as the API, so a socket connection
needs no separate host.

Eleven routes exist. Four of them are admin-only, and one renders only while
credits are on.

|Route|Screen|Who sees it|
|--|--|--|
|`/`|Overview|any app user|
|`/labs`|Labs|any app user|
|`/bench-instances`|Instances|any app user|
|`/labs/:labId`|Lab detail|the owner, and any admin|
|`/devices`|Devices|any app user|
|`/deploy-logs`|Deploy history|any app user, scoped to their benches|
|`/labs/new`|New lab|admin only|
|`/labs/templates`|Templates|admin only|
|`/build-logs`|Build history|admin only|
|`/settings`|Settings|admin only|
|`/credits`|Credits|any app user, and only while credits are on|

A guard in `frontend/src/router.js` sends a non-admin who reaches an admin-only
route back to Labs. It does the same for `/credits` while `enable_credits` is
`0`. The guard is a convenience, not the control. The API refuses the call as
well, and that refusal is the one that counts.

## Reference

The counts a change should keep true.

|Surface|Count|
|--|--|
|DocTypes|20|
|Whitelisted functions|50|
|Deploy steps|11|
|Scheduled jobs|11|
|Permission query conditions|6|
|`has_permission` hooks|5|
|Realtime events|6|

## Related

* [Data model](/docs/reference/data-model) — the 20 DocTypes and their links.
* [Deploy pipeline](/docs/reference/deploy-pipeline) — what the eleven steps do.
* [Networking](/docs/reference/networking) — the address plan for all of the above.
* [Operator track](/docs/operator) — the same system, as tasks on a host.
