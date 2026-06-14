# Upgrading a BenchPress Install

This runbook upgrades an existing BenchPress install end-to-end — app code,
database schema, and frontend assets — with a pre-upgrade backup gate and a
tested rollback path. Follow it whenever you move an install from one BenchPress
release to a newer one.

> **Scope.** This guide covers upgrading the **BenchPress control plane** (the
> Frappe app and its site). Rebuilding the **lab images** your benches run on is
> a separate, opt-in step covered in [Lab image policy](#lab-image-policy-after-an-upgrade).
>
> Prefer one command? `apps/benchpress/upgrade.sh` runs Steps 0–5 below with the
> same backup gate and abort-on-failure behaviour — see
> [Scripted upgrade](#scripted-upgrade). The manual steps remain the reference
> for what each step does and for [rollback](#rollback).

---

## Before you start

| Check | Why |
|-------|-----|
| You know your site name (e.g. `your-site.localhost`) | Every command is scoped to one site |
| You can reach the host bench shell | Upgrades run as bench commands, not in the dashboard |
| No build or deploy job is in flight | Migrating mid-deploy can leave benches in a bad state |
| You have read the [CHANGELOG](../CHANGELOG.md) for the target version | Schema or config changes may need manual steps |

Throughout this guide, replace `<your-site>` with your real site name and run
commands from the bench root (the directory that contains `apps/`, `sites/`,
and `env/`).

---

## Scripted upgrade

To run the whole flow as one command, use the bundled script. It performs
Steps 0–5 below, enforces the **Step 0 backup gate** (it aborts if the backup
fails), and stops on the first error so a failed upgrade never silently
continues:

```bash
# from the bench root
bash apps/benchpress/upgrade.sh <your-site>
```

Upgrade to a specific branch or tag, or preview every step without changing
anything:

```bash
bash apps/benchpress/upgrade.sh <your-site> version-16   # checkout a target ref
bash apps/benchpress/upgrade.sh <your-site> --dry-run    # print steps only
```

The script does **not** roll back automatically (that is a later slice). On
failure it prints the recorded pre-upgrade revision and points you at the
[Rollback](#rollback) section. The manual steps below document exactly what each
step runs — read them before relying on the script in production.

---

## Step 0 — Take a backup (the gate)

**The upgrade must not proceed unless this step succeeds.** A failed backup
means there is nothing to roll back to, so stop and fix the backup before
touching app code.

```bash
bench --site <your-site> backup --with-files
```

A successful run prints the paths of the database dump and the public/private
file archives, written under:

```
sites/<your-site>/private/backups/
```

Record the timestamp of this backup — you will need it if you roll back. Also
record the exact app revision you are upgrading **from**, so you can return to
it:

```bash
git -C apps/benchpress rev-parse HEAD > /tmp/benchpress-rollback-sha
git -C apps/benchpress describe --tags --always
```

> If `bench backup` fails (disk full, MariaDB unreachable, permissions), **do
> not continue.** Resolve the failure and re-run Step 0 from the top.

---

## Step 1 — Update the app code

Pull the target BenchPress revision into the bind-mounted app directory:

```bash
git -C apps/benchpress fetch origin
git -C apps/benchpress checkout <target-branch-or-tag>
git -C apps/benchpress pull
```

Re-install Python dependencies in case the new release added any:

```bash
bench pip install -e apps/benchpress
```

---

## Step 2 — Run database migrations

Apply schema and fixture changes for the new release:

```bash
bench --site <your-site> migrate
```

If `migrate` fails, **stop here and roll back** (see
[Rollback](#rollback)). A partially-migrated site should not be put back into
service.

---

## Step 3 — Rebuild frontend assets

The BenchPress dashboard is a Vue SPA and must be rebuilt after an upgrade:

```bash
cd apps/benchpress/frontend
yarn install
yarn build
cd -
```

Then refresh Frappe's asset bundles:

```bash
bench build --app benchpress
bench --site <your-site> clear-cache
```

---

## Step 4 — Restart services

```bash
bench restart
```

On a development bench, stop `bench start` and start it again instead.

---

## Step 5 — Verify health

Confirm the upgrade landed cleanly before declaring it done:

1. **Dashboard loads** — open `http://<your-site>:8000/frontend` and sign in.
2. **Migrations are clean** — `bench --site <your-site> migrate` a second time is
   a no-op (no pending patches).
3. **Benches are still healthy** — open the Bench Instances list; existing
   benches should still report a healthy container status.
4. **Run the doctor** (if available) — `bench --site <your-site> execute
   benchpress.doctor.run` reports host and dependency readiness.

If any check fails and cannot be fixed forward quickly, roll back.

---

## Rollback

Rolling back has two parts: restore the **code** to the revision you recorded in
Step 0, then restore the **data** from the Step 0 backup.

1. Return the app to the previous revision:

   ```bash
   git -C apps/benchpress checkout "$(cat /tmp/benchpress-rollback-sha)"
   bench pip install -e apps/benchpress
   ```

2. Restore the pre-upgrade backup (use the database dump and file archives
   printed in Step 0):

   ```bash
   bench --site <your-site> restore \
     sites/<your-site>/private/backups/<timestamp>-database.sql.gz \
     --with-public-files  sites/<your-site>/private/backups/<timestamp>-files.tar \
     --with-private-files sites/<your-site>/private/backups/<timestamp>-private-files.tar
   ```

3. Rebuild assets and restart:

   ```bash
   bench build --app benchpress
   bench --site <your-site> clear-cache
   bench restart
   ```

4. Re-run [Step 5](#step-5--verify-health) against the restored install.

> Restore overwrites the current database. Only restore onto the same site you
> backed up, and only after confirming the upgrade cannot be fixed forward.

---

## Lab image policy after an upgrade

Upgrading the control plane does **not** rebuild the Docker images your benches
run on. When a new release changes a Lab's recommended Frappe version (or you
bump it yourself):

- **Existing benches keep their current image** until you explicitly redeploy
  them — upgrades are non-disruptive to running benches by default.
- To adopt the new version, open the Lab, run **Build Image**, then redeploy the
  affected benches. See [Creating Labs](creating-labs.md).

Treat lab rebuilds as an opt-in follow-up, not part of the control-plane upgrade.

---

## What's not automated yet

The [upgrade script](#scripted-upgrade) now chains Steps 0–5 with the backup
gate and abort-on-failure, and the [CHANGELOG](../CHANGELOG.md) records what
changed between releases so you know which manual steps a multi-release upgrade
needs. Still to come:

- Automatic rollback when a step fails mid-upgrade (the script aborts and points
  you at the recorded revision + backup, but does not restore them for you).

Until that ships, follow the steps above in order and do not skip the Step 0
backup gate.
