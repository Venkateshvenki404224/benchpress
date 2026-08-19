# This Project

## Why BenchPress exists

Onboarding a developer or intern onto a Frappe-based client project used to
burn half a day: install Frappe, match app versions, wire up the N apps a
given client's site needs (client A wants 5 apps, client B wants a different
5-6), provision a server. That tax repeated for every new person and every
environment — and BenchPress is the fix, born out of exactly that pain running
a real team.

The workflow it enables: someone who knows a client/project's required app
stack builds a **template** once (Frappe version + app list). A new developer
gets access to that template and clicks **Deploy** — they get a fully working
bench with the right apps and versions pre-installed, plus SSH access and a
code-server (browser VS Code) session, with no manual setup. They connect from
their own laptop and start working immediately. When the task is done, they
destroy the environment. Spin up, use, tear down — that's the whole loop.

Supporting features that make this workable for a remote team:
- **Shareable code-server sessions** — hand someone a live session instead of
  describing a bug in chat.
- **Every app/site routed over a WireGuard VPN** — keeps betas and client
  instances private while still letting other VPN-connected teammates reach
  and inspect a given instance. The same mechanism doubles for staging.
- Possible future direction: reuse the same deploy/spawn mechanism to hand a
  fresh container to an AI agent to develop in.

**This is not a Frappe Cloud alternative or competitor.** It's a narrower,
different tool: a local, self-hosted dev-environment and onboarding suite for
teams running Frappe apps, not a hosting platform.

## What it is technically

**BenchPress** is a FAPI (Frappe) app built on the Frappe framework. Describe a
**Lab** (a Frappe version + app list) and it builds a Docker image, deploys a
container, gives it a private WireGuard IP, and hands back SSH access and a
working site URL. Vue 3 SPA on the front, `frappe.qb` and background jobs on
the back.

- **Bench:** this checkout (`apps/benchpress`) is bind-mounted into the parent
  `benchpress_devops` compose stack — bench commands run inside its `backend`
  container, not a standalone bench. See the parent repo's `CLAUDE.md` for the
  compose topology.
- **Site:** hard-coded to `frontend` (repo-wide invariant, see parent `CLAUDE.md`).
- **Login:** `Administrator` / `ADMIN_PASSWORD` from the repo-root `.env`.
- **Frontend:** Vue 3 SPA in `frontend/` (frappe-ui, vue-router, Tailwind).
- **Doctypes:** `Lab`, `Bench Instance`, `Bench Site`, `Bench App`, `Database
  Server`, `Credit Account` / `Credit Ledger Entry` / `Credit Pack`, `Deploy Log`,
  `Build Log` — under `benchpress/benchpress/doctype/`.
- **Depends on** `vpn_management` (`required_apps` in `hooks.py`) for the WireGuard
  side.

## Everyday commands

```bash
docker compose exec backend bench --site frontend migrate
docker compose exec backend bench --site frontend run-tests --app benchpress
docker compose exec backend bench build --app benchpress   # after frontend changes, then:
docker compose restart backend frontend

cd frontend && yarn dev        # SPA hot-reload
cd frontend && yarn test:run   # frontend unit tests

cd e2e && npx playwright test  # has its own config — running from the app root resolves nothing
```

## Commits & CI (must pass before every push)

- Conventional Commits: `type(scope): summary` (`feat`, `fix`, `refactor`, `test`,
  `docs`, `chore`, `perf`). Branch from `develop`, PR back into `develop` — never
  commit to `main`.
- `uvx pre-commit@4.3.0 run --all-files` — ruff (Python) + prettier/eslint (JS/Vue).
  **Never run `yarn lint`** — that's biome, a different style than the repo has
  ever used, and it will rewrite every frontend file.
- Full checklist: [CONTRIBUTING.md](CONTRIBUTING.md).

## Two things that will bite you

- Query with `frappe.qb`, never `frappe.db.sql` — and every `@frappe.whitelist()`
  must check permissions itself.
- Behavior lives in doctype controllers and `hooks.py`, not just the obvious file
  — check `benchpress/hooks.py` before assuming a save/submit does the plain thing.

## Skills

- **Any code change** → `code-style`, always.
- **Big or gnarly tasks** (build/deploy orchestration, container lifecycle, credit
  ledger math) → `dsa-conscious-coding` alongside `frappe-app-dev`.
- **Any Frappe work** (doctypes, controllers, whitelisted APIs, migrations,
  permissions) → `frappe-app-dev`.
- **Before committing to a plan or design** → `grill-me` to pressure-test it first.
- **A plan, spec, or issue that should ship in slices** → `issue-to-phases` to
  break it into phase specs and drive the branch/PR workflow.
- **Reviewing a diff or PR** → `quality-code-review`.
- **Docs, commit messages, PR descriptions, the README** → `technical-writing`.
- **New or changed doctype forms/list views** → `ui-design`.
