---
title: Backup and restore
description: Where the nightly MariaDB dumps land, how long they are kept, and
  the two restore paths — a scratch container for verification, and managed
  recovery from bench console.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Backup and restore

Where BenchPress's automatic MariaDB dumps live, and how to turn one back into
a database.

**Who this is for.** Whoever owns the host, and only them. There is no button
and no API for a restore, on purpose.

**Before you start.**

**A restore overwrites every database on the target server.** A dump made by
BenchPress contains **all** databases on the shared MariaDB, so restoring it
replaces every bench site at once. Never point a restore at a live server
unless you have accepted losing what is on it. Restore to a scratch container
instead.

## Steps

Pick the path that matches what you are doing.

|Path|Use it to|Risk|
|--|--|--|
|[A, a scratch container](#path-a-a-scratch-container)|verify a dump, or read old data|none. It touches nothing BenchPress manages|
|[B, managed recovery](#path-b-managed-recovery)|rebuild a server after a real loss|destroys the target server's current data|

## Where backups live

Every Active `Database Server` is dumped nightly at **02:00** server time. The
last **7** dumps are kept.

|Location|Path|Written|
|--|--|--|
|Host disk (primary)|`sites/<site>/private/backups/mariadb/all_databases_<timestamp>.sql.gz`|after every successful backup. It is copied off the database volume, so losing the volume does not lose the backups|
|Inside the container (fallback)|`/var/lib/mysql/backups/` in `benchpress-mariadb`|only when the copy to host disk failed. Pruned on the same 7-dump retention|

To take a dump outside the schedule, run it from `bench console`:

```python
from benchpress.mariadb_manager import backup_database_server
backup_database_server("<database-server-name>")   # returns the host path
```

**Only the shared MariaDB is backed up.** Other bench data in Docker volumes
is not. Take your own copies of anything that matters. See
[Production safety](/docs/operator/production-safety).

## Path A, a scratch container

Loads a dump into a throwaway MariaDB. Nothing BenchPress manages is touched.

1. Start a scratch container on the same major version as the source:

   ```bash
   docker run --name scratch-restore -e MARIADB_ROOT_PASSWORD=scratch -d mariadb:10.6
   ```

2. Wait until it accepts connections:

   ```bash
   docker exec scratch-restore mariadb -u root -pscratch -e "SELECT 1"
   ```

3. Copy the dump in and load it:

   ```bash
   docker cp sites/<site>/private/backups/mariadb/<dump>.sql.gz scratch-restore:/tmp/
   docker exec scratch-restore bash -c "gunzip -c /tmp/<dump>.sql.gz | mariadb -u root -pscratch"
   ```

4. Run the [post-restore check](#post-restore-check).

5. Throw the container away:

   ```bash
   docker rm -f scratch-restore
   ```

## Path B, managed recovery

Loads a host-side dump into a `Database Server` that BenchPress manages. Use
this only after a real loss.

**This overwrites all databases on the target server.** There is deliberately
no UI and no API for it. A human runs it in `bench console`.

1. Open a console on the host bench:

   ```bash
   bench --site <site> console
   ```

2. Run the helper with the document name and the host dump path:

   ```python
   from benchpress.mariadb_manager import restore_database_server
   restore_database_server(
       "<database-server-name>",
       "sites/<site>/private/backups/mariadb/<dump>.sql.gz",
   )
   ```

   It pushes the dump into the container, pipes it through
   `gunzip -c | mariadb -u root`, and raises on any non-zero exit.

3. Run the [post-restore check](#post-restore-check).

4. Restart the benches that were using the server, so they reconnect cleanly.

## Post-restore check

Confirm real data survived the round trip. Pick a table you know had rows —
any site's `tabDefaultValue` will do — and select from it.

```bash
docker exec <container> mariadb -u root -p<password> -e \
  "SELECT defkey FROM <database>.tabDefaultValue LIMIT 1"
```

A known row must come back. An empty result or an unknown-table error means
the restore did not load what you expected. Do not put the server back into
service.

## Verify

Check the schedule is actually running, not just configured. A backup nobody
watches is not a backup.

```bash
ls -lh sites/<site>/private/backups/mariadb/ | tail -8
```

You should see up to seven dumps, the newest from last night. If the newest is
older than that, the scheduled job is not running — see
[Diagnostics](/docs/operator/diagnostics).

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|No dumps on host disk|The nightly job has never run, or the scheduler is stopped|Check `bench --site <site> doctor`, then run `backup_database_server` by hand|
|Dumps exist only inside the container|The copy to host disk failed|Fix the disk or the permission, then re-run the backup. The in-container copy is the fallback, not the plan|
|More than 7 dumps|Retention did not prune|Harmless. Delete the oldest by hand|
|A restore ran and a site still fails|The site's MariaDB **user** was not in the dump, or its password changed|Redeploy that bench. Deploy owns the user|
|`restore_database_server` raises immediately|The path is wrong, or the file is not readable by the bench user|Use the full path the backup helper returned|
|The restore finished and the check returns nothing|The dump did not hold what you expected|Do not put the server back into service. Try an older dump|

## Reference

|Item|Value|
|--|--|
|Schedule|daily, `0 2 * * *` server time|
|Job|`benchpress.mariadb_manager.enqueue_backup`|
|Retention|7 dumps|
|Scope|all databases on the server|
|Host path|`sites/<site>/private/backups/mariadb/all_databases_<timestamp>.sql.gz`|
|Container fallback|`/var/lib/mysql/backups/`|
|Manual backup|`benchpress.mariadb_manager.backup_database_server`|
|Manual restore|`benchpress.mariadb_manager.restore_database_server`|
|Backup timeout|3600 s|

## Related

* [The shared database server](/docs/operator/database-server) — the record these dumps come from.
* [Upgrading](/docs/operator/upgrading) — the pre-upgrade backup gate for the control-plane site.
* [Production safety](/docs/operator/production-safety) — the full list of what is not backed up.
