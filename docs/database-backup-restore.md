# Database Backup & Restore

This runbook covers where BenchPress's automatic MariaDB backups live and how to
turn one back into a database — either on a **scratch container** (to verify a
dump, or to inspect old data) or on a **managed Database Server** (disaster
recovery).

> **Restore is destructive.** A dump created by BenchPress contains **all**
> databases on the server, and restoring it **overwrites every database** in the
> target container. Never point a restore at a live tenant DB server — restore
> to a scratch container, or only during disaster recovery onto a server whose
> current data you have accepted losing.

---

## Where backups live

BenchPress dumps **all databases** of every Active Database Server nightly at
**02:00** (server time) and keeps the **last 7** dumps.

| Location | Path | When |
|----------|------|------|
| Host disk (primary) | `sites/<your-site>/private/backups/mariadb/all_databases_<timestamp>.sql.gz` | Every successful backup — copied off the DB volume so losing the volume does not lose the backups |
| Inside the container (fallback) | `/var/lib/mysql/backups/` in `benchpress-mariadb` | Only when the copy to host disk failed; the in-container file is kept as fallback and pruned on the same 7-dump retention |

To take an out-of-schedule backup, run from `bench console`:

```python
from benchpress.mariadb_manager import backup_database_server
backup_database_server("<database-server-name>")  # returns the host path
```

---

## Restore path A — scratch container (verification / inspection)

Restores a dump into a throwaway MariaDB container. Safe: touches nothing that
BenchPress manages.

1. Start a scratch container (same major version as the source server):

   ```bash
   docker run --name scratch-restore -e MARIADB_ROOT_PASSWORD=scratch -d mariadb:10.6
   ```

2. Wait until it accepts connections:

   ```bash
   docker exec scratch-restore mariadb -u root -pscratch -e "SELECT 1"
   ```

3. Copy the dump in and load it:

   ```bash
   docker cp sites/<your-site>/private/backups/mariadb/<dump>.sql.gz scratch-restore:/tmp/
   docker exec scratch-restore bash -c "gunzip -c /tmp/<dump>.sql.gz | mariadb -u root -pscratch"
   ```

4. Verify a known row came back (see [Post-restore check](#post-restore-check)).

5. Throw the container away:

   ```bash
   docker rm -f scratch-restore
   ```

---

## Restore path B — managed recovery (`bench console`)

Restores a host-side dump into a Database Server that BenchPress manages, using
the non-whitelisted console helper. Use this only for disaster recovery.

> **This overwrites all databases on the target server.** There is deliberately
> no UI or API for it — it can only be run by a human in `bench console`.

1. Open a console on the host bench:

   ```bash
   bench --site <your-site> console
   ```

2. Run the helper with the Database Server doc name and the host dump path:

   ```python
   from benchpress.mariadb_manager import restore_database_server
   restore_database_server(
       "<database-server-name>",
       "sites/<your-site>/private/backups/mariadb/<dump>.sql.gz",
   )
   ```

   It pushes the dump into the container, pipes it through
   `gunzip -c | mariadb -u root`, and raises on any non-zero exit.

3. Verify a known row came back (below), then restart benches that were using
   the server so they reconnect cleanly.

---

## Post-restore check

Confirm real data survived the round trip — pick a table you know has rows
(any tenant site's `tabDefaultValue`, or a table of your own) and select from it:

```bash
docker exec <container> mariadb -u root -p<password> -e \
  "SELECT defkey FROM <database>.tabDefaultValue LIMIT 1"
```

A known row must come back. An empty result or an unknown-table error means the
restore did not load what you expected — do not put the server back into
service.

---

## See also

- [Production Safety & Compatibility](production-safety.md) — what is and is not backed up
- [Upgrading a BenchPress Install](upgrading.md) — the pre-upgrade backup gate for the control-plane site
- [Logs & Monitoring](logs-and-monitoring.md) — where backup failures are logged (Error Log)
