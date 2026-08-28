---
title: API
description: All 50 whitelisted BenchPress endpoints, with arguments, what each
  returns, and the permission check each one makes for itself.
lastModified: "2026-08-28T16:15:34Z"
lastAuthor: Venkatesh
---
# API

Every function this app publishes over HTTP, and what each one checks before it
does anything.

**Who this is for.** Somebody calling BenchPress from another program, or adding
an endpoint and wondering what the house rule is.

**Before you start.** Read [How an endpoint is guarded](#how-an-endpoint-is-guarded).
The decorator publishes a function. It grants nothing. Every entry in the tables
below names its own check, because there is no check anywhere else.

## Calling convention

Every endpoint is a Frappe whitelisted method. Call it by dotted path.

```bash
curl -s https://<host>/api/method/benchpress.api.get_labs \
  -H "Cookie: sid=<session id>"
```

Arguments go as query parameters on a `GET` or as form fields on a `POST`.
Frappe decides the method from the function, not from a route table.

Thirty-five of the fifty are in `benchpress.api`. Four more are module functions
elsewhere. The remaining eleven are document methods, called through
`run_doc_method` rather than by path. All three kinds are marked below.

## How an endpoint is guarded

Five helpers in `benchpress/permissions.py` do the work. An endpoint calls one
of them as its first statement.

|Helper|Passes for|Raises|
|--|--|--|
|`require_app_user()`|`System Manager`, `BenchPress Admin`, `BenchPress User`|`PermissionError`|
|`require_admin()`|`System Manager`, `BenchPress Admin`|`PermissionError`|
|`require_bench_access(name)`|whoever may read that `Bench Instance`|`PermissionError`|
|`is_admin()`|returns a boolean, raises nothing|—|
|`has_app_permission()`|returns a boolean, raises nothing|—|

`require_bench_access` calls `frappe.has_permission` on the document itself. It
scopes because the `BenchPress User` permission row on `Bench Instance` carries
`if_owner: 1`. See [How a row is scoped](/docs/reference/data-model#how-a-row-is-scoped).

A second gate sits above some endpoints. `requires_admission` is a decorator in
`benchpress/credits/guard.py`. It refuses an action before any work is queued,
and it does nothing at all while `enable_credits` is `0`.

|Decorator argument|Refuses when|
|--|--|
|`cost=`|the caller cannot pay the hold|
|`caps=`|the caller is at a cap — concurrency, size, devices or builds a day|
|`payer=`|the charge belongs to somebody other than the caller|

Two endpoints answer a guest. They are listed separately in
[The two guest endpoints](#the-two-guest-endpoints), and both are rate limited.

## Labs and templates

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_labs`|—|every lab the caller may see|`require_app_user`|
|`get_lab`|`name`|one lab, with its instance and recent runs|`require_app_user`|
|`get_lab_form_options`|—|the enums and defaults the New lab form builds itself from|`require_admin`|
|`get_lab_templates`|—|the catalog|`require_app_user`|
|`create_lab_from_template`|`template`, `lab_id`, `title`|`{name, status: "Draft"}`|`require_admin`|
|`build_lab_image`|`lab_name`|`{name, status: "Building"}`|`require_admin`, plus `requires_admission` for cost and the builds-a-day cap|
|`build_lab_golden`|`lab_name`|`{name, status: "Queued"}`|`require_admin`|
|`prewarm_catalog`|—|how many builds were queued|`require_admin`|

`build_lab_image` and `build_lab_golden` queue work and return at once. Watch
the [Build Log](/docs/reference/data-model#build-log) for the result.

`get_lab_form_options` is admin-only because only an admin reaches the New lab
screen. Do not read it as a public enum list.

## Benches

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_benches`|—|the caller's benches, or every bench for an admin|`require_app_user`|
|`create_bench`|`data` (JSON)|`{name, status: "Deploying"}`|`require_app_user`, plus `requires_admission` for the lease cost and the size cap|
|`bench_action`|`bench_name`, `action`|`{name, status}`|`require_bench_access`, and `is_admin` for `delete`|
|`server_time`|—|`{server_now_ms}`|`require_app_user`|

`bench_action` takes four actions: `start`, `restart`, `stop` and `delete`.

|Action|Extra rule|
|--|--|
|`start`, `restart`|goes through `requires_admission`, so a capped caller is refused|
|`stop`|no gate. Stopping is what a refused caller is being told to do|
|`delete`|admin only, and it raises `PermissionError` for anybody else|

`start`, `restart` and `stop` all refuse an instance with no container. A `Draft`
bench has never been deployed, and a reaped one has had its container removed.

`create_bench` is idempotent for a pair of caller and lab. The bench name is an
MD5 of the two, so a second call redeploys rather than making a second bench.

`server_time` exists so a countdown in the browser corrects against the server
clock instead of the laptop's.

## History

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_deploy_logs`|`bench_name`|the log rows for one bench|`require_bench_access`|
|`get_deploy_history`|—|up to 50 recent deploy runs|`require_app_user`, inside `run_history`|
|`get_build_history`|—|up to 50 recent image builds|`require_app_user`, inside `run_history`|

The two history endpoints do not check permissions in `api.py`. They delegate
immediately to `benchpress/run_history.py`, and the check is the first statement
there. This is the one place where the guard is a function call away, so the
table names where it lives.

Both are endpoints rather than a generic list read for a reason.
`Build Log` had no query condition, and reading it through the generic list API
served every user's image builds to everybody. Scoping cannot be added to a
generic read, so it is applied here: deploy rows go through `frappe.get_list`
and pick up `deploy_log_query_conditions`, and build rows are filtered by owner
for anybody who is not an admin.

Both answers carry `window_days`, `limit` and `truncated`. Logs are cleared
after seven days, so neither table is complete, and the answer says so rather
than implying otherwise.

## Devices

Every device endpoint is a wrapper over `vpn_management`. A device is a
`VPN Peer`, not a BenchPress DocType.

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`list_devices`|—|the caller's peers, with status and traffic counters|`require_app_user`|
|`add_device`|`device_name`, `device_type`, `public_key`|the new peer, and its config when the server generated the key|`require_app_user`, plus `requires_admission` for the device cap|
|`remove_device`|`device_name`|`{status: "removed"}`|`require_app_user`|
|`get_device_types`|—|the seven accepted types|`require_app_user`|
|`get_device_wg_config`|`device_name`|the WireGuard configuration text|`require_app_user`|
|`get_vpn_status`|—|whether the caller's tunnel is up|`require_app_user`|
|`run_connection_test`|—|a verdict on the caller's own peer|`require_app_user`|

`get_device_types` exists so no screen hand-types the list.
`run_connection_test` tests the caller's peer and never the shared
infrastructure.

## Credentials

Three endpoints return secrets. All three take a bench name and check access to
that bench.

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_bench_credentials`|`bench_name`|the SSH user, the SSH password and the site admin password|`require_bench_access`|
|`get_code_server_credentials`|`bench_name`|`{url, password}`|`require_bench_access`|
|`restart_code_server`|`bench_name`|`{ok: true}`|`require_bench_access`|

These exist because Frappe does not return `Password` fields in an ordinary
document read. Reading the `Bench Instance` gives you nothing. Ask here.

## Credits

Every endpoint below works while `enable_credits` is `0`. They report that
credits are off rather than failing.

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_user_context`|—|who the caller is, their roles, and whether credits exist|reads roles with `is_admin`, no raise|
|`get_credit_summary`|—|the balance chip, in one indexed read|`require_app_user`|
|`get_credit_statement`|`limit_start`, `limit_page_length`|one page of the caller's own ledger|`require_app_user`|
|`get_purchase_options`|—|the packs for sale, and whether a gateway exists|`require_app_user`|
|`buy_credits`|`pack`|a Razorpay order|`require_app_user`|
|`get_lease_plans`|—|the durations the renew dialog offers|`require_app_user`|
|`renew_bench`|`bench_name`, `plan`, `request_id`|the new lease state|`require_bench_access` and `require_balance`|

`get_user_context` is the one endpoint with no raising guard, and that is
deliberate. It answers what the session already knows about itself. It calls
`frappe.get_roles` and `is_admin`, and it returns no other user's data.

`get_credit_statement` filters on the session, never on an argument. There is no
way to ask for another user's ledger.

`renew_bench` takes a `request_id`. A retried call carrying the same id does not
charge twice. The new deadline extends from the deadline the caller already had,
not from now.

`buy_credits` prices from the pack, never from the caller. See
[Credits and billing](/docs/operator/credits-and-billing) for the gateway.

## Screens

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`get_overview`|—|every tile on the Overview screen, in one request|`require_app_user`|

## Diagnostics

|Endpoint|Arguments|Returns|Checks|
|--|--|--|--|
|`run_diagnostics`|—|eleven read-only environment checks|`require_admin`|
|`preflight_runtime`|`runtime`|whether that runtime can actually start a container|`require_admin`|

`run_diagnostics` reads. `preflight_runtime` creates a container, which is why
it is separate and why it is admin-only. Neither reads the queue workers. See
[Diagnostics](/docs/operator/diagnostics).

## Document methods

Eleven whitelisted methods live on controllers rather than in `api.py`. Frappe
calls them through `run_doc_method`, and it checks the document's own permission
before the method runs.

### Bench Instance

Four methods, used from the Desk form. None calls a permission helper. The
document check plus `if_owner` on the `BenchPress User` role is the guard.

|Method|Does|Extra gate|
|--|--|--|
|`enqueue_deploy`|queues a deploy on `queue-long`|`requires_admission`, lease cost and size cap|
|`enqueue_redeploy`|queues a redeploy|`requires_admission`, lease cost and size cap|
|`enqueue_start`|starts an existing container|`requires_admission`, instance lease cost|
|`enqueue_stop`|stops through `lifecycle.stopped`|none, for the same reason `bench_action` stop has none|

`enqueue_deploy` and `enqueue_redeploy` deduplicate on a job id of
`deploy_bench:<name>`. A second click while a deploy runs says so and queues
nothing.

### Database Server

Five methods. Each one calls `self.has_permission` and throws, so the check is
explicit here rather than inherited.

|Method|Does|
|--|--|
|`setup_mariadb`|creates the shared MariaDB container|
|`start_mariadb`|starts it|
|`stop_mariadb`|stops it|
|`retry_setup`|runs setup again after a failure|
|`get_logs`|returns the last `tail` lines, 100 by default|

### Credit Account

Two methods, both admin-only.

|Method|Arguments|Does|
|--|--|--|
|`post_adjustment`|`credits`, `reason`|moves a balance by hand in either direction, with the reason on the row|
|`post_refund`|`order`, `credits`, `reason`|gives credits back against the Razorpay order that granted them|

`post_adjustment` is how a balance is set without a payment. It is the path the
documentation screenshots used, because the gateway keys are empty on this host.

## The two guest endpoints

Two functions carry `allow_guest=True`. They are the whole surface an
unauthenticated caller can reach, and both are rate limited to the same shape.

|Endpoint|Arguments|Rate limit|Checks|
|--|--|--|--|
|`benchpress.waitlist.join`|`email`, `full_name`, `company`, `use_case`|3 an hour for each email and each IP address|none, by design|
|`benchpress.signup.sign_up`|`email`, `full_name`, `redirect_to`|3 an hour for each email and each IP address|`waitlist_open` and the blocked domain list|

`waitlist.join` always answers the same way. A caller cannot tell a new address
from one already on the list, so the endpoint is not an account oracle.

`signup.sign_up` answers exactly as Frappe's own signup does, behind two gates
from `Credit Settings`. Both gates are off on a self-hosted install. See
[Self-serve signup](/docs/operator/hosted-signup).

Two more waitlist functions are admin-only and not guest-reachable.

|Endpoint|Arguments|Does|Checks|
|--|--|--|--|
|`benchpress.waitlist.approve`|`entries`|approves the selected entries and invites each one|`require_admin`|
|`benchpress.waitlist.notify_of_signup`|—|tells everybody still waiting that signup is live, once each|`require_admin`|

## The whole list, counted

Fifty `@frappe.whitelist()` functions. Every one is in a table above.

|Location|Count|
|--|--|
|`benchpress/api.py`|35|
|`benchpress/benchpress/doctype/database_server/database_server.py`|5|
|`benchpress/benchpress/doctype/bench_instance/bench_instance.py`|4|
|`benchpress/waitlist.py`|3|
|`benchpress/benchpress/doctype/credit_account/credit_account.py`|2|
|`benchpress/signup.py`|1|

Recount after a change:

```bash
grep -rn "@frappe.whitelist" --include=*.py benchpress/ | wc -l
```

## Adding an endpoint

1. Write the function in the module that owns the concern, not in `api.py`.
2. Add a thin wrapper in `api.py` that calls a permission helper first.
3. If the action costs credits or hits a cap, add `requires_admission` under
   `@frappe.whitelist()`.
4. Query with `frappe.qb`. A raw `frappe.db.sql` string is a lint failure.
5. Add the endpoint to the table on this page.

The decorator order matters. `@frappe.whitelist()` goes on top, and
`@requires_admission(...)` below it, so the gate runs inside the published
function.

## Verify

Confirm an endpoint refuses the caller it should refuse:

```bash
bench --site <site> run-tests --app benchpress --module benchpress.tests.test_api_authorization
```

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`PermissionError` from every endpoint|The user holds none of the three roles|Grant `BenchPress User`. See [Users and roles](/docs/operator/users-and-roles)|
|An admin-only screen is blank|The API refused, and the router only redirects|Grant `BenchPress Admin`|
|A password field comes back empty|Frappe hides `Password` fields in a document read|Call `get_bench_credentials`|
|Every deploy is refused|`enable_credits` is `1` and the caller cannot pay the hold|Set it back to `0`, or fund the account|
|`/credits` redirects to Labs|Credits are off, so the screen does not render|Expected. See [Credits and billing](/docs/operator/credits-and-billing)|
|A build endpoint returns at once|It queues the work|Read the Build Log|
|A second deploy click does nothing|The job id deduplicates|Expected. Watch the running deploy|

## Related

* [Data model](/docs/reference/data-model) — the rows these endpoints read.
* [Deploy pipeline](/docs/reference/deploy-pipeline) — what `create_bench` sets running.
* [Production safety](/docs/operator/production-safety) — the endpoint-by-endpoint audit of these guards.
* [Realtime](/docs/reference/realtime) — how a screen hears about the result.
