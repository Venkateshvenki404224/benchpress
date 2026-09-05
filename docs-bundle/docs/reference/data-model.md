---
title: Data model
description: All 20 BenchPress DocTypes with their fields, links, naming and the
  permission rule that scopes each one — plus why there is no Device DocType.
lastModified: "2026-09-01T18:06:47+05:30"
lastAuthor: Venkatesh
---
# Data model

Every DocType the BenchPress module defines, what it holds, and who is allowed
to read a row.

**Who this is for.** Somebody reading rows directly, writing a report, or adding
a field.

**Before you start.** The counts here are the whole module. Twenty DocTypes
exist, three of them are child tables and two are Singles. Read
[How a row is scoped](#how-a-row-is-scoped) before you trust a query.

## The 20 DocTypes

|DocType|Kind|Named by|Holds|
|--|--|--|--|
|[Lab](#lab)|document|`field:lab_id`|a template made concrete: version, apps, size, image|
|[Lab App](#lab-app)|child table|parent row|one app in a lab|
|[Lab Template](#lab-template)|document|`field:key`|a ready-made lab in the catalog|
|[Bench Instance](#bench-instance)|document|controller|one deployed bench|
|[Bench Site](#bench-site)|document|`field:site_name`|a site inside a bench|
|[Bench App](#bench-app)|child table|parent row|one app on a bench|
|[Bench Event](#bench-event)|document|`hash`|an incident seen on a bench|
|[Bench Admission](#bench-admission)|document|`field:bench`|the concurrency and credit claim a bench holds|
|[Site App](#site-app)|child table|parent row|one app installed on a site|
|[Database Server](#database-server)|document|`hash`|the shared MariaDB container|
|[Deploy Log](#deploy-log)|document|`hash`|the text of one deploy run|
|[Build Log](#build-log)|document|`hash`|the text of one image build|
|[Instance Size](#instance-size)|document|`field:size_label`|a resource tier|
|[Lease Plan](#lease-plan)|document|`field:plan_label`|a duration for sale|
|[Credit Account](#credit-account)|document|`field:user`|one balance, one holder|
|[Credit Ledger Entry](#credit-ledger-entry)|document|`hash`|one movement of that balance|
|[Credit Pack](#credit-pack)|document|`field:pack_label`|a bundle of credits for sale|
|[Credit Settings](#credit-settings)|Single|—|every commercial number|
|[BenchPress Settings](#benchpress-settings)|Single|—|Docker, addressing, health and reconciliation|
|[Waitlist Entry](#waitlist-entry)|document|`field:email`|one request for hosted access|

Read the live list rather than this table when you suspect a drift:

```bash
bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'DocType','filters':{'module':'BenchPress'},'fields':['name','issingle','istable'],'limit_page_length':0}"
```

## Devices are VPN Peers

There is no Device DocType, and looking for one is a dead end. A device is a
`VPN Peer` in the `vpn_management` app, which BenchPress names in
`required_apps`.

`benchpress/vpn_adapter.py` is the only seam between the two apps. It keeps the
old device field names and reply shapes, so the Devices screen calls
`add_device` and `list_devices` and never learns the word peer.

A bench container is a `VPN Peer` too. `Bench Instance.vpn_peer` links to it,
and the insert claims the tunnel address from the server pool.

|You are looking for|It is|Reached through|
|--|--|--|
|A user device|`VPN Peer`, named `[Type] Name`|`add_device`, `list_devices`, `remove_device`|
|A bench tunnel address|`VPN Peer`, linked from `Bench Instance.vpn_peer`|`vpn_adapter.create_container_peer`|
|The WireGuard server|`WireGuard Server` in `vpn_management`|the operator's [WireGuard page](/docs/operator/wireguard-setup)|

## How a row is scoped

Frappe applies two separate rules, and a tenant-owned DocType needs both.
`permission_query_conditions` reaches the list engine only. A read of one
document never consults it.

|Rule|Applies to|Registered in|
|--|--|--|
|`permission_query_conditions`|list and report reads|`hooks.py`, 6 entries|
|`has_permission`|a single document read|`hooks.py`, 5 entries|
|`if_owner` on a role|both, from the DocType JSON|the DocType permission rows|

Six DocTypes carry a query condition: `Bench Instance`, `Deploy Log`,
`Build Log`, `Credit Account`, `Credit Ledger Entry` and `Bench Event`.

Five carry a `has_permission` hook. `Bench Instance` is the one that does not,
and it does not need one. Its `BenchPress User` permission row sets
`if_owner: 1`, so Frappe scopes the single-document read itself. This is why
`require_bench_access` works.

A missing half is a leak, not a lint failure. A user could list a row they
cannot open, or open a row they cannot list.

|DocType|A BenchPress User sees|
|--|--|
|`Bench Instance`|rows they own, through `if_owner`|
|`Deploy Log`|logs whose bench they own|
|`Bench Event`|events whose bench they own|
|`Build Log`|builds they started|
|`Credit Account`|their own account, because the name is their email|
|`Credit Ledger Entry`|entries whose `account` is their email|

An admin sees everything. `Administrator`, `System Manager` and `BenchPress Admin` all short-circuit every rule above.

## Lab

A template made concrete. The unit an operator describes once and a user
deploys many times. 22 fields.

|Field|Type|Notes|
|--|--|--|
|`lab_id`|Data|the document name|
|`title`|Data|shown in the app|
|`frappe_version`|Select|the branch the image is built from|
|`status`|Select|whether the lab can be deployed|
|`template`|Link → Lab Template|set when the lab came from the catalog|
|`description`|Small Text||
|`apps`|Table → Lab App|the app list|
|`instance_size`|Link → Instance Size|the default tier|
|`memory_limit`, `cpu_cores`|Data, Int|overrides of the size|
|`iops_limit`, `bps_limit`, `pids_limit`|Int|disk and process ceilings|
|`enable_ssh`, `shell`|Check, Data|the SSH account the deploy provisions|
|`image_tag`|Data|the cached image this lab deploys from|
|`golden_manifest`|Code|what the golden dump contains|
|`build_log`|Code|the last build's text|
|`enable_code_server`|Check|whether a deploy starts the IDE|
|`default_lease_plan`|Link → Lease Plan|credits only|
|`max_lease_minutes`|Int|credits only|
|`deploy_credits`|Float|credits only|

## Lab App

Child table. One app in a lab: `app_name`, `app_label`, `git_url`, `branch`.
It holds what the lab asks for.

## Lab Template

The catalog. 13 fields, including `key` as the name, `logo`, `eta_minutes`,
`most_used`, `is_active`, `sort_order`, an `instance_size` link and an `apps`
child table. A template is read-only to a user. Only an admin creates a lab
from one.

## Bench Instance

One deployed bench. The largest DocType at 36 fields, and the one that holds
secrets.

|Group|Fields|
|--|--|
|Identity|`bench_name`, `lab`, `status`, `frappe_version`, `site_name`|
|Access|`ssh_username`, `ssh_password`, `admin_password`, `code_server_password`, `code_server_url`|
|Address|`domain`, `public_url`, `container_ip`, `wg_ip`, `vpn_peer`, `bridge_network`|
|Container|`container_id`, `container_image`, `runtime`, `node`, `started_at`, `instance_size`|
|Health|`cpu_usage`, `memory_usage`, `container_health`, `last_health_check`|
|Data|`database_server`, `apps`|
|Lease|`expires_at_ts`, `lease_state`, `stop_claimed_at`, `stop_started_at`, `container_stopped_at`, `expiry_attempts`, `expiry_lateness`|
|Reaper|`reap_warned_at`|

The name comes from the owner and the lab, in two steps. `before_insert` sets
`bench_name` to `get_instance_id(session_user, lab)`, an MD5 of the two.
`autoname` then copies `bench_name` into `name`.

The pair is therefore the identity. The same person deploying the same lab twice
gets the same document, and `create_bench` treats the second call as a redeploy.
A duplicate insert that races the first is caught and turned into a redeploy as
well, so two clicks cannot make two benches.

Three fields are passwords: `ssh_password`, `admin_password` and
`code_server_password`. Never send the document as a whole to a client. The
realtime helper in `credits/lease.py` builds an explicit payload for this
reason.

Ten fields sit at permlevel 1: `node`, `runtime`, `bridge_network` and the seven
lease fields. A `BenchPress User` may read them and may not write them. Placement
and expiry are the system's to set.

## Bench Site

A site inside a bench, named by `site_name`. Carries `bench`, `status`,
`admin_password` and an `apps_installed` child table of `Site App`. A bench has
one primary site today, and the DocType does not assume that.

## Bench App

Child table on `Bench Instance`. The same four fields as
[Lab App](#lab-app): `app_name`, `app_label`, `git_url` and `branch`.

The two are separate on purpose. `Lab App` is what the lab asks for, and
`Bench App` is what a bench actually got. A lab edited after a deploy leaves the
two disagreeing, and that difference is the record of it.

## Bench Event

An incident, named by `hash`. Written by the Docker event listener and by the
reconcile pass, never by a user.

|Field|Values|
|--|--|
|`event_type`|`bench_died`, `oom_killed`, `bench_unhealthy`, `bench_healthy`|
|`severity`|`error`, `warning`, `info`|
|`docker_action`|the raw Docker action, kept for evidence|
|`exit_code`|the container exit code, when there was one|
|`occurred_at`, `detail`, `bench`|when, what, and whose|

See [Lifecycle and events](/docs/reference/lifecycle-and-events#incidents).

## Bench Admission

The claim a running bench holds while credits are on. Named `field:bench`, so
one row for each bench and no way to hold two claims for one bench.

`bench` is a Data field and not a Link. The claim outlives a failed insert of
the bench it names. `account`, `claimed_at` and `held_credits` record who pays
and how much is reserved.

With credits off, nothing writes this table.

## Site App

Child table. `app_name` and `app_label`. What is installed on a site.

## Database Server

The shared MariaDB, named by `hash`. Twelve fields: `container_name`, `status`,
`mariadb_version`, `image_tag`, `port`, `mariadb_root_password`, `container_id`,
`container_ip`, `memory_limit`, `volume_name`, `created_at` and `error_message`.

Every bench site's database lives in this one container. See
[The shared database server](/docs/operator/database-server).

## Deploy Log

The text of one deploy run: `bench`, `log_type`, `message`, `timestamp`. The
message is appended line by line and committed on each line, so a reader mid-run
sees what has happened so far.

`log_type` carries the verdict: `success`, `error`, `warning`, or `info` while
the run is going.

## Build Log

The same four fields, with `lab` in place of `bench`. One row for each image
build.

Both log DocTypes are cleared after seven days. Neither is a complete record,
and [Build history and deploy history](/docs/reference/api#history) states the
window rather than implying completeness.

## Instance Size

A resource tier, named by `size_label`. Seventeen fields, and the widest set of
knobs in the model.

|Group|Fields|
|--|--|
|Container|`memory_limit`, `cpu_cores`, `disk_limit`, `pids_limit`|
|Disk rate|`iops_limit`, `bps_limit`|
|Network rate|`inflight_limit`, `rate_average`, `rate_burst`|
|Product|`max_sites`, `include_code_server`, `is_default`, `sort_order`|
|Price|`credits_per_hour`, `price_multiplier`, `default_lease_plan`|

The size is resolved at deploy time and written onto the bench. A size edited in
Desk reaches the next deploy. It does not change a running container.

## Lease Plan

A duration for sale: `plan_label`, `minutes`, `credits`, `is_active`,
`sort_order`. The renew dialog lists the active plans in `sort_order`.

## Credit Account

One balance, named `field:user`, so the document name is the holder's email.
Nothing has to be guessed to know whose account it is.

`balance`, `reserved_credits`, `lifetime_purchased`, `lifetime_spent`,
`active_instances`, `is_suspended` and `low_balance_warned`.

`active_instances` and `reserved_credits` are denormalized counts.
`credits/admission_repair.py` exists because they can drift when a worker dies.

## Credit Ledger Entry

One movement, named by `hash`. `account`, `entry_type`, `credits`,
`balance_after`, `description`, and a `reference_doctype` and `reference_name`
pair pointing at whatever caused it.

`request_id` makes a movement idempotent. A retried purchase or renewal that
carries the same `request_id` does not post twice.

## Credit Pack

A bundle for sale: `pack_label`, `inr_price`, `credits`, `is_active`,
`highlight`, `sort_order`.

## Credit Settings

A Single. Sixteen fields, and Desk-only. Grants, charges, caps, the waitlist
switch and the lease sweep numbers. Every field is documented in the
[Settings reference](/docs/operator/settings-reference).

## BenchPress Settings

A Single. Twenty-six fields. The Settings dialog in the app shows ten of them,
and the rest are at `/app/benchpress-settings`.

`enable_credits` lives here, and it ships as `0`. Nothing in
[Credit Settings](#credit-settings) has any effect while it is `0`.

## Waitlist Entry

One request for hosted access, named by `field:email`. `full_name`, `company`,
`use_case`, `status`, `approved_on` and `invite_sent_on`.

This is the only DocType a guest can cause to be written. See
[the guest endpoints](/docs/reference/api#the-three-guest-endpoints).

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A user lists a row they cannot open|The DocType has a query condition and no `has_permission` hook|Add the missing half in `hooks.py`|
|A user opens a row they cannot list|The reverse of the above|Same fix, from the other side|
|A report shows every user's rows|Reports use the list engine, so check the query condition|Register the DocType in `permission_query_conditions`|
|`Bench Instance` returns nothing for an owner|The role row lost `if_owner`|Restore it. Nothing else scopes a single read|
|Two benches for one person and one lab|Not possible. The name is a hash of both|Look for two labs with different ids|
|A password field is empty over the API|Frappe does not return `Password` fields in a normal read|Use the credentials endpoints|

## Related

* [API](/docs/reference/api) — what reads and writes these rows.
* [Architecture](/docs/reference/architecture) — which module owns each DocType.
* [Lifecycle and events](/docs/reference/lifecycle-and-events) — what changes `status` behind your back.
* [Users and roles](/docs/operator/users-and-roles) — the three roles named above.
