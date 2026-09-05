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
  `Waitlist Entry` and `Contact Message`. The thirty doctypes that once modelled
  page copy are gone — `benchpress.patches.drop_page_content_doctypes` deletes
  them from a site that still has them.
- **Depends on** `vpn_management` (`required_apps` in `hooks.py`) for the WireGuard
  side.

## Public site

Eight pages under `benchpress/www/`, on nine routes. Each one resolves by
filename. None of them has a `website_route_rules` entry, and none may be
given one.

The whole site is behind one site-config key, `benchpress_public_site`, absent
by default. `benchpress.public_site.require_public_site` raises
`PageDoesNotExistError` for every route and every guest endpoint while it is
unset, and `benchpress.public_site.seed` plants nothing. This site belongs to
the hosted deployment: a self-hoster who installs the app gets their own home
page, their own login screen and no marketing pages.

| Route | Template | Controller | Copy lives in |
|---|---|---|---|
| `/` | `www/index.html` | `www/index.py` | `site_content.LANDING_SEED` |
| `/landing` | `www/landing.html` (extends `index.html`) | `www/landing.py` | `site_content.LANDING_SEED` |
| `/signup` | `www/signup.html` | `www/signup.py` | `www/signup.SIGNUP_SEED` |
| `/login` | `www/login.html` | `www/login.py` | `www/login.LOGIN_SEED` |
| `/about` | `www/about.html` | `www/about.py` | `site_content.ABOUT_SEED` |
| `/self-host` | `www/self-host.html` | `www/self_host.py` | `www/self_host.SELF_HOST_SEED` |
| `/services` | `www/services.html` | `www/services.py` | `www/services.SERVICES_SEED` |
| `/vs/frappe-docker` | `www/vs/frappe-docker.html` | `www/vs/frappe_docker.py` | `www/vs/frappe_docker.COMPARISON_SEED` |
| `/contact` | `www/contact.html` | `www/contact.py` | `www/contact.CONTACT_SEED` |

Fifteen facts that are easy to break:

- `www/login.html` deliberately shadows `frappe/www/login.html`, because
  `TemplatePage.set_template_path` searches `reversed(get_installed_apps())`.
  `www/login.py` calls Frappe's own `get_context` first and only decorates the
  result. Filename shadowing has no off position, so with `benchpress_public_site`
  unset the controller points `context.template` back at `frappe/www/login.html`.
  `TemplatePage` reads that key after `get_context` returns, so the stock page
  serves. Keep the context keys and the DOM contract in step with the framework
  on every Frappe upgrade. Re-read `frappe/www/login.py`,
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
- **A page in a subfolder is a module in a subpackage, and two things have to agree.**
  `www/vs/frappe-docker.html` routes to `/vs/frappe-docker` and its controller is
  `www/vs/frappe_docker.py` — Frappe swaps hyphens for underscores to find it. The
  composed sitemap walks `www/**/*.html` with `rglob` for the same reason; a `glob` would
  have found the top level only and left every comparison page out.
- The header carries **pages only**, never an on-page anchor: an anchor cannot be linked
  from off the page, and the nine-item list it replaced read as a table of contents. The
  landing page's own sections live in the footer instead, where no two rows share a URL.
- The header and footer are one include each, and they render the same markup on
  every route — no variant, no page flag. `site_content.chrome_content` is the only
  thing that resolves the header CTA, `signup_route`, the session state the header
  renders (`is_signed_in`, `login_route`, `console_route`) and the page's
  `csrf_token`. All eight pages must offer the same door: never re-resolve any of
  them in a page controller. Sign-out is a form, not a link — both of Frappe's
  logout endpoints are POST-only.
- The header is fixed, so every page's first section has to clear it. The dock's
  height at each breakpoint is `--m-header-height` in `bp-brand.bundle.css`; the
  desktop clearance is `calc(var(--m-header-height) + …)` in the page's own stylesheet,
  and below 900px `bp-brand.bundle.css` does it through `data-r~="hero"` on the
  section's inner element.
- Every page renders from its constant and reads nothing at render time. There is
  nothing behind a page in Desk any more, so a section that should not appear is
  absent from the template rather than switched off.
- The contact form's routing is constants too, in `benchpress/contact.py`:
  `TOPICS` (first row is the default), `RESPONSE_TIMES` and `ACKNOWLEDGE_SENDER`.
  Only the forwarding address is per-deployment — the `benchpress_contact_email`
  site-config key, falling back to `CONTACT_EMAIL`.
- The seven `Email Template` rows are the one thing `benchpress.public_site.seed`
  still plants, and they are deliberately not a `fixtures` entry: `sync_fixtures`
  imports with `force=True` on every `bench migrate`, which no flag can gate and
  which overwrites an edited body.
- The seven marketing pages extend `benchpress/templates/public_base.html`, not
  `templates/web.html`. It emits no framework stylesheet, no script bundle and no
  boot payload, so `bp-site.bundle.js` takes the request token from `data-csrf-token`
  on the body. `/login` keeps `templates/base.html`, because Frappe's login script
  needs both bundles. The element defaults the framework used to supply — inherited
  weight, line height and letter spacing, and the bare-element margins — are in
  `bp-brand.bundle.css` on `.bp` and under `:where(.bp)`.
