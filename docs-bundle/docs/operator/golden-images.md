---
title: Golden images
description: A lab's finished site is baked into its own image as a database
  dump, so a deploy restores it instead of creating tables — the measured
  numbers, the two settings, and why a golden gets refused.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# Golden images

Why a deploy takes 13 seconds instead of 43, what turns it off, and how to
check which labs have it.

**Who this is for.** Whoever is asked why a deploy is slow.

**Before you start.** Both settings ship **on**. There is nothing to enable on
a fresh install. Read this page when a deploy is slower than you expect, or
when [Diagnostics](/docs/operator/diagnostics) reports partial golden
coverage.

## What a golden is

Creating a Frappe site creates its tables through the ORM — 281 of them for a
CRM lab, 1,055 for a seven-app one. That happens on every deploy, for every
user, and it is **92% to 97% of the whole deploy**.

A golden image carries the finished site's database as a compressed dump
inside the image. `setup-site.sh` restores that dump instead of installing the
site.

The dump ships inside the image on purpose, so it can never drift from the
code that produced it. The layer carrying it is appended over the existing
tag rather than rebuilt into a new one, because lab images are 5.5 GB to
19.7 GB and a rebuild does not fit on a normal host.

## The measured numbers

Measured on a 2-vCPU host, comparing the same image with the golden used and
with it refused.

|Arm|Site step|Whole deploy|
|--|--:|--:|
|Golden restored|**9.1 s**|**13.3 s**|
|Cold (same image, golden off)|37.2 s|43.3 s|

Reproduce it yourself. The drill deploys through the shipped `create_bench`
endpoint and reads every duration back out of the run's own Deploy Log, so it
cannot report a number the product did not produce:

```bash
python3 scripts/golden_drill.py --lab crm --runs 3 --i-know-this-is <your base domain>
python3 scripts/golden_drill.py --lab crm --runs 3 --cold --i-know-this-is <your base domain>
```

`--cold` is the control and uses the same image. It turns `restore_from_golden`
off for the run and puts it back afterwards, so both arms deploy the same lab,
the same apps and the same container, differing only in whether the site is
restored or created.

Two behaviors of the drill worth knowing before you run it on a live host. It
goes to the host's own nginx rather than through the CDN, and it refuses to
run unless `--i-know-this-is` matches the site's own `base_domain`. Every
bench it makes belongs to `golden-drill@example.com`, and cleanup runs in a
`finally` block.

The underlying measurement, taken directly inside `benchpress-mariadb`: a
281-table database dumps in 0.67 s and restores in **6.6 s**, against 40.4 s
to create. A 1,055-table one dumps in 2.5 s and restores in **24.9 s**,
against 202 s to create.

## Steps

1. **Check which labs carry a golden.**

   ```bash
   bench --site <site> execute benchpress.diagnostics.run_diagnostics
   ```

   The `golden_images` row names every built lab whose image has no dump. On
   this host it reads **4 of 12 built labs carry a golden dump**, and names
   the eight that build their site from scratch on every deploy.

2. **Give a lab a golden.** Either rebuild the lab, or run **Build golden** on
   it. A rebuild is expensive — see [The image cache](/docs/operator/image-cache)
   before you start one.

