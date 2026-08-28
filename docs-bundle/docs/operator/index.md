---
title: Operator track
description: Run BenchPress on your own box — install, the VPN plane, settings,
  the shared database, images, upgrades, safety and diagnostics.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# Operator track

Everything about the machine BenchPress runs on, rather than the benches it
hands out.

**Who this is for.** Whoever owns the host: installs the app, keeps the shared
MariaDB alive, decides how large a bench may be, and gets called when a deploy
fails for everybody at once.

**Before you start.** The [user track](/docs/user/quick-tour) describes the same
product from the other side. Read it first if you have never deployed a bench —
several pages here only make sense once you have watched one run.

## The path through this track

Read these in order on a new host. Each one assumes the last.

|#|Page|What it settles|
|--|--|--|
|1|[Prerequisites](/docs/operator/prerequisites)|whether this machine can run BenchPress at all|
|2|[Install](/docs/operator/install)|the app, the shared infrastructure, the first screen|
|3|[WireGuard and the VPN plane](/docs/operator/wireguard-setup)|how benches and laptops reach each other|
|4|[Settings reference](/docs/operator/settings-reference)|every field, every default, and where each one is edited|
|5|[The shared database server](/docs/operator/database-server)|the one MariaDB every bench site lives in|
|6|[Backup and restore](/docs/operator/backup-and-restore)|what is dumped, when, and how to put it back|

## Then, as you need them

|Page|Read it when|
|--|--|
|[Golden images](/docs/operator/golden-images)|a deploy feels slow, or a lab takes the cold path|
|[The image cache](/docs/operator/image-cache)|disk is filling, or a template has no image|
|[Users and roles](/docs/operator/users-and-roles)|somebody needs access, or has too much|
|[Upgrading](/docs/operator/upgrading)|you are moving to a newer BenchPress release|
|[Production safety](/docs/operator/production-safety)|before you point anything you care about at this host|
|[Diagnostics](/docs/operator/diagnostics)|something is wrong and you do not yet know what|

## Optional, off by default

Two pages describe running BenchPress **for a team**: metering time, capping
concurrency, and letting people sign themselves up. None of it runs on a
self-hosted install, because `enable_credits` is `0` out of the box.

|Page|What it turns on|
|--|--|
|[Credits and billing](/docs/operator/credits-and-billing)|leases, a balance per user, and an optional payment gateway|
|[Admission and limits](/docs/operator/admission-and-limits)|concurrency caps, size ceilings, device and build quotas|
|[Self-serve signup](/docs/operator/hosted-signup)|a public signup page instead of a waitlist|

Skip all three if you are the only person on the box. BenchPress is a
dev-environment tool, not a hosting platform, and none of this is needed to
deploy a bench.

## What an operator actually owns

BenchPress drives Docker on one host. It does not run a control plane
elsewhere, and there is no second machine to keep in step.

* **One shared MariaDB.** Every bench site is a database inside
  `benchpress-mariadb`. See [The shared database server](/docs/operator/database-server).
* **One image per lab**, tagged `benchpress/<lab_id>:lab`, 5.5 GB to 19.7 GB
  each. See [The image cache](/docs/operator/image-cache).
* **One WireGuard interface**, owned by the `vpn_management` app. See
  [WireGuard and the VPN plane](/docs/operator/wireguard-setup).
* **Two settings documents**, `BenchPress Settings` and `Credit Settings`. See
  [Settings reference](/docs/operator/settings-reference).

## Related

* [Quick tour](/docs/user/quick-tour) — the screens, from a user's side.
* [Troubleshooting](/docs/user/troubleshooting) — the symptom index a user reads before calling you.
