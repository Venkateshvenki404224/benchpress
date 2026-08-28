---
title: The shared database server
description: One MariaDB holds every bench site's database — where it lives, how
  BenchPress drives it, what drift detection watches, and the four actions on
  the record.
lastModified: "2026-08-28T13:08:38Z"
lastAuthor: Venkatesh
---
# The shared database server

Every bench site's database lives in one shared MariaDB container. This page
covers the record that describes it and the actions on that record.

**Who this is for.** Whoever gets paged when every bench fails at once.

**Before you start.** There is exactly one `Database Server` document on a
normal install, and losing that container loses every bench site. Read
[Backup and restore](/docs/operator/backup-and-restore) before you touch it.

## Steps

1. Open `/app/database-server` in Desk and pick the row.

   ![The Database Server document benchpress-mariadb in Frappe Desk with an Active badge. Basic reads Container Name benchpress-mariadb, Status Active, MariaDB Version 10.6, Image Tag mariadb colon 10.6 and Port 3306. Credentials shows MariaDB Root Password as masked dots. Container Details reads Container IP 172.30.0.3, Memory Limit 1g, Volume Name benchpress-mariadb-data, and a Created At timestamp labelled Asia slash Calcutta. A connection chip at the top reads Bench Instance 15.](../images/operator/database-server/01-database-server.png)

   The record on this host reads container `benchpress-mariadb`, status
   **Active**, MariaDB **10.6** from image `mariadb:10.6`, port **3306**,
   container IP `172.30.0.3`, memory limit **1g**, and volume
   `benchpress-mariadb-data`. A connection chip counts **15 Bench Instance**
   rows against it. `mariadb_root_password` is a masked password field, and it
   stays masked — nothing on this page needs you to reveal it.

   Note the timezone label under `Created At`. Frappe renders every datetime
   in the **site's** timezone, which is `Asia/Calcutta` here, while this
   container answers SQL `NOW()` in UTC. That 5-hour-30-minute gap is the
   `clock_skew` failure on [Diagnostics](/docs/operator/diagnostics), and it is
   why a stored deadline must never be compared against `NOW()`.

2. Use the button that matches what you need. All four are admin-only.

   |Action|Method|What it does|
   |--|--|--|
   |Setup|`setup_mariadb`|Writes the environment file, brings the compose pair up, waits for the server to accept connections, and marks the record `Active`|
   |Start|`start_mariadb`|Starts a stopped container. Does not recreate it|
   |Stop|`stop_mariadb`|Stops the container. Every bench site loses its database until it comes back|
   |Get logs|`get_logs`|Tails the container log, 100 lines by default|

   `retry_setup` re-runs setup after a failure and clears `error_message`.

3. If the record and the container disagree, run **Setup** rather than editing
   the fields. The record describes the container, and the fields are written
   by the action, not read by it.

## Verify

```bash
bench --site <site> execute benchpress.mariadb_manager.check_mariadb_health \
  --kwargs "{'db_server_name':'<name>'}"
```

`True` means the server answered. The scheduled check runs the same call every
five minutes and writes the record's status from it.

## What a site database is

A bench site does not get its own MariaDB. It gets a database and a user
inside the shared one.

|Thing|How it is named|
|--|--|
|The database|`_<sha1 of the site name>` — an identifier, hashed so it is always legal SQL|
|The user|one per site, created at deploy and dropped at teardown|
|Everything else|`information_schema`, `mysql`, `performance_schema`, `sys` and `backups` are excluded from every site listing|

Two consequences an operator should hold on to:

* **A dump of this server is a dump of every tenant.** That is why restore is
  destructive and has no button. See
  [Backup and restore](/docs/operator/backup-and-restore).
* **Dropping a site database is a per-site operation**, and teardown does it
  by name. A restore does not.

## Drift detection

The compose file declares MariaDB and Redis settings as command flags.
BenchPress re-reads the live values every five minutes and reports any that
disagree, because a container can predate a flag, a daemon can refuse one, and
somebody can run `SET GLOBAL`.

|Service|Declared setting|Declared value|
|--|--|--|
|MariaDB|`max_connections`|`500`|
|MariaDB|`innodb_buffer_pool_size`|`134217728` (128 MB)|
|MariaDB|`key_buffer_size`|`16777216` (16 MB)|
|Redis|`maxmemory`|`268435456` (256 MB)|
|Redis|`maxmemory-policy`|`allkeys-lru`|

The buffer-pool hit rate is reported beside the drift list and never judged.
On this host the check reads `MariaDB responding at benchpress-mariadb, buffer pool hit rate 99.97%, on the declared settings` — no drift. The 128 MB pool
rests on a single measurement, so treat the rate as evidence for the next
person to size it on, not as a verdict.

The record also carries a `custom_config` block, applied to the container as
`[mysqld]` settings:

```ini
[mysqld]
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
innodb_buffer_pool_size=536870912
max_connections=500
wait_timeout=28800
```

**`custom_config` is not what the running server took.** It asks for a 512 MB
buffer pool and `utf8mb4_unicode_ci`. Read live, this server answers
`innodb_buffer_pool_size` 134217728 and `collation_server`
`utf8mb4_general_ci` — the compose flag and the image default, not the block
above. Drift detection compares the live server against the compose flags
only, so it reports **on the declared settings** and never mentions the gap.

Read the server before you quote either:

```bash
docker exec benchpress-mariadb mariadb -u root -p<password> -e \
  "SHOW VARIABLES WHERE Variable_name IN
   ('max_connections','innodb_buffer_pool_size','collation_server')"
```

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|Every bench site is down at once|The shared MariaDB is stopped or unhealthy|Press **Start**, then **Get logs** if it does not come back|
|The record says `Error` with a message|Setup failed part way|Read `error_message`, fix the cause, then **Retry setup**|
|Diagnostics reports `mariadb` as failed|The container did not answer the health call|Check the container is running, then read its log|
|A drift line names a setting|The live value disagrees with what compose declares|Decide which is right. Recreating the container adopts the flags|
|A deploy fails creating the site database|The server is up but the root password does not match the record|Re-run **Setup**, which rewrites the environment file|
|`mariadb` passes and a single bench site still fails|That site's own database or user is missing|Redeploy the bench. Teardown and deploy own those two objects|

**Never recreate this container to fix a settings problem.** Every bench
site's data is in `benchpress-mariadb-data`, and a recreate that loses the
volume loses all of it.

## Reference

Measured on this host.

|Field|Value|Ships as|
|--|--|--|
|`container_name`|`benchpress-mariadb`|`benchpress-mariadb`|
|`status`|`Active`|`Pending`|
|`mariadb_version`|`10.6`|`10.6`|
|`image_tag`|`mariadb:10.6`|*(none)*|
|`port`|`3306`|`3306`|
|`container_ip`|`172.30.0.3`|*(written by setup)*|
|`memory_limit`|`1g`|`1g`|
|`volume_name`|`benchpress-mariadb-data`|*(written by setup)*|
|`mariadb_root_password`|encrypted|*(generated)*|
|`error_message`|empty|*(none)*|

Status values are `Pending`, `Active`, `Stopped` and `Error`.

|Schedule|Job|
|--|--|
|Every 5 minutes|`benchpress.mariadb_manager.enqueue_health_check`|
|Daily at 02:00|`benchpress.mariadb_manager.enqueue_backup`|

## Related

* [Backup and restore](/docs/operator/backup-and-restore) — the nightly dump and both restore paths.
* [Diagnostics](/docs/operator/diagnostics) — the `mariadb` and `redis` checks in context.
* [Production safety](/docs/operator/production-safety) — what is and is not backed up.
