---
title: Glossary
description: What each BenchPress term means here — lab, bench, site, lease,
  admission, golden image, peer — including the words that mean something else
  elsewhere.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Glossary

One name for one thing. This page is the list of names.

**Who this is for.** Anybody reading the other pages, or a diff, and unsure
whether two words mean the same thing.

**Before you start.** Four words in this product also mean something else in
Frappe or in Docker. They are marked. A wrong reading of one of them is the
most common way to misread this codebase.

## The core nouns

|Term|Means here|
|--|--|
|**Lab**|a description of an environment: a Frappe version and a list of apps. An operator writes one, a user deploys it many times. A `Lab` DocType|
|**Lab template**|a ready-made lab in the catalog. Only an admin turns one into a lab|
|**Bench instance**|one deployed container made from a lab. A `Bench Instance` DocType. Often shortened to **bench**|
|**Bench site**|the Frappe site running inside a bench instance. A `Bench Site` DocType|
|**Control plane**|the BenchPress app itself, and the stack it runs in. It never runs a bench's code|
|**Shared infrastructure**|the one MariaDB, one Traefik and one WireGuard server that every bench uses|
|**Instance size**|a resource tier: memory, CPU, disk rate, network rate and price|
|**Deploy**|the eleven step job that turns a lab into a running bench|
|**Redeploy**|the same job on a bench that already exists. It replaces the container and the site database|
|**Teardown**|removing the container, the peer, the site database, the route file and the row|

## The words that mean something else elsewhere

These four are the traps.

|Term|Here|Elsewhere|
|--|--|--|
|**Bench**|a deployed container BenchPress created|in Frappe, a directory holding apps and sites. The control plane runs inside one of those|
|**Site**|the Frappe site inside a bench|the control plane also has a site, always named `frontend`|
|**Image**|a lab's Docker image, one for each lab|the control plane image is a different thing, built by `entry.py`|
|**Device**|a laptop or phone on the VPN|not a DocType. It is a `VPN Peer` in the `vpn_management` app|

The site invariant is worth stating twice. The control plane's site is
`frontend`, everywhere and always. A bench's site is named from the instance id
and the base domain. The two are never the same thing.

## Credits and leases

Every term here applies only while `enable_credits` is `1`. It ships as `0`.

|Term|Means|
|--|--|
|**Credit**|the unit of account. Not money. A credit pack converts money into credits|
|**Credit account**|one balance, named by the holder's email address|
|**Ledger entry**|one movement of a balance, with what caused it on the row|
|**Lease**|the window a deploy buys. It has a deadline, and the bench stops at it|
|**Lease plan**|a duration for sale, in minutes and credits|
|**Renew**|buying one more window. It extends from the deadline you had, not from now|
|**Hold**|credits reserved against a running bench, not yet spent|
|**Admission**|the decision that lets an action start: can this caller pay, and are they under their caps|
|**Cap**|a ceiling on concurrency, size, devices or builds a day|
|**Drain**|the sweep that ends leases that have run out|
|**Warden**|the long-lived loop that claims a due lease within seconds of its deadline|
|**Reaper**|the daily job that removes containers stopped for too long. Stopped is free, but not forever|
|**Sweep**|the balance pass: whose running benches must stop, and who is warned first|

**Admission is not authorization.** Authorization asks whether the caller may do
this at all, and lives in `permissions.py`. Admission asks whether they can
afford it right now, and lives in `credits/guard.py`. An endpoint can pass one
and fail the other.

## Images and speed

|Term|Means|
|--|--|
|**Lab image**|the Docker image a lab deploys from, tagged by the lab's own identity|
|**Golden image**|a lab image that also carries a database dump of the finished site|
|**Golden dump**|that dump. Restoring it is the difference between a deploy in seconds and one in minutes|
|**Cold deploy**|a deploy that creates the site from scratch instead of restoring|
|**Prewarm**|building an image for a catalog template that has none yet|
|**Image cache**|the set of built lab images on the host. Large. 5 GB to 20 GB each|

## Networking

|Term|Means|
|--|--|
|**Bench bridge**|a Docker bridge network holding bench containers. Named `benchpress-N`|
|**Peer**|a WireGuard participant. Both a bench and a user device are peers|
|**Tunnel address**|the WireGuard address a bench answers on. The `wg_ip` field|
|**Public address**|the Traefik-served HTTPS address, under the base domain|
|**Base domain**|the zone every public bench address sits under. Empty means no public address|
|**Route file**|one YAML file in Traefik's flat directory, publishing one bench|
|**Anchor**|`wildcard-anchor.yml`, the one file that names a certificate resolver|
|**Instance id**|the 32 character hexadecimal name of a bench. Also the container name|

## Logs and events

|Term|Means|
|--|--|
|**Deploy Log**|the text of one deploy run, appended line by line|
|**Build Log**|the same, for one image build|
|**Step**|one of the eleven deploy boundaries, reported inside a `=== … ===` marker|
|**Bench Event**|an incident: a bench died, ran out of memory, or changed health|
|**Settle window**|15 seconds, inside which two incidents for one bench become one|
|**Reconcile**|the pass that compares Docker against the database, in both directions|
|**Orphan**|a BenchPress container no row points at, older than the grace window|

## Roles

Three roles, and everything in the product keys off them.

|Role|May|
|--|--|
|`BenchPress User`|deploy, use and stop their own benches, and manage their own devices|
|`BenchPress Admin`|everything a user may, plus every bench, labs, templates, settings and builds|
|`System Manager`|the Frappe role. Treated as an admin everywhere here|

An admin sees every row. Both admin roles short-circuit every scoping rule. See
[How a row is scoped](/docs/reference/data-model#how-a-row-is-scoped).

## Related

* [Data model](/docs/reference/data-model) — the DocType behind each noun.
* [Architecture](/docs/reference/architecture) — which module owns each concept.
* [Users and roles](/docs/operator/users-and-roles) — granting the three roles.
* [Credits and billing](/docs/operator/credits-and-billing) — the whole optional half.
