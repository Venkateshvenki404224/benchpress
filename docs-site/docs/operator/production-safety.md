---
title: Production safety
description: What BenchPress is and is not ready to carry — the alpha verdict,
  the container privilege boundary, what is backed up, and the release checklist
  that covers 25 of 52 whitelisted callables.
lastModified: "2026-08-30T17:48:34+05:30"
lastAuthor: Venkatesh
---
# Production safety

Whether BenchPress is safe to run on your host, and what has to be true first.

**Who this is for.** Whoever is deciding what this box will carry.

**Before you start.** Read the verdict before the tables. It has not changed
and it is not hedged.

## The verdict

**BenchPress is alpha software. Do not run it on a host you cannot afford to
lose.**

It is built for developers and small teams spinning up disposable Frappe and
ERPNext environments. It is not built to host customer data. Concretely:

* **It takes host-level privilege.** `setup.sh` adds your user to the `docker`
  group, starts the shared MariaDB and Redis containers, and enables IP
  forwarding under `/etc/sysctl.d`. These are real, persistent changes to the
  host.
* **A lab user gets root inside their bench.** That is by design and it is why
  the runtime matters. See
  [The container privilege boundary](#the-container-privilege-boundary).
* **Database backups are automatic. Restore is manual.** The shared MariaDB is
  dumped nightly to host disk outside its data volume, and the restore path is
  documented and verified. Other bench data in Docker volumes is **not** backed
  up. See [Backup and restore](/docs/operator/backup-and-restore).
* **Single-tenant assumption.** Quotas, rate limits and audit trails are still
  in progress. Run BenchPress for people you trust, on a host dedicated to it.
* **The security review is partial.** It covers 25 of the app's 52 whitelisted
  callables. The credit-purchase path and the per-bench credential endpoint are
  among the 27 it never reached. See
  [the release checklist](#the-release-checklist).

Use it on a dedicated dev box, a VM, or a cloud instance you can rebuild. Not
on your daily-driver workstation, and not on a shared production server.

## The container privilege boundary

This is the one item on the checklist that reads **not ready** without a
deployment precondition.

`create_bench_container` deliberately avoids `privileged`. A bench gets
`NET_ADMIN` and `/dev/net/tun`, and nothing else. But a lab user holds root
**inside** the container, and without a user namespace, in-container UID 0 is
host UID 0.

Close it one of two ways before you ship anything real:

|Option|How|Status here|
|--|--|--|
|Sysbox|`default_bench_runtime = sysbox`, with `sysbox-runc` registered with Docker|the default, and what this host runs|
|Docker userns-remap|`{"userns-remap": "default"}` in `/etc/docker/daemon.json`|see [WireGuard and the VPN plane](/docs/operator/wireguard-setup)|

Running the daemon rootless is an accepted third option.

Prove it, do not assume it:

```bash
bash apps/benchpress/setup.sh <site> --strict
```

`--strict` exits non-zero rather than warning. Use it on any host that matters.

## Steps

1. Read [the verdict](#the-verdict) and decide what this host will carry.
2. Close [the container privilege boundary](#the-container-privilege-boundary).
3. Confirm the platform and versions on
   [Prerequisites](/docs/operator/prerequisites).
4. Confirm backups are landing. See
   [Backup and restore](/docs/operator/backup-and-restore).
5. Run the diagnostics and fix every failing row. See
   [Diagnostics](/docs/operator/diagnostics).
6. Work through [the release checklist](#the-release-checklist) and decide
   which follow-ups you are accepting.

## Verify

```bash
bash apps/benchpress/setup.sh <site> --strict          # exits 0
bench --site <site> execute benchpress.diagnostics.run_diagnostics
ls -lh sites/<site>/private/backups/mariadb/ | tail -3
```

All three must pass on a host carrying anything you would miss.

## The release checklist

Reviewed 2026-07-02, from the authorization suite, the contract and timing
suite, a branch security review, and a sweep of every `ignore_permissions=True`
and secret-handling path. Every row below was re-checked against the code on
2026-08-30. Two findings had been fixed, one described an endpoint that never
existed, and several guard descriptions were wrong.

**What the audit covered.** The app exposes **52** whitelisted callables. This
checklist covers **25** of them: 16 endpoints and 9 controller methods. It also
carried a row for a `create_site` endpoint, which does not exist in the code —
that row is gone. **27 whitelisted callables have never been reviewed**, and
that is the largest gap on this page. They are:

|Never reviewed|Where|
|--|--|
|`buy_credits`, `get_purchase_options`, `get_credit_summary`, `get_credit_statement`, `get_lease_plans`, `renew_bench`|the credit and lease path, including the one that takes money|
|`get_bench_credentials`|decrypts SSH, admin and code-server passwords for one bench|
|`launch_template`, `launch_lab`, `build_lab_golden`, `prewarm_catalog`|the one-click deploy and golden-build path|
|`sign_up`, `join`, `notify_of_signup`, `approve`|`signup.py` and `waitlist.py`, the only self-service entry points|
|`Credit Account.post_adjustment`, `post_refund`|controller methods that move a balance|
|`server_time`, `get_lab_form_options`, `get_device_types`, `get_build_history`, `get_deploy_history`, `get_overview`, `get_vpn_status`, `run_connection_test`, `run_diagnostics`, `preflight_runtime`|the rest|

Treat an unreviewed endpoint as unreviewed, not as safe.

Read the verdicts as: **Ready**, **Ready with a follow-up**, **Not ready**.

### Whitelisted endpoints

`require_app_user` admits `System Manager`, `BenchPress Admin` and
`BenchPress User`. `require_admin` admits the first two. Both are
`frappe.only_for`, so neither is satisfied by login alone.

|Endpoint|Guard|Verdict|Note|
|--|--|--|--|
|`get_labs`|`require_app_user`|Ready|A shared admin-curated catalog. No per-user data|
|`get_lab`|`require_app_user`|Ready|One catalog row|
|`get_lab_templates`|`require_app_user`|Ready|A static list|
|`create_lab_from_template`|`require_admin`|Ready|Admin-only, proven by test|
|`build_lab_image`|`require_admin`|Ready|Admin-only, proven by test|
|`get_benches`|`require_app_user`, owner filter|Ready|No longer returns any password. The field list holds no secret, and a test asserts their absence. Retrieval moved to `get_bench_credentials`|
|`create_bench`|`require_app_user`, own deterministic id|Ready|The id embeds the caller, so a user can only create their own|
|`bench_action`|`require_bench_access`, delete admin-only|Ready|Start, stop and restart are owner-scoped. Delete is admin-gated|
|`get_deploy_logs`|`require_bench_access`|Ready|Cross-user access denied by test|
|`add_device`|`require_app_user`, peer owned by caller|Ready|Writes `owner_user` as the session user, so it creates only the caller's peer|
|`remove_device`|`require_app_user`, then an owned-peer lookup|Ready|Ownership resolved before the delete|
|`list_devices`|`require_app_user`, `owner_user` filter|Ready|Bench peers excluded|
|`get_device_wg_config`|`require_app_user`, then an owned-peer lookup|Follow-up|The guard exists. The cross-user negative test still does not|
|`get_user_context`|login only|Ready|No role check, deliberately: the SPA calls it on boot. Returns the caller's own identity, roles and credit summary, and nothing about another user|
|`get_code_server_credentials`|`require_bench_access`|Ready|Decrypted only after the ownership check|
|`restart_code_server`|`require_bench_access`|Ready|Cross-user denied by test|

### Whitelisted controller methods

|Method|Guard|Verdict|Note|
|--|--|--|--|
|`Bench Instance.enqueue_deploy`|document read permission, owner-limited|Ready|The framework enforces it on call|
|`Bench Instance.enqueue_redeploy`|same|Ready||
|`Bench Instance.enqueue_stop`|same|Ready||
|`Bench Instance.enqueue_start`|same|Ready||
|`Database Server.setup_mariadb`|`frappe.has_permission` with no `ptype`, so `read`|Follow-up|A state-changing operation should check `write`, and it has no authorization test. The doctype grants `read` only to `System Manager` and `BenchPress Admin`, both of which also hold `write`, so the gap is hardening rather than an open door|
|`Database Server.start_mariadb`|same|Follow-up|As above|
|`Database Server.stop_mariadb`|same|Follow-up|As above|
|`Database Server.retry_setup`|same|Follow-up|As above|
|`Database Server.get_logs`|read permission|Ready|A read, checked as a read. Add a test|

### Cross-cutting

|Component|Verdict|Note|
|--|--|--|
|Permission model|Ready|Guest, wrong role and cross-user are all rejected. `only_for` raises for non-administrators|
|Secret handling|Ready|Both decryptions a whitelisted endpoint can reach sit behind `require_bench_access`. The database root password is never logged. One of the two, `get_bench_credentials`, was never in this audit — see the coverage list above|
|`ignore_permissions=True`, 53 uses outside tests|Ready|Confined to enqueued and system flows. Ownership is tracked on `owner` and `owner_user`. The count was 39 at the 2026-07-02 review|
|SQL construction|Ready|Identifiers are hashed and SQL is base64-wrapped before shelling. Not injectable|
|Container isolation|**Not ready without a precondition**|Non-privileged, but a lab user holds in-container root. Ship only on a host with sysbox, userns-remap or a rootless daemon|

### What to fix, in order

1. **The container privilege boundary.** Ship only on a host that closes it.
   This is a deployment precondition, not an app default.
2. **The 27 unreviewed endpoints.** Review them, starting with `buy_credits`,
   which takes money, and `get_bench_credentials`, which decrypts passwords.
3. **`Database Server` state-changing methods.** They call
   `frappe.has_permission` with no `ptype`, which checks `read`. Move them to
   `write` and add authorization tests.
4. **`get_device_wg_config` test gap.** Add an explicit cross-user negative
   test. The guard exists. The coverage does not.

Two items from the 2026-07-02 list are closed. `get_benches` no longer returns
any password. The `create_site` item described an endpoint that does not exist.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`setup.sh --strict` refuses to continue|Neither userns-remap nor rootless is on|Enable sysbox or userns-remap, then re-run|
|A bench container will not start after enabling userns-remap|The remapped daemon cannot see the old storage|Everything must be redeployed. Nothing was deleted|
|Volumes are not in the nightly dump|Only the shared MariaDB is backed up|Take your own copies of anything else|
|A user reached another user's bench|This should not happen and is a security finding|Capture the request and open an issue|

## Reference

|Item|Value|
|--|--|
|Readiness|alpha|
|Strict setup|`bash apps/benchpress/setup.sh <site> --strict`|
|Container capabilities|`NET_ADMIN`, `/dev/net/tun`. Not `privileged`|
|Default runtime|`sysbox`|
|Backed up|the shared MariaDB, nightly, 7 dumps|
|Not backed up|bench Docker volumes|
|Checklist reviewed|2026-07-02, re-verified against the code 2026-08-30|
|Whitelisted callables|52|
|Covered by this checklist|25|
|Never reviewed|27|

## Related

* [Prerequisites](/docs/operator/prerequisites) — platforms and versions.
* [WireGuard and the VPN plane](/docs/operator/wireguard-setup) — userns-remap in full, with its migration warning.
* [Backup and restore](/docs/operator/backup-and-restore) — the half that is automatic.
* [Diagnostics](/docs/operator/diagnostics) — the checks that read the host.
