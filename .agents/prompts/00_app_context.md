`<reasoning_effort>40</reasoning_effort>`

# app_context

BenchPress is a Frappe app that drives the Docker daemon on the host it is installed on, so a
careless change here costs a host rather than a page. It is alpha software with one live public
deployment, and its control plane holds every tenant's bench credentials in plain reach of a
whitelisted endpoint. Benchpress reads this file first and then the axis file that matches the work.

The test before touching any file in this repo: **does this change still hold on a host somebody
else runs, with somebody else's benches on it?**

## what_this_app_is

- A Frappe v16 app installed into an existing bench — not a standalone service — declared in
  `pyproject.toml` with `requires-python = ">=3.14"` and one runtime dependency, `docker>=7.0.0`.
- The control plane answers 55 `@frappe.whitelist()` methods across 164 non-test Python modules,
  and puts every slow action on a Redis queue because a deploy takes tens of seconds.
- The browser half is a Vue 3.5 single-page app — 59 `.vue` files under `frontend/src` — built by
  Vite 5.4 against the frappe-ui Tailwind preset, served at `/frontend`.
- A second browser surface is the public marketing site: 11 templates under `benchpress/www/`,
  every one gated behind the `benchpress_public_site` site-config key, absent by default.
- The app talks to exactly three things — the Docker daemon over its socket, one shared MariaDB
  container, and the WireGuard plane owned by `vpn_management`, a `required_apps` entry.
- `benchpress/benchpress/doctype/` holds 22 doctype directories; `Lab` → image, `Bench Instance` →
  container, `Bench Site` → database are the three that carry the product.

## who_uses_it

- A team lead defines a lab once, and a new developer deploys it — so the deploy path is the
  most-run code in the app and the least forgiving of a regression.
- A lab user holds root inside their own bench, which is why `docker_manager.py:342-350` refuses
  `privileged=True` in a comment rather than in passing.
- Guests reach three endpoints only — `benchpress/contact.py:45`, `benchpress/waitlist.py:26` and
  `benchpress/signup.py:20` — each `allow_guest=True`, each POST-only, and each rate-limited by
  `benchpress/throttle.py`.
- Anything under `benchpress/www/` is world-readable when the hosted deployment is on, so a copy
  change there ships to strangers, not to operators.

## how_the_code_is_shaped

- 889 tracked files: 247 `.py`, 139 `.md`, 68 `.js`, 59 `.vue`, 40 `.mdx`, 26 `.html`, 23 `.ts`.
- Five trees carry the work — `benchpress/` (399 files), `frontend/` (165), `docs/` (92), `e2e/`
  (22), `scripts/` (11) — and `docs-site/` (52) plus `docs-bundle/` (42) are generated output.
- The largest non-test modules are `api.py` (799 lines), `mariadb_manager.py` (741),
  `docker_manager.py` (661), `ingress.py` (625) and `lifecycle.py` (522); nothing else clears 500.
- The largest source file in the tree is `benchpress/public/css/bp-landing.bundle.css` at 2571
  lines, and the largest Python file is a copy constant, `site_content.py` at 1150 lines.
- Behavior hides in `benchpress/hooks.py` — `doc_events`, `permission_query_conditions`,
  `has_permission`, `override_whitelisted_methods` and 11 scheduler entries all live there.
- No duplicated-concept folders exist: there is one `utils/` in the SPA and no `helpers/` twin,
  and Benchpress does not create one.

## known_live_defects

- `feather-icons` is a declared dependency in `frontend/package.json:18` with **zero** importing
  files under `frontend/src`, and `vite.config.js:36` still pre-bundles it alongside
  `highlight.js/lib/core`, which no manifest declares at all.
- The repo root carries both `package-lock.json` and `yarn.lock` for one manifest — CI's Docs job
  runs `npm ci`, so the root `yarn.lock` gates nothing and drifts unobserved.
- Two JavaScript linters are configured: eslint through `.pre-commit-config.yaml` (gating) and
  biome through `frontend/package.json` `lint` (not gating, and a different style entirely).
- 51 of the last 200 non-merge commits carry no Conventional Commits header — headers such as
  `Implemented phase two (#228)` — because nothing in CI checks a commit message.
- The Playwright suite — 10 spec files and 8 page objects under `e2e/` — runs in no CI job.
- 56 `frappe.get_all(` / `frappe.get_list(` call sites declare no `limit`; a few are deliberate and
  say so, as at `api.py:485-487`, and the rest are simply unbounded.
- The SPA holds **zero** `AbortController` uses, so no in-flight request is ever cancelled.
- `CLAUDE.md:232` still says to branch from `develop`; `CONTRIBUTING.md:70-72` records that
  `develop` was abandoned at the 0.1.0 release. `version-16` is the only trunk.
- `CLAUDE.md:208` names `--site frontend` in a `run-tests` command — that site has no
  `allow_tests` and an interrupted run leaves its scheduler off, which silently stops all mail.
- `CLAUDE.md:59` counts eight public pages; `benchpress/www/vs/` has held three comparison pages
  since `e6e8d32`, so the count and the routing table under it are both short.

## patterns_worth_propagating

- `benchpress/overview.py:4-11` states the batching contract in its own docstring and keeps it —
  one query per collection, no `get_doc` inside a loop, scoping reused rather than reimplemented.
- `benchpress/request_cache.py` is the memoisation seam, and its docstring says why a module-level
  dict is wrong here: workers are forked and a global outlives the request that filled it.
- `benchpress/throttle.py` is 49 lines and hides the whole rate-limit decision behind
  `@public_form(limit)`, reading the email off the call rather than `form_dict`.
- `frontend/src/utils/clock.js` runs one timer for every subscriber, returns its own unsubscribe,
  and re-aligns to the server's second — the correct shape for anything periodic in the SPA.
- `benchpress/permissions.py` pairs every tenant-scoped doctype's query condition with a
  `has_permission` twin, because query conditions reach only the list engine.
- `benchpress/docker_manager.py` defines each container label once and treats the label filter as
  the sole authority for what the app may remove.

## what_not_to_do

- Do not add a second library for a need the tree has already settled — the icon set is
  `~icons/lucide` (23 files), not `feather-icons` (0 files).
- Do not run `yarn lint` — that is biome, a style this repo has never used, and it rewrites every
  frontend file in one pass.
- Do not name `frontend` in any `run-tests` command; `bp_test_site` locally and `test_site` in CI
  are the sites that carry `allow_tests`.
- Do not hand-edit anything under `docs-site/` or `docs-bundle/` — both are generated, and the
  Docs job fails on a diff it did not produce.
- Do not leave test rows behind on a site: labs, bench instances, credit ledger entries, waitlist
  entries and throwaway users have all been found alive after a run.
- Do not treat a comment in this codebase as decoration — most of them record a measured failure,
  and deleting one deletes the reason.
