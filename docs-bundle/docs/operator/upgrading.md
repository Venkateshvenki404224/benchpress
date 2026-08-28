---
title: Upgrading
description: Move a BenchPress install to a newer release — the backup gate, the
  five steps, the scripted path, rollback, and why lab images are a separate
  opt-in.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# Upgrading

App code, database schema and frontend assets, with a backup gate in front and
a tested rollback behind.

**Who this is for.** Whoever owns the host.

**Before you start.** This upgrades the **BenchPress control plane** — the
Frappe app and its site. Rebuilding the **lab images** your benches run on is
separate and opt-in. See
[Lab images after an upgrade](#lab-images-after-an-upgrade).

|Check|Why|
|--|--|
|You know the site name|every command is scoped to one site|
|You can reach the host bench shell|upgrades are bench commands, not dashboard actions|
|No build or deploy is in flight|migrating mid-deploy can leave benches in a bad state|
|You have read the CHANGELOG for the target release|schema or config changes may need a manual step|

Run every command from the bench root — the directory holding `apps/`,
`sites/` and `env/`. Replace `<site>` with your real site name.

## The scripted path

The bundled script runs steps 0 to 5, enforces the backup gate, and stops on
the first error so a failed upgrade never continues quietly.

```bash
bash apps/benchpress/upgrade.sh <site>
bash apps/benchpress/upgrade.sh <site> version-16   # a specific ref
bash apps/benchpress/upgrade.sh <site> --dry-run    # print the steps only
```

The script does **not** roll back for you. On failure it prints the recorded
pre-upgrade revision and points at [Rollback](#rollback). Read the manual
steps below before relying on it for anything you care about.

## Steps

### 0 — Take a backup. This is the gate

**Do not proceed unless this step succeeds.** A failed backup means there is
nothing to roll back to.

```bash
bench --site <site> backup --with-files
```

A successful run prints the paths of the database dump and the file archives,
written under `sites/<site>/private/backups/`. Record the timestamp. Then
record the revision you are upgrading **from**:

```bash
git -C apps/benchpress rev-parse HEAD > /tmp/benchpress-rollback-sha
git -C apps/benchpress describe --tags --always
```

If `bench backup` fails — disk full, MariaDB unreachable, a permission — stop.
Fix the cause and run step 0 again from the top.

### 1 — Update the app code

```bash
git -C apps/benchpress fetch origin
git -C apps/benchpress checkout <target-branch-or-tag>
git -C apps/benchpress pull
bench pip install -e apps/benchpress
```

### 2 — Migrate

```bash
bench --site <site> migrate
```

If `migrate` fails, stop and [roll back](#rollback). A partially migrated site
must not go back into service.

### 3 — Rebuild the frontend

```bash
cd apps/benchpress/frontend && yarn install && yarn build && cd -
bench build --app benchpress
bench --site <site> clear-cache
```

### 4 — Restart

```bash
bench restart
```

On a development bench, stop `bench start` and start it again.

### 5 — Verify health

See [Verify](#verify) below.

## Verify

Four checks. Run all four before you call it done.

1. **The dashboard loads.** Open `http://<site>:8000/frontend` and sign in.
2. **Migrations are clean.** A second `bench --site <site> migrate` is a no-op,
   with no pending patches.
3. **Benches are still healthy.** Open the Instances list. Existing benches
   still report a healthy container.
4. **The host is still ready.**

   ```bash
   bench --site <site> execute benchpress.diagnostics.run_diagnostics
   ```

If any check fails and cannot be fixed forward quickly, roll back.

## Rollback

Two parts: the code goes back to the revision recorded in step 0, then the
data goes back to the step 0 backup.

1. Return the app to the previous revision:

   ```bash
   git -C apps/benchpress checkout "$(cat /tmp/benchpress-rollback-sha)"
   bench pip install -e apps/benchpress
   ```

2. Restore the pre-upgrade backup:

   ```bash
   bench --site <site> restore \
     sites/<site>/private/backups/<timestamp>-database.sql.gz \
     --with-public-files  sites/<site>/private/backups/<timestamp>-files.tar \
     --with-private-files sites/<site>/private/backups/<timestamp>-private-files.tar
   ```

3. Rebuild and restart:

   ```bash
   bench build --app benchpress
   bench --site <site> clear-cache
   bench restart
   ```

4. Run [Verify](#verify) against the restored install.

**Restore overwrites the current database.** Restore only onto the site you
backed up, and only after deciding the upgrade cannot be fixed forward. This
is the control-plane site, not the shared bench database — that one has its
own runbook at [Backup and restore](/docs/operator/backup-and-restore).

## Lab images after an upgrade

Upgrading the control plane does **not** rebuild the Docker images your
benches run on.

* **Existing benches keep their current image** until you redeploy them. An
  upgrade is non-disruptive to running benches by default.
* To adopt a new Frappe version, open the Lab, run **Rebuild image**, then
  redeploy the affected benches.

Treat a rebuild as an opt-in follow-up, and read
[The image cache](/docs/operator/image-cache) first. An image is 5.5 GB to
19.7 GB, and a rebuild takes tens of minutes.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`bench backup` fails|Disk full, MariaDB unreachable, or a permission|Fix it and re-run step 0. Do not continue|
|`migrate` fails part way|A patch could not apply|Roll back. Do not put a half-migrated site into service|
|The dashboard loads unstyled|Assets were not rebuilt|Step 3, then `clear-cache`|
|Benches show as unhealthy after the upgrade|The health probe changed and the containers predate it|Redeploy the affected benches|
|The upgrade script stopped and said nothing more|It aborts on the first error by design|Read the last command it printed, then follow the runbook|
|A rollback restored but the app still misbehaves|The code was not moved back|Step 1 of [Rollback](#rollback)|

## What is not automated yet

The script chains steps 0 to 5 with the backup gate and abort-on-failure, and
the CHANGELOG records what changed between releases. Automatic rollback when a
step fails mid-upgrade is not built. Until it is, follow the steps in order
and never skip the step 0 gate.

## Reference

|Item|Value|
|--|--|
|Script|`bash apps/benchpress/upgrade.sh <site> [ref] [--dry-run]`|
|Backup command|`bench --site <site> backup --with-files`|
|Backup location|`sites/<site>/private/backups/`|
|Recorded revision|`/tmp/benchpress-rollback-sha`|
|Steps the script runs|0 to 5|
|Automatic rollback|not implemented|

## Related

* [Backup and restore](/docs/operator/backup-and-restore) — the bench database, which this runbook does not cover.
* [The image cache](/docs/operator/image-cache) — before you order any rebuild.
* [Diagnostics](/docs/operator/diagnostics) — the post-upgrade health check in full.
