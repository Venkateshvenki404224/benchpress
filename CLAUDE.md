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
  `Build Log` — under `benchpress/benchpress/doctype/`. The public site adds
  `Landing Page Settings`, `Signup Page Settings`, `About Page Settings`,
  `Contact Page Settings` (four Singles that hold page copy), `Waitlist Entry`
  and `Contact Message`.
- **Depends on** `vpn_management` (`required_apps` in `hooks.py`) for the WireGuard
  side.

## Public site

Five pages under `benchpress/www/`, on six routes. Each one resolves by
filename. None of them has a `website_route_rules` entry, and none may be
given one.

| Route | Template | Controller | Copy lives in |
|---|---|---|---|
| `/` | `www/index.html` | `www/index.py` | `Landing Page Settings` |
| `/landing` | `www/landing.html` (extends `index.html`) | `www/landing.py` | `Landing Page Settings` |
| `/signup` | `www/signup.html` | `www/signup.py` | `Signup Page Settings` |
| `/login` | `www/login.html` | `www/login.py` | `Signup Page Settings` (the nine `login_*` fields) |
| `/about` | `www/about.html` | `www/about.py` | `About Page Settings` |
| `/contact` | `www/contact.html` | `www/contact.py` | `Contact Page Settings` |

Seven facts that are easy to break:

- `www/login.html` deliberately shadows `frappe/www/login.html`, because
  `TemplatePage.set_template_path` searches `reversed(get_installed_apps())`.
  `www/login.py` calls Frappe's own `get_context` first and only decorates the
  result. Keep the context keys and the DOM contract (spec §4.3) in step with the
  framework on every Frappe upgrade. Re-read `frappe/www/login.py`,
  `frappe/templates/includes/login/login.js`, `frappe/templates/signup.html` and
  `frappe/public/scss/login.bundle.scss` when the framework version moves.
- `/` needs `Website Settings.home_page` to say `index`.
  `frappe.website.utils.get_home_page` falls back to `login` for a guest when
  nothing names a home page, so an empty value serves the login form at `/`.
  `benchpress.public_site.seed.claim_home_page` writes the value once, only when
  it is empty. That field is *also* Frappe's post-login destination for every
  user, so `benchpress.public_site.home` answers ahead of it — via the
  `get_website_user_home_page` hook, which despite the name runs for everyone —
  and keeps a signed-in visitor out of the marketing page. It answers *only*
  while the stored value is still `index`: hooks are read before Website
  Settings, so an unconditional answer would make a stock Desk setting
  guests-only.
- `/landing` is the landing page's second route, and the only one a signed-in
  operator can reach. `path_resolver.resolve_path` maps an empty path to `index`
  and then maps `index` through `get_home_page`, which answers `desk` for a
  System User — so `/` and `/index` both leave the marketing page unpreviewable
  from a logged-in session. `www/landing.html` is one `{% extends %}` of
  `www/index.html` and `www/landing.py` delegates to `index.get_context`, so the
  two routes cannot drift. It carries `sitemap = 0`; `/` stays canonical.
- The header and footer are one include, and `site_content.chrome_content` is the
  only thing that resolves the header CTA, `signup_route`, the session state the
  header renders (`is_signed_in`, `login_route`, `console_route`) and the page's
  `csrf_token`. All five pages must offer the same door: never re-resolve any of
  them in a page controller. Sign-out is a form, not a link — both of Frappe's
  logout endpoints are POST-only.
- Section order lives in the template. Desk owns the copy inside a section,
  whether an optional section renders, and the rows in a repeater.
- Every page renders from a seed constant when its Single is empty. The seed is
  also what `benchpress.public_site.seed.seed_public_site` writes into Desk, so
  each string has one home. The seeder never overwrites an operator's edit.
- The six `Email Template` rows are the exception. They are a `fixtures` entry,
  and `sync_fixtures` imports with `force=True` on every `bench migrate`, so a
  body edited in Desk is overwritten on the next migrate. After an edit, run
  `bench --site frontend export-fixtures --app benchpress` and commit the result.

The contract the five pages were built against is
[internal/public-site-spec.md](internal/public-site-spec.md).

## Cobalt is the palette of record

Every token lives in `benchpress/public/css/brand.css`. A new marketing surface
uses those tokens and never a raw hex value.

- `:root` holds the mode-independent marketing tokens (`--m-ink`, `--m-blue`,
  `--m-panel` and the rest). `.bp[data-mode="dark"]` and `.bp[data-mode="light"]`
  hold the page palette (`--bg0`, `--card`, `--fg`, `--accent`, `--brand`).
- A surface that stays dark in both modes carries `data-ondark`, which re-pins
  the text tokens for its descendants. Never hard-code white text. Add the
  attribute.
- The Espresso ramp (`--gray-*`, `--ink-*`, `--green-*`, `--red-*`) is fenced to
  the console mock on the landing page. That block is a picture of the product.
  Do not mix the two palettes anywhere else.
- `handoff 2/_ds/*/tokens/marketing.css` is superseded. It ships
  `--m-blue: #2490EF`, the Espresso product blue, which every page in the handoff
  overrides with the Cobalt navy `#1F5CF5`. Do not import it, and do not "fix" a
  Cobalt value back to it.
- Cobalt names no error color. `/signup` declares a page-scoped `--bp-danger`
  set, and `/login` falls back to Frappe's own red tokens. Promoting one
  mode-varying `--danger` triplet into `brand.css` would let both stop inventing
  one.

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
- Write the commit message with the `technical-writing` skill: plain, short,
  no filler — the Conventional Commits header above still applies.
- Docstrings are capped at two lines by a `PostToolUse` hook
  ([.claude/hooks/docstring_limit.py](.claude/hooks/docstring_limit.py), wired in
  `.claude/settings.json`). It only flags docstrings the current edit touched, so
  legacy ones are left alone. Review or disable it with `/hooks`.
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

## Agent skills

### Issue tracker

GitHub Issues on `Venkateshvenki404224/benchpress`, via the `gh` CLI.
See `.agents/issue-tracker.md`.

### Triage labels

The five default roles, each label string equal to its name.
See `.agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root.
See `.agents/domain.md`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
