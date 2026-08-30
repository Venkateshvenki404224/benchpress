---
title: The image cache
description: One image per lab, tagged benchpress/<lab_id>:lab — what it costs
  on disk, how the weekly prewarm and sweep work, and what is safe to prune.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# The image cache

Lab images are the largest thing on a BenchPress host. This page says how they
are named, what keeps them, what removes them, and what you must never prune.

**Who this is for.** Whoever watches the disk.

**Before you start.** Read the numbers below before you order a rebuild. A
lab image on this host is between **5.5 GB and 19.7 GB**, and building one
takes tens of minutes.

## How an image is named

A lab's image is tagged `benchpress/<lab_id>:lab`. The tag comes from the
lab's identity, not from a hash of its recipe.

That has one useful consequence. The first Lab created from a catalog template
takes the template's own key as its `lab_id`, so a template's pre-warmed image
and the first unmodified Lab built from it resolve to the same tag with no
extra bookkeeping.

A Lab that then diverges from its template — edited apps, a different Frappe
version — needs its own build. `Lab.validate()` notices, and resets the lab's
status to `Draft` when the build spec no longer matches what was last built.

## What is on this host

Twelve lab images, measured with `docker images`:

|Image|Size|
|--|--:|
|`benchpress/client-claude-16:lab`|19.7 GB|
|`benchpress/client-frappe-16:lab`|19.7 GB|
|`benchpress/helpdesk-sandbox:lab`|19.7 GB|
|`benchpress/client-google-16:lab`|12.5 GB|
|`benchpress/client-chatgpt-16:lab`|10.2 GB|
|`benchpress/crm:lab`|9.1 GB|
|`benchpress/crm-demo:lab`|9.1 GB|
|`benchpress/benchpress-16:lab`|7.86 GB|
|`benchpress/password-manager:lab`|6.99 GB|
|`benchpress/erpnext:lab`|6.14 GB|
|`benchpress/erpnext-training:lab`|6.14 GB|
|`benchpress/vpn-management-16:lab`|5.5 GB|

Those figures **overlap heavily**. Docker reports each image's full size, and
images built from the same base share layers. The whole image set on this host
occupies 54.74 GB, of which 19.12 GB is reclaimable.

## Steps

1. **Check what a build would cost before you order one.**

   ```bash
   df -h /
   docker system df
   ```

   A deploy costs roughly 0.2 GB to 1 GB. A build costs the size of a new
   image. Do not start a build with a few gigabytes free.

2. **Pre-warm the catalog** so the first person to use a template does not pay
   for the build.

   ```bash
   bench --site <site> execute benchpress.image_cache.enqueue_prewarm_catalog
   ```

   It queues **one job per template** that has no cached image, so a single
   failing template cannot cancel the rest. It runs on `queue-long`, the only
   worker with a Docker socket. The golden runs in the same job, so a fresh
   host's catalog comes out golden rather than needing a second pass.

3. **Sweep images nothing points at.**

   ```bash
   bench --site <site> execute benchpress.image_cache.enqueue_sweep
   ```

   Both jobs also run weekly on their own.

4. **Watch a build.** Open **Build history** at `/frontend/build-logs`,
   reached from **Labs**. The screen is admin-only, and says so under its own
   heading.

   ![The Build history page in BenchPress, listing image builds across every lab in six columns — Lab, Image tag, Result, Last step, Duration and Started. The top row is Password Manager building benchpress/password-manager, Success, 26m 5s, 6 hours ago. One Frappe CRM row reads Failed after 44s, and several rows carry the image tag golden rather than a lab tag.](../images/operator/image-cache/01-build-logs.png)

   Six columns: the lab, the image tag, the result, the last step reached, the
   duration and when it started. The slowest build on this host took **26
   minutes 5 seconds**, and one CRM row **failed after 44 seconds** at
   `Build started`. Read the build history rather than the deploy log when a
   deploy fails for a lab that has never been built.

   **A row tagged `golden` is not an image build.** It is the pass that bakes
   the finished site's dump into an image that already exists. Those runs take
   5 to 11 minutes here, against 4 to 26 for a full build. See
   [Golden images](/docs/operator/golden-images).

## Verify

```bash
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | grep '^benchpress/'
```

Every tag ends in `:lab`. That suffix is what identifies an image BenchPress
built — the `benchpress/` prefix alone would also catch a stray hand-tagged
image.

## What the sweep keeps

The sweep removes cached images nothing needs. Four things count as needing
one:

|Kept because|Read from|
|--|--|
|A Lab points at it|`Lab.image_tag`|
|A bench container runs it|`Bench Instance.container_image`|
|It is a catalog template's image|the template list. A template's image is kept even while no Lab points at it|
|A build in flight will produce it|Labs in `Building`, whose tag does not exist yet|

That fourth case is the one worth understanding. A `Building` lab has no
`image_tag` yet, so its fresh image would look like an orphan and a sweep
could delete it out from under the deploy waiting for it. Hashing exactly
those labs' specs protects exactly those tags, so one lab stuck in `Building`
cannot disable the whole sweep.

Without the sweep the cache is an unbounded disk leak.

## What never to prune

**Never run `docker image prune -a` on a BenchPress host.** Untagged but still
useful lab images are 5.5 GB to 19.7 GB each, and rebuilding one costs an hour
and most of the free disk.

These are safe:

|Command|Reclaims|Safe because|
|--|--|--|
|`docker volume prune -f`|orphaned bench volumes|volumes for benches that no longer exist. Reclaimed 4.66 GB on this host once|
|`docker image prune -f`|dangling images only|it leaves anything tagged. On this host it reclaimed 345 kB, because the dangling images share every layer with a tagged one|
|`benchpress.image_cache.enqueue_sweep`|unreferenced lab images|it checks all four references above first|

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A template's first deploy takes tens of minutes|No cached image, so the deploy built one|Pre-warm the catalog before people use it|
|A lab went back to `Draft` on its own|Its apps or Frappe version changed, so the built image no longer matches|Rebuild the lab|
|The disk filled during a build|The image did not fit|Free space first. Never `docker image prune -a`|
|The sweep removed nothing|Everything is still referenced|Expected. Delete the Labs you no longer want, then sweep|
|Pre-warm queued nothing|Every template already has an image|Expected|
|A build never starts|`queue-long` is stopped, and it is the only worker with a Docker socket|Start it, then re-run the job|

## Reference

|Item|Value|
|--|--|
|Tag pattern|`benchpress/<lab_id>:lab`|
|Repository glob|`benchpress/*`|
|Build timeout|10,800 s (3 hours)|
|Sweep timeout|600 s|
|Pre-warm schedule|weekly, `benchpress.image_cache.enqueue_prewarm_catalog`|
|Sweep schedule|weekly, `benchpress.image_cache.enqueue_sweep`|
|Worker|`queue-long` — the only one with a Docker socket|
|Pre-warm job id|`benchpress_prewarm_catalog`|
|Sweep job id|`benchpress_sweep_cached_images`|

## Related

* [Golden images](/docs/operator/golden-images) — what the build bakes into each of these images.
* [Prerequisites](/docs/operator/prerequisites) — sizing the disk before any of this.
* [Create a lab](/docs/user/create-a-lab) — the screen that orders a build.
