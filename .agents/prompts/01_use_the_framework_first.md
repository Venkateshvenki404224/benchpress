`<reasoning_effort>40</reasoning_effort>`

# use_the_framework_first

This codebase has already picked a winner for every recurring need, and the margins are not close
— 0 raw SQL against 24 `frappe.qb` sites, 0 `axios` against 58 frappe-ui resources, one Docker
client factory against 3 `subprocess.run(` calls in 164 modules. A second way to do a settled
thing is not a preference here; it is a fork that somebody has to reconcile later.

The test before adding a library, a client or a helper: **what does this repo already use for
this, and how many files use it?**

## the_winner_for_each_need

| Need | Winner (files / sites) | Loser, and why it loses |
|---|---|---|
| Database reads | `frappe.qb` (24 sites, 10 files) + `frappe.get_all` (88) | `frappe.db.sql(` — 0 uses, and it bypasses permissions |
| HTTP from the SPA | `createResource` / `createListResource` (58) | `axios` (0), raw `fetch(` (0 in `frontend/src`) |
| UI components | `frappe-ui` (60 files) | Hand-rolled equivalents — none exist, keep it that way |
| Icons | `~icons/lucide` (23 files) | `feather-icons` — declared, 0 imports |
| Docker | `docker` SDK via `get_client()` (41 ops) | `subprocess.run(["docker", …])` — 1 site, compose only |
| JS lint | eslint via pre-commit (gating) | biome via `yarn lint` — not gating, wrong style |
| Rate limiting | `@public_form` in `throttle.py` | A counter written at the call site |
| Per-request memoisation | `local_cache` in `request_cache.py` | A module-level dict — forked workers outlive it |

## database_access

- Claude queries with `frappe.qb` or `frappe.get_all`, never `frappe.db.sql(`, because raw SQL
  skips the permission layer that `permission_query_conditions` registers in `hooks.py:142`.
- The two surviving raw calls are `sql_ddl` in `patches/drop_page_content_doctypes.py:52` and
  `patches/retire_always_on_passes.py:80` — DDL a query builder cannot express, in a patch that
  runs once. Neither is precedent for a `SELECT`.
- A read that must be exhaustive uses `get_all` and a read that must be scoped uses `get_list` —
  `api.py:485-487` names the difference and the consequence of getting it backwards.
- Claude reuses `get_bench_owner_filter()` from `benchpress/permissions.py` rather than writing an
  `owner` filter inline, since the scoping rule then changes in one place.
- A field read on one row uses `frappe.db.get_value` and a whole document uses
  `frappe.get_cached_doc` — the cached form is the default for settings, because
  `BenchPress Settings` is read on nearly every Docker call.

## the_frontend_data_layer

- Every server call goes through a frappe-ui resource declared in `frontend/src/data/` — 16
  modules for 16 concerns — because a resource carries loading, error and refresh state that a
  bare `fetch` would make every component reinvent.
- `frontend/src/data/` is the only place a resource is declared; a component imports one and never
  builds its own, so a screen cannot quietly acquire a second copy of the same request.
- Claude does not reach for `axios` or the browser `fetch` in the SPA — there are zero of each in
  `frontend/src`, and the one raw `fetch` in the tree is `bp-site.bundle.js:36`, which serves the
  public pages where frappe-ui is deliberately not loaded.
- State is `computed` (143 uses) and `watch` (17); `watchEffect` has 0 uses and stays that way,
  because an effect with an implicit dependency set is the hardest kind to review here.

## the_docker_seam

- Every Docker call resolves its client through `docker_manager.get_client()`
  (`docker_manager.py:118-120`), which reads the socket from `BenchPress Settings` — so the socket
  is configurable once, not hard-coded 41 times.
- Claude does not shell out to the `docker` CLI. The single exception is
  `mariadb_manager.py:60`, which runs `docker compose` because the SDK models no compose project.
- The other two `subprocess.run(` sites are `docker_manager.py:98` (`lsblk`) and `install.py:44`,
  both host tools with no SDK equivalent — the bar for a fourth is an API that genuinely does not
  exist, not convenience.

## the_frappe_seams

- Behavior belongs in `hooks.py` and a doctype controller, never in an ad-hoc import chain, since
  `doc_events`, `has_permission` and `override_whitelisted_methods` are where a reviewer looks.
- A whitelisted **document** method inherits Frappe's doctype permission check — which is why
  `bench_instance.py:155` carries no explicit guard — but a **module-level** whitelist inherits
  nothing and must check for itself.
- Claude adds a scheduled job to `scheduler_events` in `hooks.py:255` with a comment saying which
  worker it must land on, because `queue-short` holds neither the Docker socket nor the route
  mount and a job placed there fails in a way no log explains.
- Email bodies are `Email Template` rows planted by `benchpress.public_site.seed`, never a
  `fixtures` entry — `sync_fixtures` imports with `force=True` on every migrate and would
  overwrite an edited body.
- A public route resolves from `benchpress/www/` by filename and gets no `website_route_rules`
  entry, because a rule and a filename that disagree produce a page nobody can find.
- A page in a subfolder needs both halves to agree: `www/vs/frappe-docker.html` →
  `www/vs/frappe_docker.py`, since Frappe swaps the hyphen for an underscore to find the module.
- Claude checks `benchpress/hooks.py` before assuming a save or a submit does the plain thing —
  five doctypes route their permission check through it, and the controller alone will mislead.

## what_not_to_do

- Do not introduce `frappe.db.sql(` for a read — the count is 0 and the permission layer depends
  on it staying 0.
- Do not add a second HTTP client, icon set, or UI kit to the SPA; the table above already names
  the winner and the count behind it.
- Do not build a `docker.DockerClient` anywhere but `get_client()`, because a second factory
  ignores the configured socket and the 600-second timeout.
- Do not cache a lookup table in a module-level global — workers are forked, and
  `request_cache.local_cache` exists for exactly this.
- Do not re-resolve a header CTA, `signup_route` or session flag in a page controller;
  `site_content.chrome_content` is the only resolver, so all pages offer the same door.
- Do not paper over a missing framework feature with a helper before checking `frappe.utils` —
  `cint`, `flt`, `cstr` and `add_days` are already used throughout.