- Every stylesheet and script the pages load is a bundler entry point, emitted with
  `include_style` / `include_script` / `bundled_asset` and served under
  `/assets/benchpress/dist/` with a content hash. Editing one needs
  `bench build --app benchpress`; without a build the helpers hand back a path that
  404s. The `bp-` prefix is not decoration — `sites/assets/assets.json` is keyed by
  bare filename across every installed app, and `login.bundle.css` is Frappe's.
  The chrome pair is emitted by `site_head.html`, not by the `web_include_css` /
  `web_include_js` hooks: those are site-wide, and would put the marketing CSS on
  every website route of a self-hosted install.
  A stylesheet's hash changes on every build even when the file did not: Frappe's
  postcss step copies the source through a temp directory with a random name, and
  that name lands in the sourcemap the hash covers. Scripts are content-stable.
  Whatever the bundler does not hash — the icons, the manifest, the logos and the hero
  video — takes one `?v=` token from `site_content.asset_version`.
- **The commands on the public site are the ones that run.** BenchPress installs into a
  Frappe bench you already have, so there is no `git clone` path. `site_content` owns
  `INSTALL_COMMANDS` and `SETUP_COMMAND`, verbatim from `/docs/operator/install`, and both
  `/self-host` and `/llms.txt` read them from there. A test asserts that no public surface
  carries `git clone`: the landing page shipped a clone-and-run pair for months, and it never
  worked.
- `bp-brand.bundle.css` drops every h1-h3 to one size below 900px, with `!important`. A page
  that uses real headings for hierarchy restates each title's size in the `max-width: 900px`
  block of `bp-pages.bundle.css`. A new heading class that skips this renders at 24px on a
  phone.
- Jinja autoescape is off in Frappe, so a template escapes by hand: `| e` on every
  value a controller passes it. What a template renders raw is shipped HTML, a
  macro's output or a framework helper's, and carries a comment saying which. The
  mail bodies in `benchpress/templates/emails/` are the one place guest-typed text
  reaches a template raw, and `benchpress/emails.py` wraps it in `Markup` on the
  way. This is the whole of the rule; no template repeats it.

## Cobalt is the palette of record

Every token lives in `benchpress/public/css/bp-brand.bundle.css`. A new marketing
surface uses those tokens and never a raw hex value.

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
  mode-varying `--danger` triplet into `bp-brand.bundle.css` would let both stop
  inventing one.

## Everyday commands

```bash
docker compose exec backend bench --site frontend migrate
docker compose exec backend bench --site bp_test_site run-tests --app benchpress
docker compose exec backend bench build --app benchpress   # after frontend changes, then:
docker compose restart backend frontend

cd frontend && yarn dev        # SPA hot-reload
cd frontend && yarn test:run   # frontend unit tests

cd e2e && npx playwright test  # has its own config — running from the app root resolves nothing

npm run docs:build && npm run docs:lint && npm run docs:score && npm run docs:links
```

**Never name `frontend` in a `run-tests` command.** That site carries no
`allow_tests`, so the runner refuses it — but only after disabling its scheduler
from a value it holds in memory and restores on a clean exit. A site with the
scheduler off composes mail and never sends it, and no log says so.
`bp_test_site` is the site that exists to be tested; CI uses `test_site`. The
`migrate` line above is right as it stands: migrating your own site is what a
person does.

## Documentation source

`docs/**/*.mdx` is the source; `docs-site/` and `docs-bundle/` are generated and
must never be hand-edited. Only page source belongs under `docs/`: leadtype
lists every `.md` it finds there in `llms.txt` but converts only `.mdx`, so a
working note left in `docs/` is published as a link to a page that was never
written. Internal notes live in `internal/`, and `npm run docs:links` fails on
the dead link either way.

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

## Clean up every test record you create

Whatever a test run puts on a site is yours to remove, in the same session that
made it. That covers users — including any `@example.com` or `.local` address —
throwaway roles, Email Accounts and Domains, queued mail, and the application
rows a test inserted: labs, bench instances, credit accounts and ledger entries,
waitlist entries, contact messages, deploy logs. It also covers any site setting
a test changed.

Prefer a test that tears down its own fixtures, so nothing can be left behind.
Where a console session or a one-off script created the rows, delete them before
the task is called done, and say what was removed. Leftovers are not only
clutter: test users have been found on the live site still holding
`System Manager`.

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

## Working prompts (read before you code)

Six standing prompts under [.agents/prompts/](.agents/prompts/), measured on this repository.
Read `00` once per session, then the axis that matches the task.

| File | Read it when |
|---|---|
| [00_app_context.md](.agents/prompts/00_app_context.md) | Always first — what the app is, how it is shaped, the live defects not to add to |
| [01_use_the_framework_first.md](.agents/prompts/01_use_the_framework_first.md) | Adding a library, a client, a query or a helper |
| [02_containers_and_images.md](.agents/prompts/02_containers_and_images.md) | Touching Docker — image builds, container options, labels, removal |
| [03_security_and_credentials.md](.agents/prompts/03_security_and_credentials.md) | Writing an endpoint, a permission rule or a template that renders a value |
| [04_data_access_and_cost.md](.agents/prompts/04_data_access_and_cost.md) | Writing a query, a loop or a component, or changing the build |
| [05_verification_gates.md](.agents/prompts/05_verification_gates.md) | Before running tests, linting, committing or pushing |

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
