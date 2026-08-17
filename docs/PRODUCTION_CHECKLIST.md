# Production readiness checklist

Release-readiness verdict for every whitelisted endpoint and the security-sensitive
components behind them. Seeded from the phase-3 authorization suite
(`benchpress/tests/test_api_authorization.py`), the phase-2 contract/timing suite
(`benchpress/tests/test_api.py`), the branch security review
(`specs/completed/api-test-suite/security-review-phase-3.md`), and a sweep of
`ignore_permissions=True` and secret-handling (`get_decrypted_password` /
`get_password`) paths.

Last reviewed: 2026-07-02.

**Legend** — ✅ Ready · ⚠️ Ready with follow-up · ❌ Not ready for release.

## Whitelisted API endpoints (`benchpress/api.py`)

| Endpoint | Guard | Authz test | Verdict | Notes |
|---|---|---|---|---|
| `get_labs` | login only | timing/contract | ✅ | Shared admin-curated catalog; no per-user data. |
| `get_lab` | login only | timing/contract | ✅ | Single catalog row; no tenant data. |
| `get_lab_templates` | login only | timing/contract | ✅ | Static template list. |
| `create_lab_from_template` | `require_admin` | Guest + non-admin denied; admin allowed | ✅ | Admin-only proven. |
| `build_lab_image` | `require_admin` | Guest + non-admin denied | ✅ | Admin-only proven. |
| `get_benches` | owner filter | hides other users' bench; owner sees own | ⚠️ | Returns decrypted ssh/admin/code-server passwords in the list payload — owner-scoped, but prefer fetching secrets on demand. |
| `create_bench` | login; own deterministic `instance_id` | contract | ✅ | `get_instance_id(session.user, lab)` embeds the caller, so a user can only create/mutate their own bench. |
| `bench_action` | `require_bench_access` + delete is admin-only | cross-user denied; owner-delete denied | ✅ | start/stop/restart owner-scoped; delete admin-gated, both proven. |
| `get_deploy_logs` | `require_bench_access` | cross-user denied | ✅ | |
| `add_device` | login; peer `owner_user = session.user` | device round-trip | ✅ | Creates only the caller's own peer. |
| `remove_device` | `_owned_device_peer` (owner or admin) | device wrapper tests | ✅ | Ownership enforced before delete. |
| `list_devices` | owner filter (`owner_user`), excludes bench peers | device round-trip | ✅ | |
| `get_device_wg_config` | `_owned_device_peer` (owner or admin) | device wrapper tests | ⚠️ | Guard exists; add an explicit cross-user negative test in the API authz suite. |
| `create_site` | `require_bench_access` **only when `bench` set** | contract | ⚠️ | Bench-less call skips the guard and creates an orphan Bench Site; make `bench` mandatory / guard the empty case. |
| `get_user_context` | login (own session) | timing/contract | ✅ | Returns only the caller's own identity/roles. |
| `get_code_server_credentials` | `require_bench_access` | cross-user denied; owner allowed | ✅ | Decrypted password returned only after ownership check. |
| `restart_code_server` | `require_bench_access` | cross-user denied | ✅ | |

## Whitelisted controller methods

| Method | Guard | Test | Verdict | Notes |
|---|---|---|---|---|
| `Bench Instance.enqueue_deploy` | `run_doc_method` read perm (`if_owner`) | contract | ✅ | Framework enforces doc read perm on call. |
| `Bench Instance.enqueue_redeploy` | `run_doc_method` read perm (`if_owner`) | contract | ✅ | |
| `Bench Instance.enqueue_stop` | `run_doc_method` read perm (`if_owner`) | contract | ✅ | |
| `Bench Instance.enqueue_start` | `run_doc_method` read perm (`if_owner`) | contract | ✅ | |
| `Database Server.setup_mariadb` | `has_permission(read)`; DocType admin-only | none | ⚠️ | Admin-only in practice (non-admins have zero perms), but a state-changing op should check `write`, and it has no authz test. |
| `Database Server.start_mariadb` | `has_permission(read)`; DocType admin-only | none | ⚠️ | As above. |
| `Database Server.stop_mariadb` | `has_permission(read)`; DocType admin-only | none | ⚠️ | As above. |
| `Database Server.retry_setup` | `has_permission(read)`; DocType admin-only | none | ⚠️ | As above. |
| `Database Server.get_logs` | `has_permission(read)`; DocType admin-only | none | ✅ | Read op; read check is correct. Add a test. |

## Cross-cutting components

| Component | Evidence | Verdict | Notes |
|---|---|---|---|
| Permission model (`permissions.py` + Bench Instance `if_owner`) | authz suite green | ✅ | Guest / wrong-role / cross-user all rejected; `only_for` raises for non-Administrators. |
| Secret handling (`get_decrypted_password`, `get_password`, `get_root_password`) | api.py, mariadb_manager.py | ✅ | Decryption only behind owner/admin guards; DB root password never logged (only in generated SQL run inside the container). |
| `ignore_permissions=True` (39 uses) | background jobs + system-context writes | ✅ | Confined to enqueued/system flows; user-facing ownership is tracked via `owner` / `owner_user`, and device peer inserts are deliberate (users hold no VPN role). |
| SQL construction (`mariadb_manager`) | review §candidates | ✅ | Identifiers SHA1-hashed, SQL base64-wrapped before shelling — not injectable. |
| Container isolation (`docker_manager.create_bench_container`) | review §candidates | ❌ | Non-privileged (NET_ADMIN + /dev/net/tun only), **but** lab users get in-container root. Not release-ready unless the Docker host enables `userns-remap` (see [wireguard-setup.md](wireguard-setup.md)); without it, container-root ≠ host-root is not guaranteed. |

## Not ready for release — action required

- **❌ Container privilege boundary.** Ship only on a host with Docker `userns-remap`
  enabled. Lab users have in-container root; userns-remap is what keeps that from
  becoming host root. This is a deployment precondition, not an app default.
- **⚠️ `create_site` bench-less path.** Make `bench` mandatory (or guard the empty case)
  so the endpoint cannot create an orphan Bench Site that bypasses `require_bench_access`.
- **⚠️ Database Server state-changing methods.** Switch `setup`/`start`/`stop`/`retry`
  to a `write` permission check and add authorization tests.
- **⚠️ `get_benches` secret exposure.** Move ssh/admin/code-server password retrieval
  out of the bulk list payload to an on-demand, per-bench call.
- **⚠️ `get_device_wg_config` test gap.** Add an explicit cross-user negative test to the
  API authorization suite (the guard exists; the coverage does not).