3. **Confirm it took.** Deploy the lab and read the Deploy Log.

   ![The Deploy log tab of the Frappe CRM demo lab, showing a Latest deploy header reading Success in 21s over eleven ticked steps. Step seven, Creating the site, took 17s and reads that the site was restored from the image's golden dump. Step two reads Using built image benchpress/crm-demo:lab.](../images/operator/golden-images/01-deploy-log-golden.png)

   The site step says `Site <name> restored from the image's golden dump` when
   the golden ran. A cold run says `Site created successfully` instead, and
   the step before it names the reason.

   That run finished in **21 seconds**, of which the site step was **17**.
   Both are slower than the drill's 13.3 and 9.1, and neither contradicts it.
   The drill measures one deploy on an otherwise idle host. This one ran on a
   host with nine benches already up. Compare a golden run against a cold run
   on the same host, never against a number measured on a different one.

## Verify

The image's own labels are the truth, not the `Lab.golden_manifest` field. The
field is a claim about an image, and the image is what a deploy runs.

```bash
docker inspect benchpress/crm:lab \
  --format '{{index .Config.Labels "benchpress.golden"}} {{index .Config.Labels "benchpress.golden.mariadb"}}'
```

`1 10.6.28-MariaDB-ubu2204` means this image carries a dump taken from MariaDB
10.6.

## Why a golden gets refused

A refusal is always a **slow deploy, never a failed one**. The site is created
the old way and the Deploy Log names the reason.

|Reason logged|Cause|Fix|
|--|--|--|
|`Restoring from a golden dump is turned off in BenchPress Settings`|`restore_from_golden` is `0`|Set it back to `1`|
|`No golden dump in <tag> — this site is built from scratch. Rebuild the lab, or run Build golden, to make its deploys ~5x faster.`|The image was built before goldens, or with `enable_golden_images` off|Rebuild the lab, or run **Build golden**|
|`Golden dump was taken from MariaDB X and this server is Y`|The shared server's major version moved|Rebuild the lab's golden against the new server|
|`Could not compare the golden dump's MariaDB … with this server's …`|One of the two versions was unreadable|Check the server answers, then read `docker inspect` on the tag|

**Only the major version has to match.** A patch bump is the same schema
contract, and refusing on one would take every golden on the host out of
service the next time MariaDB was updated.

## The manifest

Each golden records what was baked. This is `crm` on this host:

|Field|Value|
|--|--|
|`lab_id`|`crm`|
|`image_tag`|`benchpress/crm:lab`|
|`frappe_version`|`version-15`|
|`apps`|`crm` from `https://github.com/frappe/crm`, branch `main`|
|`installed_apps`|`crm`, `frappe`|
|`tables`|281|
|`mariadb_version`|`10.6.28-MariaDB-ubu2204`|
|`dump_bytes`|266,129|
|`dump_sha256`|`689a827f…d7d538`|
|`restore_seconds`|5.5|
|`created_at`|2026-08-26|

`mariadb_version` is the one fact whose validity lives outside the image, and
it is the field the deploy compares.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|Every deploy takes the cold path|`restore_from_golden` is off|Set it to `1` in [Settings](/docs/operator/settings-reference)|
|New builds carry no golden|`enable_golden_images` is off|Set it to `1`. Images already built are unaffected|
|One lab is slow and the rest are fast|That image has no dump|**Build golden** on the lab|
|Every golden stopped working after a database upgrade|The dumps were taken on the old major version|Rebuild each lab's golden|
|A restored site is missing an app|The golden was baked from a different recipe|The build verifies the restore against the recipe. Rebuild the lab and read the build log|
|The drill refuses to start|`--i-know-this-is` does not match `base_domain`|Pass the site's real base domain|

## Reference

|Item|Value|
|--|--|
|`enable_golden_images`|`1` — whether a build bakes a dump|
|`restore_from_golden`|`1` — whether a deploy uses one|
|Image label|`benchpress.golden=1`|
|Version label|`benchpress.golden.mariadb=<version>`|
|Deploy Log phrase|`restored from the image's golden dump`|
|Drill|`python3 scripts/golden_drill.py --lab <id> --runs <n> --i-know-this-is <domain>`|
|Golden site prefix|`bpgolden-`|
|Golden database prefix|`_bpgolden`|

## Related

* [The image cache](/docs/operator/image-cache) — what a rebuild costs before you order one.
* [Settings reference](/docs/operator/settings-reference) — the two switches, with their measured values.
* [Diagnostics](/docs/operator/diagnostics) — the `golden_images` coverage check.
* [Read logs and container stats](/docs/user/logs-and-monitoring) — where the site step's wording appears.
