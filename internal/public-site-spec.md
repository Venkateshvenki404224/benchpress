# Public site — integration contract

Status: contract. Contributors build against this file independently.
Anything ambiguous here becomes an integration bug, so this file is deliberately literal:
exact fieldnames, exact dotted paths, exact context keys, exact seed strings.

Source of truth for the design: `handoff 2/landing.html`, `handoff 2/pages.html`
(signup / login / about / contact behind `sc-if`), `handoff 2/README.md` and
`handoff 2/_ds/*/tokens/*.css`. The repeated content in the mockups lives in the
`<script type="text/x-dc">` block at the bottom of each file; every array there is
reproduced verbatim below as seed data.

---

## 0. Rules that apply to every phase

1. **Query with `frappe.qb`.** Never `frappe.db.sql`. `frappe.get_all` / `frappe.db.get_value`
   are fine for simple reads.
2. **Every `@frappe.whitelist()` checks permissions itself** — `require_admin()` or
   `require_app_user()` from `benchpress/permissions.py`. `allow_guest=True` needs the
   reviewed-justification comment, a `@rate_limit`, and input clipping, exactly as
   `benchpress/waitlist.py` does it.
3. **Docstrings are capped at two lines** by the `PostToolUse` hook.
4. **Section order lives in the template, not in Desk.** Desk owns the copy inside a
   section, whether the section renders at all (a `Check`), and the rows inside a
   repeater. Desk never owns "the pipeline comes after the bento".
5. **No new guest read endpoints.** Page content is rendered server-side by the page
   controllers. The only guest-writable surfaces are the three forms in §3.
6. **Seed once, never overwrite.** The install hook plants seed content only when the
   Single has never been saved and only into empty child tables. An operator's edit must
   survive `bench migrate`.
7. **Every configurable string is nullable in code.** A page must render with an empty
   Single: fall back to the seed constant, never to a blank page or a traceback.

### Key notation

Content keys below (`landing.hero.headline`) are stable identifiers used for
cross-referencing between contributors. They are **not** stored anywhere. Where a key maps to a
Desk field the field is named; where it maps to structural chrome it is marked
`[TEMPLATE]` and must be hard-coded in the Jinja file.

---

## 1. Content inventory

### 1.1 Global chrome (shared header / footer)

Rendered by `benchpress/templates/includes/` (owned by another phase — see §7 notes).
This section is the **contract** those includes must satisfy, not permission to edit them.

| Key | Value / source | Kind |
|---|---|---|
| `chrome.logo.dark` | `/assets/benchpress/images/logo/wordmark-on-dark.png` | `[TEMPLATE]` |
| `chrome.logo.light` | `/assets/benchpress/images/logo/wordmark-on-light.png` | `[TEMPLATE]` |
| `chrome.logo.mark` | `/assets/benchpress/images/logo/mark.png` | `[TEMPLATE]` |
| `chrome.logo.alt` | `Benchpress` | `[TEMPLATE]` |
| `chrome.theme_toggle.dark_label` | `Light` | `[TEMPLATE]` |
| `chrome.theme_toggle.light_label` | `Dark` | `[TEMPLATE]` |
| `chrome.nav.items` | Desk — `Landing Page Settings.nav_items` | **Desk** |
| `chrome.footer.tagline` | Desk — `Landing Page Settings.footer_tagline` | **Desk** |
| `chrome.footer.links` | Desk — `Landing Page Settings.footer_links` | **Desk** |
| `chrome.footer.copyright` | Desk — `Landing Page Settings.footer_copyright` | **Desk** |
| `chrome.footer.trademark` | Desk — `Landing Page Settings.footer_trademark` | **Desk** |
| `chrome.auth` | Session — a guest is offered `Log in` → `/login`; a signed-in visitor `Dashboard` → `/frontend` and a `Log out` button | `[TEMPLATE]` |
| `chrome.auth` | Session — a guest is offered `Log in` → `/login`; a signed-in visitor `Dashboard` → `/frontend` and a `Log out` button | `[TEMPLATE]` |

The mockup's `data-mode="dark|light"` attribute lives on the outermost `.bp` wrapper. The
toggle only flips that attribute; it persists to `localStorage` under the key
`bp-mode`. Default is `dark`.

**Landing chrome is a floating pill dock** (`position:fixed;top:18px`); the four
non-landing pages use a plain top bar. Both are `[TEMPLATE]`.

### 1.2 `/` — Landing

Section order, fixed in the template:

`hero` → `templates-marquee` → `paths` → `bento` → `pipeline` → `console` → `agents`
(optional) → `compare` → `services` → `about` (optional) → `testimonials` (optional) →
`faq` → `cta` → `footer`

#### hero (`#top`)

| Key | Seed value | Kind |
|---|---|---|
| `landing.hero.badge_text` | `Open source, AGPL-3.0` | Desk `hero_badge_text` |
| `landing.hero.badge_version` | `v16` | Desk `hero_badge_version` |
| `landing.hero.headline` | `A Frappe environment in the time it takes to read this line.` | Desk `hero_headline` |
| `landing.hero.headline_accent` | `read this line.` | Desk `hero_headline_accent` |
| `landing.hero.subhead` | `Pick a version and an app set. Press deploy. Benchpress builds an isolated Docker environment with its own site, database and browser VS Code, and puts it on your private WireGuard mesh. No bench commands, no SSH, no ticket to the one person who knows.` | Desk `hero_subhead` |
| `landing.hero.cta_primary_label` | `Start free — 500 credits` | Desk `hero_cta_primary_label` |
| `landing.hero.cta_primary_url` | `/signup` | Desk `hero_cta_primary_url` |
| `landing.hero.cta_secondary_label` | `Self-host it instead` | Desk `hero_cta_secondary_label` |
| `landing.hero.cta_secondary_url` | `#paths` | Desk `hero_cta_secondary_url` |
| `landing.hero.assurances[]` | `No card required` / `Bring your own server` / `Failed builds are free` | Desk `hero_assurances` (child) |

`landing.hero.headline_accent` is rendered in `--accent`; the template splits the headline
on that substring. If the accent string is absent from the headline the whole headline
renders plain — no error.

Hero terminal mock — **all `[TEMPLATE]`**, it is a picture of the product:

```
deploy · erpnext-demo                                   step 7 of 11
00:00  ✓  Reserved a container slot
00:04  ✓  Pulled bp/erpnext-v15:cached
00:22  ✓  Container up · mariadb, redis, code-server
00:49  ✓  Created site erpnext-demo.bp.local
01:16  •  Installing erpnext · migrating
$ bench build --production
10.13.13.24    code-server :8443    0 credits charged so far
Site live in 1m 52s
```

#### templates-marquee

| Key | Seed | Kind |
|---|---|---|
| `landing.templates.eyebrow` | `Templates` | Desk `templates_eyebrow` |
| `landing.templates.cards[]` | see below | Desk `template_cards` (child) |

Seed rows (`app_name`, `build_time`, `icon`), in order:

| app_name | build_time | icon |
|---|---|---|
| `ERPNext v15` | `~90s` | `/assets/benchpress/images/app-icons/erpnext.svg` |
| `Frappe HR` | `~2m` | `.../hrms.svg` |
| `Frappe CRM` | `~60s` | `.../crm.svg` |
| `Helpdesk` | `~75s` | `.../helpdesk.svg` |
| `Frappe Learning` | `~90s` | `.../lms.svg` |
| `Custom image` | `build once` | `.../frappe.svg` |

The marquee doubles the list in the template (`cards + cards`) for the CSS loop —
**do not** seed twelve rows.

README requires a trademark line under the template gallery. It is **not** in the mockup;
add it: reuse `landing.footer.trademark` (`footer_trademark`) rendered small under the
marquee.

#### paths (`#paths`)

Two columns: Hosted, Self-hosted.

| Key | Seed | Kind |
|---|---|---|
| `landing.paths.hosted.eyebrow` | `Hosted` | Desk `paths_hosted_eyebrow` |
| `landing.paths.hosted.badge` | `Fastest way in` | Desk `paths_hosted_badge` |
| `landing.paths.hosted.title` | `You want a site, not a server.` | Desk `paths_hosted_title` |
| `landing.paths.hosted.body` | `Sign in, deploy a lab, get the URL and the IDE link. We run the host, the mesh and the upgrades. 500 credits to start, no card.` | Desk `paths_hosted_body` |
| `landing.paths.hosted.points[]` | see below | Desk `path_points` (child, `path = Hosted`) |
| `landing.paths.hosted.cta_primary` | `Start free — 500 credits` → `/signup` | Desk `paths_hosted_cta_label` / `_url` |
| `landing.paths.hosted.cta_secondary` | `Talk to us` → `/contact` | Desk `paths_hosted_cta2_label` / `_url` |
| `landing.paths.selfhosted.eyebrow` | `Self-hosted` | Desk `paths_self_eyebrow` |
| `landing.paths.selfhosted.title` | `You already have the server.` | Desk `paths_self_title` |
| `landing.paths.selfhosted.body` | `Clone it, point it at your Docker daemon, keep every container and credential in-house. No account, no telemetry, no ceiling on labs.` | Desk `paths_self_body` |
| `landing.paths.selfhosted.terminal` | `$ git clone github.com/Venkateshvenki404224/benchpress`<br>`$ cd benchpress && ./setup.sh` | Desk `paths_self_terminal` (Code) |
| `landing.paths.selfhosted.chips[]` | `AGPL-3.0` / `Docker + WireGuard` / `Your data, your host` | Desk `path_points` (child, `path = Self-hosted`) |
| `landing.paths.selfhosted.cta_primary` | `Read the repo` → repo URL | Desk `paths_self_cta_label` / `_url` |
| `landing.paths.selfhosted.cta_secondary` | `Have us install it` → `#services` | Desk `paths_self_cta2_label` / `_url` |
| `landing.paths.footnote` | `Same code either way — the hosted build is this repo with billing attached.` | Desk `paths_footnote` |

`landing.paths.hosted.points[]` seed:

1. `Nothing to install — first environment in about 90 seconds`
2. `WireGuard config issued per device, revocable in one click`
3. `Failed builds and stopped instances cost nothing`

#### bento

| Key | Seed | Kind |
|---|---|---|
| `landing.bento.eyebrow` | `What you get` | Desk `bento_eyebrow` |
| `landing.bento.title` | `Four things per lab, every time, without anyone typing bench.` | Desk `bento_title` |
| `landing.bento.body` | `A Lab template pins the Frappe version, the app set and the seed data — so the environment your intern gets is the environment you tested.` | Desk `bento_body` |
| `landing.bento.cards[]` | five rows below | Desk `feature_cards` (child) |

Seed rows (`title`, `body`, `icon`, `span`):

1. `Browser VS Code, attached to the container` — `code-server runs inside the same container as the site, so the file you edit is the file the site serves. No local bench, no Docker Desktop, no "works on my machine".` — `terminal` — `Wide`
2. `Nothing on the public internet` — `Every site answers on a WireGuard mesh address, one key per device, revocable in a click.` — `shield` — `Standard`
3. `Metering you can argue with` — `Deploys are free. Stopped instances and failed builds are free. Every line lands in the ledger.` — `credit-card` — `Standard`
4. `Reusable lab templates` — `Pin the version, the apps and the branches once. Build a custom image from your own repo and deploy from it forever.` — `layout-template` — `Standard`
5. `Disposable on purpose` — `Remove the environment when the work is done. The confirmation tells you exactly what gets destroyed — container, site, databases — before you type the name.` — `trash-2` — `Standard`

The illustration inside each card is `[TEMPLATE]` (the `hooks.py` snippet, the three mesh
rows, the `0 / credits for a run that fails` stat, the three-line `apps.json`). Card 1 code
block, verbatim:

```
hooks.py  ·  apps/erpnext/erpnext
app_name = "erpnext"
doc_events = {
  "Sales Invoice": {"on_submit": "erpnext.hooks.notify"},
}
```

Card 2 mesh rows `[TEMPLATE]`: `10.13.13.2 your laptop` (green),
`10.13.13.24 erpnext-demo` (accent, pulsing), `10.13.13.31 crm-sandbox` (amber).
Card 3 stat `[TEMPLATE]`: `0` / `credits for a run that fails`.
Card 4 code `[TEMPLATE]`: `frappe@version-16` / `erpnext@version-15` / `hrms@develop`.

#### pipeline (`#how`)

| Key | Seed | Kind |
|---|---|---|
| `landing.pipeline.eyebrow` | `The pipeline` | Desk `pipeline_eyebrow` |
| `landing.pipeline.title` | `One click, four phases, eleven steps.` | Desk `pipeline_title` |
| `landing.pipeline.body` | `Benchpress is a control plane, not a host. It talks to a Docker daemon — ours or yours — runs the bench commands you would have typed, and hands the result to the mesh.` | Desk `pipeline_body` |
| `landing.pipeline.default_phase` | `site` | Desk `pipeline_default_phase` |
| `landing.pipeline.phases[]` | four rows | Desk `pipeline_phases` (child) |
| `landing.pipeline.steps[]` | eleven rows | Desk `pipeline_steps` (child) |
| `landing.pipeline.failure_title` | `If a step fails` | Desk `pipeline_failure_title` |
| `landing.pipeline.failure_body` | `the run stops at that step, the container is discarded, and nothing is metered — a failed run costs nothing.` | Desk `pipeline_failure_body` |

Architecture diagram labels — `[TEMPLATE]`:
`Architecture`, `Your device` / `10.13.13.2` / `Browser, WireGuard client and VS Code in a tab. The only way in.`,
`Benchpress control plane` / `Frappe app`, chips `REST / API keys` `Deploy queue` `Credit ledger`,
`The host · Docker daemon` / `/var/run/docker.sock`, `bench container` / `frappe + apps` /
`gunicorn · socketio` / `code-server :8443`, `shared services` / `mariadb :3306` /
`redis cache · queue` / `volume /sites`, `WireGuard mesh` / `10.13.13.0/24` /
`Every site answers on a mesh address. Nothing is published to the internet.`

**Phase seed** (`phase_key`, `label`, `step_range`, `summary`, `timing`, `plane_nodes`, `plane_chips`):

| phase_key | label | step_range | plane_nodes | plane_chips |
|---|---|---|---|---|
| `request` | `Request` | `1-2` | `device,control` | `api,queue,ledger` |
| `image` | `Image` | `3-4` | `control,host` | `queue` |
| `site` | `Site` | `5-8` | `host` | *(empty)* |
| `network` | `Network` | `9-11` | `host,mesh,device` | `ledger` |

Summaries / timings:

- `request` — `Benchpress checks the plan, confirms the balance and reserves room on the host before anything is pulled.` / `Under a second — deploying is free; nothing is metered until the container runs.`
- `image` — `The app list becomes a layer. Templates reuse a cached image; a custom lab builds one once and keeps it.` / `Cached template: ~10s. First custom build: 3-6 minutes.`
- `site` — `The container comes up and Benchpress runs the exact bench commands you would have typed, in order.` / `Roughly 60-120 seconds depending on the app set.`
- `network` — `The environment joins the mesh, gets health-checked, and only then are the credentials handed over and the meter started.` / `5-10 seconds, then the environment is yours.`

**Step seed** (`phase_key`, `step_number`, `title`, `detail`, `command`):

1. `request` / 1 / `Reserve a container slot` / `The API validates the template, checks concurrency against your plan and reserves CPU, memory and a site name on the target host.` / `POST /api/method/benchpress.deploy\n{ "template": "erpnext-v15" }`
2. `request` / 2 / `Check the balance` / `Deploying costs nothing. Benchpress confirms the account can cover the first hour of runtime and that you are inside your concurrency cap.` / `credits.check(user="you@example.com", size="Small")`
3. `image` / 3 / `Resolve the app list` / `Frappe version, apps and branches are pinned into an apps.json — the same file a manual bench build would use.` / `apps.json\n  frappe@version-16\n  erpnext@version-15`
4. `image` / 4 / `Pull or build the image` / `A matching layer is pulled from the registry. Custom labs run a real image build, and its log is streamed into Deploy history line by line.` / `docker build --build-arg APPS_JSON_BASE64=…\n  -t bp/erpnext-v15 .`
5. `site` / 5 / `Start the container and services` / `The bench container starts alongside MariaDB, Redis and code-server, with the sites directory on a named volume so data survives a restart.` / `docker run -v bp_sites:/home/frappe/…/sites`
6. `site` / 6 / `Create the site` / `A fresh site is created with a generated administrator password, stored encrypted and revealed only to you.` / `bench new-site erpnext-demo.bp.local\n  --admin-password ****`
7. `site` / 7 / `Install apps and migrate` / `Every app in the template is installed, then migrations run. This is the step that fails loudest, so its output is kept verbatim.` / `bench --site erpnext-demo.bp.local install-app erpnext\nbench migrate`
8. `site` / 8 / `Build assets` / `Frontend bundles are built inside the container and served by its own nginx — no shared asset host to drift out of sync.` / `bench build --production`
9. `network` / 9 / `Attach the WireGuard route` / `The container is given a mesh address and a peer entry per registered device. Nothing is bound to a public interface.` / `wg set wg0 peer <pubkey>\n  allowed-ips 10.13.13.24/32`
10. `network` / 10 / `Health check` / `Benchpress fetches the site over the mesh until it answers. If it never does, the run is marked failed and the container is torn down.` / `GET /api/method/ping → pong`
11. `network` / 11 / `Hand over credentials` / `Site URL, mesh IP, code-server link and passwords appear on the lab page. The hourly meter starts at this point, and only this point.` / `ledger.start(lab="erpnext-demo", size="Small")`

> `benchpress/www/home_content.py` holds a **different**, more accurate eleven-step list
> keyed to the real `deploy_pipeline.DEPLOY_STEPS`. The mockup's list is the one specified
> here because this is a marketing page and the handoff is the design contract. See §7.

#### console (`#console`)

| Key | Seed | Kind |
|---|---|---|
| `landing.console.eyebrow` | `The console` | Desk `console_eyebrow` |
| `landing.console.title` | `Status you can read at a glance.` | Desk `console_title` |
| `landing.console.body` | `Bench status and container health are separate columns, because they fail separately. Deploy history keeps every log line. Devices shows who is on the mesh.` | Desk `console_body` |
| `landing.console.callouts[]` | three rows | Desk `console_callouts` (child) |

Callout seed (`title`, `body`, `icon`):

1. `Secrets stay hidden` — `Administrator passwords are stored encrypted and revealed once, to you, behind a click.` — `eye-off`
2. `Elapsed time per step` — `You can see which step is slow, and the exact failing command when a build breaks.` — `timer`
3. `Role-aware` — `Users see instances and deploy. Admins get templates, build logs, devices and billing.` — `users`

**Everything inside the three console tabs is `[TEMPLATE]`.** It is a screenshot mock in the
Espresso palette and must not be made editable. Verbatim strings:

Tabs: `Instances` (`list`), `Deploy history` (`file-text`), `Devices` (`laptop`).

*Instances*: header `Instances` / `6 instances · 4 running, 1 stopped` / `New lab`.
Columns `Lab` `Bench` `Container` `Uptime`. Rows:

| icon | name | sub | bench | container | uptime | action |
|---|---|---|---|---|---|---|
| erpnext | `erpnext-demo` | `ERPNext v15 · Small · you` | `Deploying…` (info) | `Starting` (info) | `—` | `Deploying…` |
| hrms | `hr-v16` | `Frappe HR · Medium · priya` | `Running` (ok) | `Healthy` (ok) | `6d 04h` | `Open site` |
| crm | `crm-sandbox` | `Frappe CRM · Small · ravi` | `Running` (ok) | `Unreachable` (warn) | `2d 11h` | `VPN off` |
| helpdesk | `helpdesk-client-a` | `Helpdesk · Small · agency` | `Running` (ok) | `Healthy` (ok) | `17h 22m` | `Open site` |
| lms | `lms-intern-3` | `Frappe Learning · Small · intern` | `Stopped` (idle) | `Stopped` (idle) | `—` | `Start` |

Footnote: `crm-sandbox is Unreachable — its owner's device is not connected to the mesh.`

*Deploy history*: `Deploy history · erpnext-demo` / `9 runs, last 7 days` / `1,342 credits left`.
Steps (`state`, `title`, `cmd`, `elapsed`):

- done / `Reserve a container slot` / `POST /api/method/benchpress.deploy` / `0.4s`
- done / `Pull the lab image` / `docker pull bp/erpnext-v15:cached` / `11s`
- done / `Start the container and services` / `docker run -v bp_sites:/home/frappe/…` / `18s`
- done / `Create the site` / `bench new-site erpnext-demo.bp.local` / `27s`
- active / `Install apps and migrate` / `bench --site erpnext-demo.bp.local install-app erpnext` / `1m 45s`
- todo / `Build assets` / `bench build --production` / `—`
- todo / `Attach the WireGuard route` / `wg set wg0 peer <pubkey>` / `—`

Failure banner: `Failed at step 2 — Preparing the lab image` /
`no branch version-16 on github.com/frappe/hrms` / `build discarded · 0 credits charged` /
buttons `Edit apps and rebuild`, `View raw log`.

Raw log block: `Installing app erpnext...` / `Updating DocTypes for erpnext : [==============] 100%` /
`Updating customizations for Address` / `$ bench build --production` /
`Built js/erpnext.bundle.js in 12.4s`

*Devices*: `Devices` / `WireGuard · 3 registered` / `Add device`. Rows:

- `laptop` / `Priya · MacBook Pro` / `10.13.13.2 · handshake 12s ago` / `Connected` (ok)
- `monitor` / `Ravi · Windows desktop` / `10.13.13.7 · handshake 40s ago` / `Connected` (ok)
- `laptop` / `intern-3 · loaner` / `config downloaded, never connected` / `Not connected` (warn)

Row action `Revoke`. Footnote: `Each device gets its own key. Revoking one leaves the others connected.`

#### agents (`#agents`) — optional section

Rendered only when `Landing Page Settings.show_agents` is checked (default 1).

| Key | Seed | Kind |
|---|---|---|
| `landing.agents.eyebrow` | `For AI coding agents` | Desk `agents_eyebrow` |
| `landing.agents.title` | `Disposable environments, spawned by API.` | Desk `agents_title` |
| `landing.agents.body` | `Everything the console does is an endpoint. An agent asks for a fresh ERPNext environment, runs against it, reads the logs and tears it down — inside the mesh, with a credit ceiling so a runaway loop can't run up a bill.` | Desk `agents_body` |
| `landing.agents.points[]` | three rows | Desk `agent_points` (child) |
| `landing.agents.examples[]` | three rows | Desk `agent_api_examples` (child) |
| `landing.agents.footnote` | `ttl_minutes and credit_ceiling are both enforced server-side.` | Desk `agents_footnote` |
| `landing.agents.badge` | `202 accepted` | Desk `agents_badge` |

Points seed (`icon`, `text`):
`bot` / `One container per agent run — no shared state`;
`terminal` / `Logs and bench output returned as JSON`;
`lock` / `Scoped tokens, per-key credit limits, auto-expiry`.

API examples seed (`tab_label`, `code`) — three tabs `deploy`, `logs`, `destroy`, code verbatim:

```
POST /api/method/benchpress.deploy
{
  "template": "erpnext-v15",
  "name": "agent-run-4821",
  "ttl_minutes": 30,
  "credit_ceiling": 20
}

→ 202 {
  "instance": "agent-run-4821",
  "status": "deploying",
  "url":  "https://agent-run-4821.vpn",
  "ide":  "https://agent-run-4821.vpn:8443",
  "logs": "/api/.../BLD-26-242"
}
```

```
GET /api/method/benchpress.logs?run=BLD-26-242

→ 200 {
  "step": 7,
  "title": "Install apps and migrate",
  "elapsed": "1m 45s",
  "lines": [
    "Installing app erpnext...",
    "Updating DocTypes for erpnext : 100%",
    "$ bench build --production"
  ]
}
```

```
DELETE /api/method/benchpress.instance
{ "instance": "agent-run-4821" }

→ 200 {
  "destroyed": true,
  "container": "removed",
  "databases": "dropped",
  "credits_charged": 6
}
```

The `copy` affordance beside the code block is `[TEMPLATE]`.

#### compare

| Key | Seed | Kind |
|---|---|---|
| `landing.compare.eyebrow` | `Versus doing it by hand` | Desk `compare_eyebrow` |
| `landing.compare.title` | `The same environment, minus the afternoon.` | Desk `compare_title` |
| `landing.compare.col_manual` | `Manual bench` | Desk `compare_col_manual` |
| `landing.compare.col_bp` | `Benchpress` | Desk `compare_col_bp` |
| `landing.compare.col_bp_badge` | `One click` | Desk `compare_col_bp_badge` |
| `landing.compare.rows[]` | six rows | Desk `comparison_rows` (child) |

Row seed (`aspect`, `manual`, `benchpress`):

1. `New environment` / `30–90 min, SSH required` / `One click, ~90 seconds`
2. `Who can do it` / `Someone who knows bench` / `Anyone on the team`
3. `An intern's first day` / `A morning of setup calls` / `A link and a password`
4. `When it breaks` / `Scroll the terminal, guess` / `Named failing step, then rebuild`
5. `Access` / `Open a port, hope` / `Mesh-only, per-device keys`
6. `Automation` / `Shell scripts you maintain` / `HTTP API with credit ceilings`

#### services (`#services`)

| Key | Seed | Kind |
|---|---|---|
| `landing.services.eyebrow` | `Done for you` | Desk `services_eyebrow` |
| `landing.services.title` | `The software is free. The afternoons are what we sell.` | Desk `services_title` |
| `landing.services.body` | `Run Benchpress yourself and it costs nothing but a server. When you would rather hand it over, these are the four things we do.` | Desk `services_body` |
| `landing.services.cards[]` | four rows | Desk `service_cards` (child) |
| `landing.services.cta_title` | `Not sure which door is yours?` | Desk `services_cta_title` |
| `landing.services.cta_body` | `Tell us the team size, the server you have and what breaks today. We will say plainly whether you need us at all.` | Desk `services_cta_body` |
| `landing.services.cta_label` | `Book a 20-minute call` | Desk `services_cta_label` |
| `landing.services.cta_url` | `/contact` | Desk `services_cta_url` |

Card seed (`number`, `icon`, `title`, `body`, `meta`):

1. `01` / `server` / `Managed hosting` / `We run the host, the mesh and the upgrades. You get a console, a credit balance and someone to call.` / `Hosted · monthly`
2. `02` / `hammer` / `Setup on your server` / `One engagement: Benchpress installed on your machine, WireGuard configured, templates seeded, keys handed over.` / `One-time · fixed scope`
3. `03` / `terminal` / `Custom Frappe apps` / `The app your process actually needs, built against a Benchpress lab so every review runs on a real site.` / `Project · by sprint`
4. `04` / `layout-template` / `Team training` / `Half a day on bench, labs and the deploy pipeline, so the next new joiner onboards themselves.` / `Remote or on-site`

#### about (`#about`) — optional section

Rendered only when `Landing Page Settings.show_about` is checked (default 1). A teaser for
`/about`, not a second copy of it: the prose is authored here, and the four numbers beside it
are read from `About Page Settings.stats` so the two pages cannot disagree.

| Key | Seed | Kind |
|---|---|---|
| `landing.about.eyebrow` | `About` | Desk `about_eyebrow` |
| `landing.about.title` | `We built this because onboarding cost us half a day, every time.` | Desk `about_title` |
| `landing.about.body` | `Frappe's own tooling creates a bench well enough. Our problem started after that: every new developer, and every client stack they moved between, meant matching versions and wiring apps by hand. Benchpress is that half-day, spent once.` | Desk `about_body` |
| `landing.about.link_label` | `Read the full story` | Desk `about_link_label` |
| `landing.about.link_url` | `/about` | Desk `about_link_url` |
| `landing.about.stats[]` | four rows | `About Page Settings.stats` (child) |

#### testimonials — optional section

Rendered only when `Landing Page Settings.show_testimonials` is checked (default 1).

| Key | Seed | Kind |
|---|---|---|
| `landing.testimonials.eyebrow` | `In use` | Desk `testimonials_eyebrow` |
| `landing.testimonials.disclaimer` | `Placeholder — swap in real quotes and logos` | Desk `testimonials_disclaimer` |
| `landing.testimonials.quotes[]` | three rows | Desk `testimonials` (child) |
| `landing.testimonials.logos[]` | *(empty at seed)* | Desk `logo_strip` (child) |

Quote seed (`quote`, `person_name`, `person_role`, `is_placeholder=1`):

1. `An intern used to cost us a morning of setup. Now they get a link, a password and a VS Code tab before standup.` / `Placeholder name` / `Placeholder — engineering lead`
2. `Every client demo is its own container. Nothing leaks between them and nothing is on the public internet.` / `Placeholder name` / `Placeholder — Frappe agency`
3. `Our agent spins up a fresh ERPNext site per run, reads the logs and destroys it. The credit ceiling is the safety net.` / `Placeholder name` / `Placeholder — automation team`

The template doubles the quote list for the marquee, exactly as the mockup does. The
disclaimer renders whenever **any** row has `is_placeholder` set, or the logo strip is empty.

#### faq

| Key | Seed | Kind |
|---|---|---|
| `landing.faq.title` | `Questions` | Desk `faq_title` |
| `landing.faq.items[]` | six rows | Desk `faq_items` (child) |

Item seed (`question`, `answer`, `default_open`):

1. `Do I need to know bench or Docker?` / `No. Deploying a template needs a name and a click. Bench commands only show up in the log, and only if you expand it.` / `1`
2. `What is the difference between hosted and self-hosted?` / `The code — there isn't any. The hosted build is this repo with billing attached. Hosted means we run the server, the mesh and the upgrades; self-hosted means you do, for free, forever.` / `0`
3. `Where do the environments actually run?` / `As Docker containers on a server — ours on the hosted build, or one you connect: your VPS, your bare metal, a machine in the office. Benchpress orchestrates; it doesn't hold your data.` / `0`
4. `Can an agent spin environments up and down on its own?` / `Yes. Issue a scoped API key with a credit ceiling and a TTL. The agent deploys, works, reads logs and destroys the instance; the ceiling stops a runaway loop.` / `0`
5. `What happens to credits if a build fails?` / `Nothing is charged. Failed builds and stopped instances are free; the ledger in Settings shows every line so you can check.` / `0`
6. `Is the VPN optional?` / `On the hosted build, no — it's the access path. Self-hosted, you can expose sites yourself, but the default assumes private.` / `0`

The template splits the list into two columns by index parity, matching the mockup.

#### cta (`#start`)

| Key | Seed | Kind |
|---|---|---|
| `landing.cta.title` | `Create a Frappe environment, press deploy, get a working site and a VS Code window.` | Desk `cta_title` |
| `landing.cta.primary_label` | `Start free — 500 credits` | Desk `cta_primary_label` |
| `landing.cta.primary_url` | `/signup` | Desk `cta_primary_url` |
| `landing.cta.secondary_label` | `Clone the repo` | Desk `cta_secondary_label` |
| `landing.cta.secondary_url` | repo URL | Desk `cta_secondary_url` |
| `landing.cta.footnote` | `GitHub sign-in is one click and needs no email verification. Self-hosting needs no account at all.` | Desk `cta_footnote` |

#### footer

| Key | Seed | Kind |
|---|---|---|
| `landing.footer.tagline` | `Isolated Frappe environments, deployed in one click and kept on your private network.` | Desk `footer_tagline` |
| `landing.footer.links[]` | thirteen rows | Desk `footer_links` (child) |
| `landing.footer.copyright` | `© 2026 Benchpress. AGPL-3.0 licensed.` | Desk `footer_copyright` |
| `landing.footer.trademark` | `Frappe, ERPNext and Frappe HR are trademarks of Frappe Technologies Pvt. Ltd. Benchpress is an independent project, not affiliated with or endorsed by Frappe Technologies.` | Desk `footer_trademark` |

Footer link seed (`column_heading`, `label`, `url`), in order — the controller groups by
`column_heading` preserving first-seen order:

| column_heading | label | url |
|---|---|---|
| `Product` | `Pipeline` | `/#how` |
| `Product` | `Console` | `/#console` |
| `Product` | `Templates` | `/#top` |
| `Developers` | `Agent API` | `/#agents` |
| `Developers` | `Self-hosting guide` | `/#paths` |
| `Developers` | `GitHub` | `https://github.com/Venkateshvenki404224/benchpress` |
| `Services` | `Managed hosting` | `/#services` |
| `Services` | `Setup on your server` | `/#services` |
| `Services` | `App development` | `/#services` |
| `Services` | `Training` | `/#services` |
| `Company` | `About us` | `/about` |
| `Company` | `Contact` | `/contact` |
| `Company` | `Sign in` | `/login` |

Nav item seed (`Landing Page Settings.nav_items`, fields `label`, `anchor`, `is_cta`):

| label | anchor | is_cta |
|---|---|---|
| `Hosted or self-host` | `/#paths` | 0 |
| `Pipeline` | `/#how` | 0 |
| `Console` | `/#console` | 0 |
| `Agents` | `/#agents` | 0 |
| `Services` | `/#services` | 0 |
| `About` | `/about` | 0 |
| `Contact` | `/contact` | 0 |
| `Start free` | `/signup` | 1 |

### 1.3 `/signup` — Request access

Section order: `intro` → `form` **or** `pending` (mutually exclusive) → `footer`.

| Key | Seed | Kind |
|---|---|---|
| `signup.badge` | `Reviewed by a human` | Desk `badge_text` |
| `signup.title` | `Request access to hosted Benchpress.` | Desk `title` |
| `signup.body` | `Hosted accounts are approved manually while we keep capacity honest — usually within one business day. Tell us what you plan to run and we will either open the account with 500 credits or say why not.` | Desk `intro_body` |
| `signup.steps[]` | three rows | Desk `signup_steps` (child) |
| `signup.selfhost_note` | `**Don't want to wait?** Self-hosting needs no account and no approval — clone the repo, run ./setup.sh, and you are running the same code we host.` | Desk `selfhost_note` (Text Editor) |
| `signup.form.title` | `Access request` | Desk `form_title` |
| `signup.form.subtitle` | `All fields except the message are required.` | Desk `form_subtitle` |
| `signup.form.privacy_note` | `We use this to decide on access and nothing else. No newsletter.` | Desk `form_privacy_note` |
| `signup.form.submit_label` | `Send request` | Desk `form_submit_label` |
| `signup.form.login_prompt` | `Already approved?` / link `Log in` → `/login` | Desk `form_login_prompt` |
| `signup.pending.title` | `Request received — pending review` | Desk `pending_title` |
| `signup.pending.body` | `We read every request by hand. If it fits the capacity we have, you will get a login link and 500 credits, usually within one business day. If it doesn't, you will get a plain answer instead of silence.` | Desk `pending_body` |
| `signup.pending.while_you_wait[]` | two rows | Desk `pending_links` (child) |
| `signup.pending.back_label` | `Back to the form` | Desk `pending_back_label` |

Steps seed (`step_number`, `title`, `body`):

1. `You tell us what you plan to run` / `Apps, Frappe version, how many people need environments. Two minutes of typing.`
2. `We read it and decide` / `A person checks capacity and fit. Usually within one business day, and always with an answer either way.`
3. `Approved accounts start with 500 credits` / `Enough for a few environments and a week of poking. Deploys are free; failed builds cost nothing.`

`pending_links` seed (`icon`, `text`, `url`):

- `github` / `While you wait, the repo is public — clone it and self-host the same code for free.` / repo URL
- `book-open` / `The self-hosting guide covers Docker, WireGuard and the first template end to end.` / `/docs`

**Form field labels and placeholders — `[TEMPLATE]`**, because each one is bound to a
concrete `Waitlist Entry` field and a Desk-editable label would let an operator rename a
field out of alignment with its column:

| Field | Label | Placeholder | Maps to |
|---|---|---|---|
| text | `Full name` | `Priya Raman` | `full_name` |
| email | `Work email` | `priya@company.com` | `email` |
| text | `Company or team` | `Northwind Systems` | `company` |
| select | `People who need environments` | — | `team_size` |
| chips | `What are you here for?` | — | `intent` |
| text | `Apps you expect to run` | `ERPNext v15, Frappe HR, two custom apps` | `expected_apps` |
| textarea | `Anything we should know — optional` | `We onboard two interns a month and lose a morning each time.` | `use_case` |
| checkbox | `I understand access is granted manually and my request may be declined.` | — | `consented` |

Select options `[TEMPLATE]`, must match the `team_size` Select exactly:
`1 — just me`, `2–5`, `6–15`, `16 or more`.
Chip options `[TEMPLATE]`, must match the `intent` Select exactly:
`Hosted account`, `Setup on my server`, `Just evaluating`, `Agent / automation`.

Pending-state mono block, rendered from the endpoint response (`[TEMPLATE]` layout,
dynamic values):

```
request  {{ reference }}
status   pending manual review
next     email to {{ email }}
```

### 1.4 `/login` — Log in

Section order: `form` → `after_login_panel` → `footer`.

| Key | Seed | Kind |
|---|---|---|
| `login.title` | `Log in` | Desk `login_title` |
| `login.body` | `Access is granted after review, so accounts only exist once we have approved a request.` | Desk `login_body` |
| `login.oauth_label` | `Continue with GitHub` | Desk `login_oauth_label` |
| `login.divider_label` | `or email` | Desk `login_divider_label` |
| `login.remember_label` | `Keep me signed in on this device` | Desk `login_remember_label` |
| `login.submit_label` | `Log in` | Desk `login_submit_label` |
| `login.signup_prompt` | `No account yet? Request access — approved by hand, usually inside a business day. Self-hosting needs no account at all.` | Desk `login_signup_prompt` (Text Editor) |
| `login.panel_eyebrow` | `After you log in` | Desk `login_panel_eyebrow` |
| `login.panel_title` | `A console, a credit balance, and one button that matters.` | Desk `login_panel_title` |

Field labels `Email`, `Password`, `Forgot?` and placeholders `priya@company.com`,
`••••••••••` are `[TEMPLATE]` — they are wired to Frappe's `login.js` by element id.

Session mock in the right panel — `[TEMPLATE]`:

```
session · benchpress
✓ session opened · priya@northwind
✓ 4 instances running · 1,342 credits
✓ wireguard peer up · 10.13.13.2
$ bench --site erpnext-demo console
```

> The `Continue with GitHub` button is **rendered but deliberately not wired** — see §4.3.

### 1.5 `/about` — About

Section order: `hero` → `situation` → `two-days` → `is-is-not` → `stats` → `principles` →
`timeline` → `cta` → `trademark` → `footer`.

Every string here is Desk-configurable. This page is the heart of the site.

| Key | Seed | Kind |
|---|---|---|
| `about.eyebrow` | `About` | Desk `eyebrow` |
| `about.title` | `A developer joins on Monday. By 9:15 they are working on the client's actual project.` | Desk `title` |
| `about.lede` | `That sentence is the whole reason Benchpress exists. Not "installing bench is hard" — Frappe already has good tooling for creating a bench and installing apps, and if that were our problem we would have simply used it. Our problem started <i>after</i> the bench existed: every person who joined, and every client they moved between, needed their own working environment, and somebody senior had to build it by hand.` | Desk `lede` (Text Editor) |
| `about.situation.eyebrow` | `The situation we kept living in` | Desk `situation_eyebrow` |
| `about.situation.body` | two paragraphs, below | Desk `situation_body` (Text Editor) |
| `about.days.without_title` | `Monday, without Benchpress` | Desk `days_without_title` |
| `about.days.with_title` | `Monday, with Benchpress` | Desk `days_with_title` |
| `about.days.entries[]` | ten rows | Desk `day_entries` (child) |
| `about.days.closing` | closing paragraph, below | Desk `days_closing` (Text Editor) |
| `about.contrast.title` | `So what is it, exactly — and what is it not?` | Desk `contrast_title` |
| `about.contrast.lede` | `The honest one-liner: Benchpress is an <b>environment-handout system for teams</b>. Bench creation is a step inside it, not the point of it.` | Desk `contrast_lede` (Text Editor) |
| `about.contrast.rows[]` | five rows | Desk `contrast_rows` (child) |
| `about.contrast.closing` | `It is open source under AGPL-3.0, because a development tool you cannot read is a development tool you cannot trust. Run it on your own server for free, forever. When you would rather not run a server, we host it — the same code, with billing attached.` | Desk `contrast_closing` (Text Editor) |
| `about.stats[]` | four rows | Desk `stats` (child) |
| `about.principles.title` | `What we hold to` | Desk `principles_title` |
| `about.principles[]` | four rows | Desk `principles` (child) |
| `about.timeline.title` | `How it got here` | Desk `timeline_title` |
| `about.timeline[]` | four rows | Desk `timeline` (child) |
| `about.cta.title` | `Want the hosted version?` | Desk `cta_title` |
| `about.cta.body` | `Requests are read by a person, not a queue. Tell us what you plan to run.` | Desk `cta_body` |
| `about.cta.label` | `Request access` | Desk `cta_label` |
| `about.cta.url` | `/signup` | Desk `cta_url` |
| `about.trademark` | `Frappe, ERPNext, Frappe HR, Frappe CRM, Helpdesk and Frappe Learning are trademarks of Frappe Technologies Pvt. Ltd., used here only to name the software each template installs. Benchpress is an independent project, not affiliated with, endorsed by or sponsored by Frappe Technologies.` | Desk `trademark` |

`about.situation.body` seed (two paragraphs):

> Say you run a 20-person company with four clients — **A, B, C and D**. Each one is a
> different world: a different Frappe version, a different set of apps, different
> customisations, different data. You hire a developer to work on client B. On their first
> day they need *client B's* environment — not a generic bench, not a copy of someone's
> laptop. The right version, the right apps, the right data, running and reachable.
>
> Somebody has to build that. In practice it is your most experienced developer, and it
> costs them half a day of setup calls, missing branches, port clashes and "works on mine".
> Multiply that by every joiner, every client switch and every intern who needs a sandbox
> for two weeks.

`about.days.closing` seed:

> You — the company — host Benchpress once and save a Lab template per client. The new
> joiner logs in, clicks **Client B**, and about a minute later they have a running site, a
> browser VS Code window attached to the container, and an address on the company's private
> network. Nobody senior was interrupted. Nothing was installed on their laptop.

`about.days.entries[]` seed (`column`, `time_label`, `text`):

*column = `Without BenchPress`*

1. `09:00` / `New joiner arrives. Nobody has an environment for client B ready.`
2. `09:20` / `A senior developer stops their own work to set one up.`
3. `11:30` / `Wrong Frappe version, a branch that no longer exists, a port already in use.`
4. `14:00` / `Something runs locally. It does not match what the client is on.`
5. `Day 2` / `The joiner is still reading setup notes instead of the client's code.`

*column = `With BenchPress`*

1. `09:00` / `New joiner logs in and sees the labs their team owns.`
2. `09:01` / `They click Client B — the template already pins the version, apps and data.`
3. `09:03` / `Site is live. Browser VS Code opens on the same container.`
4. `09:15` / `They are reading client B's actual code, on an environment that matches production.`
5. `Later` / `Moving them to client D is another click, not another afternoon.`

`about.contrast.rows[]` seed (`not_text`, `is_text`):

1. `Not a nicer way to run bench commands on your machine.` / `A place your team keeps ready-made environments, one per client or project.`
2. `Not something each developer installs and maintains locally.` / `One install, by you, on one server. Everyone else just clicks.`
3. `Not a hosting or production platform for client sites.` / `Development and demo environments — disposable on purpose, removed when the work is done.`
4. `Not a laptop-dependent setup that drifts per person.` / `Everyone on a project gets the identical container, so 'works on mine' stops being a sentence.`
5. `Not open to the internet with ports and proxies to babysit.` / `Every environment answers on your private WireGuard network, one key per device.`

`about.stats[]` seed (`value`, `label`):

1. `~90s` / `From a new joiner's click to a working site and IDE`
2. `1 install` / `On one server, for the whole team — not per laptop`
3. `0` / `Credits charged for a build that fails`
4. `AGPL-3.0` / `Licensed, self-hostable, no telemetry`

`about.principles[]` seed (`icon`, `title`, `body`):

1. `eye` / `Show the machine` / `Every bench command, every log line, every elapsed second is visible. A tool that hides the terminal cannot be debugged.`
2. `shield` / `Private by default` / `Environments answer on a WireGuard mesh, not the public internet. Access is a key per device, revocable in a click.`
3. `credit-card` / `Meter honestly` / `Deploys are free, stopped instances are free, failed builds are free. Everything else lands in a ledger you can read.`
4. `github` / `Stay forkable` / `The hosted product is this repository with billing attached. If we ever stop being useful, you keep running it yourself.`

`about.timeline[]` seed (`period`, `title`, `body`):

1. `2024` / `An internal script` / `A shell script that stood up a bench container for whoever joined next. It broke often and only one person could fix it.`
2. `2025` / `A Frappe app` / `The script became a control plane with a real object model — Lab templates, Bench Instances, Bench Sites, deploy history.`
3. `2025` / `WireGuard and browser VS Code` / `Access stopped meaning SSH keys and open ports. Every environment got a mesh address and code-server on :8443.`
4. `2026` / `Open sourced, then hosted` / `Published under AGPL-3.0. The hosted build followed for teams who wanted the tool without the server.`

### 1.6 `/contact` — Contact

Section order: `hero` → `channels` → `form` + `sidebar` → `footer`.

Like About, everything here is Desk-configurable.

| Key | Seed | Kind |
|---|---|---|
| `contact.eyebrow` | `Contact` | Desk `eyebrow` |
| `contact.title` | `Talk to the people who wrote it.` | Desk `title` |
| `contact.body` | `No chatbot, no ticket robot. Pick whichever door fits — a bug goes to GitHub, a quote goes to the form, an urgent production question goes to email.` | Desk `intro_body` |
| `contact.channels[]` | three rows | Desk `channels` (child) |
| `contact.form.title` | `Send a message` | Desk `form_title` |
| `contact.form.subtitle` | `We answer every message within one business day.` | Desk `form_subtitle` |
| `contact.form.topic_label` | `Topic` | Desk `form_topic_label` |
| `contact.form.topics[]` | four rows | Desk `topics` (child) |
| `contact.form.submit_label` | `Send message` | Desk `form_submit_label` |
| `contact.form.success_title` | `Message sent` | Desk `form_success_title` |
| `contact.form.success_body` | `Thanks — it is in front of a person, not a queue. You will hear back within one business day.` | Desk `form_success_body` |
| `contact.sla.title` | `Response times` | Desk `sla_title` |
| `contact.sla[]` | three rows | Desk `response_times` (child) |
| `contact.selfhost.title` | `Self-hosting a question` | Desk `selfhost_title` |
| `contact.selfhost.body` | `Self-hosted installs get community support on GitHub — issues and discussions, answered in public so the next person finds the answer. Paid support with a response window is one of the four things we sell.` | Desk `selfhost_body` (Text Editor) |
| `contact.selfhost.links` | `github.com/Venkateshvenki404224/benchpress` / `hello@benchpress.dev` | Desk `selfhost_links` (Small Text, one per line) |
| `contact.notify_email` | `hello@benchpress.dev` | Desk `notify_email` |

Field labels `Name`, `Email`, `Message` and placeholders `Ravi Kumar`, `ravi@company.com`,
`We run ERPNext for 40 people and want Benchpress installed on our own server.` are
`[TEMPLATE]` — bound to `Contact Message` fields.

`contact.channels[]` seed (`icon`, `title`, `body`, `meta`, `url`):

1. `mail` / `Email us` / `Sales, hosted access, quotes for setup or app work. A human replies.` / `hello@benchpress.dev` / `mailto:hello@benchpress.dev`
2. `github` / `GitHub issues` / `Bugs, feature requests and self-hosting questions, answered in public.` / `/benchpress/issues` / `https://github.com/Venkateshvenki404224/benchpress/issues`
3. `calendar` / `Book 20 minutes` / `Bring your server details and what breaks today. We will say plainly whether you need us.` / `cal / benchpress` / *(empty)*

`contact.form.topics[]` seed (`label`, `route_to_email`, `is_default`):

1. `Hosted access` / *(empty)* / `1`
2. `Setup or migration` / *(empty)* / `0`
3. `Custom app work` / *(empty)* / `0`
4. `Bug or issue` / *(empty)* / `0`

`contact.sla[]` seed (`subject`, `window`):

1. `Hosted access requests` / `1 business day`
2. `Sales and quotes` / `1 business day`
3. `GitHub issues` / `2–3 days`

### 1.7 Non-landing footer

The four non-landing pages use a compact footer, `[TEMPLATE]` layout, Desk copy:
`© 2026 Benchpress. AGPL-3.0 licensed.` (`Landing Page Settings.footer_copyright`) and
`Not affiliated with Frappe Technologies.` (a separate field
`Landing Page Settings.footer_trademark_short`).

---

## 2. Data model

All new doctypes live in module **Benchpress** at
`benchpress/benchpress/doctype/<snake_case>/`. Child tables carry `"istable": 1` and no
permissions block. Normal and Single doctypes carry the same two-role permission block as
`Waitlist Entry`: **System Manager** and **BenchPress Admin**, full CRUD.

Field spec format: `fieldname` / `Fieldtype` / `Label` / reqd / default.

### 2.1 `Waitlist Entry` — EXTENDED (Normal)

Do **not** change: `"autoname": "field:email"` (deliberate anti-enumeration — a duplicate
signup is a primary-key conflict, never a lookup), `approve()`, `invite_user()`,
`create_user()`, `normalise_email()`.

Existing fields kept as-is: `email`, `full_name`, `company`, `column_break_identity`,
`status`, `approved_on`, `invite_sent_on`, `context_section`, `use_case`.

**New fields**, inserted into `field_order` as shown:

| fieldname | Fieldtype | Label | reqd | default |
|---|---|---|---|---|
| `team_size` | Select | People Who Need Environments | 0 | `1 — just me` |
| `intent` | Select | What They Are Here For | 0 | `Hosted account` |
| `expected_apps` | Data | Apps They Expect To Run | 0 | — |
| `consented` | Check | Acknowledged Manual Review | 0 | `0` |
| `source` | Select | Source | 0 | `Signup Page` |
| `rejected_on` | Datetime | Rejected On | 0 | — |
| `rejection_reason` | Small Text | Rejection Reason | 0 | — |

Options:

- `team_size`: `1 — just me\n2–5\n6–15\n16 or more`
- `intent`: `Hosted account\nSetup on my server\nJust evaluating\nAgent / automation`
- `source`: `Signup Page\nLanding Waitlist\nDesk\nImport` — `read_only: 1`

`field_order` (full, in order):

```
email, full_name, company, column_break_identity, status, source,
approved_on, rejected_on, invite_sent_on,
request_section, team_size, intent, expected_apps, consented,
context_section, use_case, rejection_reason
```

Add `request_section` / Section Break / label `Request`. `expected_apps` gets
`in_list_view: 0`; `intent` gets `in_standard_filter: 1`.

**Column widths for clipping** (`waitlist.clip`): `full_name`, `company`, `expected_apps`
→ `DATA_LIMIT` (140). `use_case` → `TEXT_LIMIT` (1000).

**Controller additions** (`waitlist_entry.py`):

```python
REFERENCE_PREFIX = "REQ"

def onload(self):
    self.set_onload("reference", self.request_reference())

def request_reference(self) -> str:
    """A short, stable handle for this request. Derived on read, never stored."""
    return derive_reference(self.name)

def reject(self, reason: str = "") -> None:
    """The other half of `approve` — records the decision so the notice can name it."""
```

```python
def derive_reference(email: str) -> str:
    """`REQ-XXXX-XXXX` from the row name, keyed so a stranger cannot recompute it."""
    key = get_encryption_key().encode()
    digest = hmac.new(key, normalise_email(email).encode(), hashlib.sha256).hexdigest()
    return f"{REFERENCE_PREFIX}-{digest[:4].upper()}-{digest[4:8].upper()}"
```

`get_encryption_key` is `frappe.utils.password.get_encryption_key` — stable for the life of
the site, already present in `site_config.json`.

**Why this shape, and not the mockup's `REQ-26-118`:**

- **Derived, not a naming series.** The doctype's name must stay the email. A second
  autoname or a counter column would create a second identity for the same row and a
  monotonic counter leaks the size of the waitlist.
- **No year, no counter.** `derive_reference` is a pure function of the email, so
  `waitlist.join` returns the identical reference whether the row was just inserted or
  already existed. Any component derived from `creation` would make the response differ
  between a new and a repeat address — a membership oracle, which is exactly what
  `autoname: field:email` + `insert_once` exist to prevent.
- **Keyed, so it is not guessable.** A plain `sha256(email)` could be recomputed by anyone
  holding a candidate address, turning a support reference into a confirmation channel.
  The HMAC key is the site's `encryption_key`.
- **Non-secret.** The value discloses nothing on its own: it is safe to print in an email,
  quote in a support thread, and show in Desk. It is a handle, not a credential — never
  accept it as authentication for anything.
- The mockup string `REQ-26-118` is a static mock. Match the **format** `REQ-XXXX-XXXX`.

### 2.2 `Landing Page Settings` (Single)

Fieldnames as listed against every `Desk <fieldname>` in §1.2. Types:

| Group | fieldname | Fieldtype | reqd | default |
|---|---|---|---|---|
| Sections | `show_agents` | Check | 0 | `1` |
| Sections | `show_testimonials` | Check | 0 | `1` |
| Hero | `hero_badge_text` | Data | 0 | seed |
| Hero | `hero_badge_version` | Data | 0 | seed |
| Hero | `hero_headline` | Small Text | 1 | seed |
| Hero | `hero_headline_accent` | Data | 0 | seed |
| Hero | `hero_subhead` | Small Text | 0 | seed |
| Hero | `hero_cta_primary_label` | Data | 0 | seed |
| Hero | `hero_cta_primary_url` | Data | 0 | `/signup` |
| Hero | `hero_cta_secondary_label` | Data | 0 | seed |
| Hero | `hero_cta_secondary_url` | Data | 0 | `#paths` |
| Hero | `hero_assurances` | Table → `Landing Hero Assurance` | 0 | seed |
| Templates | `templates_eyebrow` | Data | 0 | `Templates` |
| Templates | `template_cards` | Table → `Landing Template Card` | 0 | seed |
| Paths | `paths_hosted_eyebrow` | Data | 0 | seed |
| Paths | `paths_hosted_badge` | Data | 0 | seed |
| Paths | `paths_hosted_title` | Small Text | 0 | seed |
| Paths | `paths_hosted_body` | Small Text | 0 | seed |
| Paths | `paths_hosted_cta_label` | Data | 0 | seed |
| Paths | `paths_hosted_cta_url` | Data | 0 | `/signup` |
| Paths | `paths_hosted_cta2_label` | Data | 0 | seed |
| Paths | `paths_hosted_cta2_url` | Data | 0 | `/contact` |
| Paths | `paths_self_eyebrow` | Data | 0 | seed |
| Paths | `paths_self_title` | Small Text | 0 | seed |
| Paths | `paths_self_body` | Small Text | 0 | seed |
| Paths | `paths_self_terminal` | Code | 0 | seed |
| Paths | `paths_self_cta_label` | Data | 0 | seed |
| Paths | `paths_self_cta_url` | Data | 0 | repo URL |
| Paths | `paths_self_cta2_label` | Data | 0 | seed |
| Paths | `paths_self_cta2_url` | Data | 0 | `#services` |
| Paths | `paths_footnote` | Small Text | 0 | seed |
| Paths | `path_points` | Table → `Landing Path Point` | 0 | seed |
| Bento | `bento_eyebrow` | Data | 0 | seed |
| Bento | `bento_title` | Small Text | 0 | seed |
| Bento | `bento_body` | Small Text | 0 | seed |
| Bento | `feature_cards` | Table → `Landing Feature Card` | 0 | seed |
| Pipeline | `pipeline_eyebrow` | Data | 0 | seed |
| Pipeline | `pipeline_title` | Small Text | 0 | seed |
| Pipeline | `pipeline_body` | Small Text | 0 | seed |
| Pipeline | `pipeline_default_phase` | Data | 0 | `site` |
| Pipeline | `pipeline_phases` | Table → `Landing Pipeline Phase` | 0 | seed |
| Pipeline | `pipeline_steps` | Table → `Landing Pipeline Step` | 0 | seed |
| Pipeline | `pipeline_failure_title` | Data | 0 | seed |
| Pipeline | `pipeline_failure_body` | Small Text | 0 | seed |
| Console | `console_eyebrow` | Data | 0 | seed |
| Console | `console_title` | Small Text | 0 | seed |
| Console | `console_body` | Small Text | 0 | seed |
| Console | `console_callouts` | Table → `Landing Console Callout` | 0 | seed |
| Agents | `agents_eyebrow` | Data | 0 | seed |
| Agents | `agents_title` | Small Text | 0 | seed |
| Agents | `agents_body` | Small Text | 0 | seed |
| Agents | `agents_badge` | Data | 0 | `202 accepted` |
| Agents | `agents_footnote` | Small Text | 0 | seed |
| Agents | `agent_points` | Table → `Landing Agent Point` | 0 | seed |
| Agents | `agent_api_examples` | Table → `Landing Agent Api Example` | 0 | seed |
| Compare | `compare_eyebrow` | Data | 0 | seed |
| Compare | `compare_title` | Small Text | 0 | seed |
| Compare | `compare_col_manual` | Data | 0 | `Manual bench` |
| Compare | `compare_col_bp` | Data | 0 | `Benchpress` |
| Compare | `compare_col_bp_badge` | Data | 0 | `One click` |
| Compare | `comparison_rows` | Table → `Landing Comparison Row` | 0 | seed |
| Services | `services_eyebrow` | Data | 0 | seed |
| Services | `services_title` | Small Text | 0 | seed |
| Services | `services_body` | Small Text | 0 | seed |
| Services | `service_cards` | Table → `Landing Service Card` | 0 | seed |
| Services | `services_cta_title` | Data | 0 | seed |
| Services | `services_cta_body` | Small Text | 0 | seed |
| Services | `services_cta_label` | Data | 0 | seed |
| Services | `services_cta_url` | Data | 0 | `/contact` |
| Testimonials | `testimonials_eyebrow` | Data | 0 | `In use` |
| Testimonials | `testimonials_disclaimer` | Data | 0 | seed |
| Testimonials | `testimonials` | Table → `Landing Testimonial` | 0 | seed |
| Testimonials | `logo_strip` | Table → `Landing Logo` | 0 | *(empty)* |
| FAQ | `faq_title` | Data | 0 | `Questions` |
| FAQ | `faq_items` | Table → `Landing Faq Item` | 0 | seed |
| CTA | `cta_title` | Small Text | 0 | seed |
| CTA | `cta_primary_label` | Data | 0 | seed |
| CTA | `cta_primary_url` | Data | 0 | `/signup` |
| CTA | `cta_secondary_label` | Data | 0 | seed |
| CTA | `cta_secondary_url` | Data | 0 | repo URL |
| CTA | `cta_footnote` | Small Text | 0 | seed |
| Chrome | `nav_items` | Table → `Landing Nav Item` | 0 | seed |
| Chrome | `footer_tagline` | Small Text | 0 | seed |
| Chrome | `footer_links` | Table → `Landing Footer Link` | 0 | seed |
| Chrome | `footer_copyright` | Data | 0 | seed |
| Chrome | `footer_trademark` | Small Text | 0 | seed |
| Chrome | `footer_trademark_short` | Data | 0 | `Not affiliated with Frappe Technologies.` |
| SEO | `meta_title` | Data | 0 | `Benchpress — a Frappe environment in one click` |
| SEO | `meta_description` | Small Text | 0 | `hero_subhead` seed |
| SEO | `og_image` | Attach Image | 0 | — |

Every group above is preceded by a Section Break named `<group>_section` and split with
Column Breaks where a group has more than eight fields.

### 2.3 Landing child tables

All `istable: 1`, `editable_grid: 1`, module `Benchpress`.

| Doctype | Fields |
|---|---|
| `Landing Nav Item` | `label` Data reqd; `anchor` Data reqd; `is_cta` Check default `0` |
| `Landing Hero Assurance` | `label` Data reqd |
| `Landing Template Card` | `app_name` Data reqd; `build_time` Data; `icon` Attach Image |
| `Landing Path Point` | `path` Select `Hosted\nSelf-hosted` reqd default `Hosted`; `point` Data reqd |
| `Landing Feature Card` | `title` Data reqd; `body` Small Text; `icon` Data default `box`; `span` Select `Standard\nWide` default `Standard` |
| `Landing Pipeline Phase` | `phase_key` Data reqd; `label` Data reqd; `step_range` Data; `summary` Small Text; `timing` Small Text; `plane_nodes` Data; `plane_chips` Data |
| `Landing Pipeline Step` | `phase_key` Data reqd; `step_number` Int reqd; `title` Data reqd; `detail` Small Text; `command` Code |
| `Landing Console Callout` | `title` Data reqd; `body` Small Text; `icon` Data |
| `Landing Agent Point` | `icon` Data; `text` Data reqd |
| `Landing Agent Api Example` | `tab_label` Data reqd; `code` Code reqd |
| `Landing Comparison Row` | `aspect` Data reqd; `manual` Data; `benchpress` Data |
| `Landing Service Card` | `number` Data; `icon` Data; `title` Data reqd; `body` Small Text; `meta` Data |
| `Landing Testimonial` | `quote` Small Text reqd; `person_name` Data; `person_role` Data; `is_placeholder` Check default `0` |
| `Landing Logo` | `logo` Attach Image reqd; `alt_text` Data |
| `Landing Faq Item` | `question` Data reqd; `answer` Small Text reqd; `default_open` Check default `0` |
| `Landing Footer Link` | `column_heading` Data reqd; `label` Data reqd; `url` Data reqd |

`plane_nodes` / `plane_chips` are comma-separated key lists (`device,control`) resolved
against the fixed diagram nodes `device` `control` `host` `mesh` and chips `api` `queue`
`ledger`. They are `Data` and not a child table because the diagram itself is `[TEMPLATE]`
— an operator toggles which boxes light up per phase, never invents a new box.

`Landing Pipeline Step.phase_key` is a plain `Data` because Frappe has no nested child
tables. `LandingPageSettings.validate()` throws when a step names a `phase_key` no phase
row declares, so the mismatch is caught at save rather than silently dropping the step.

### 2.4 `About Page Settings` (Single)

| fieldname | Fieldtype | Label | reqd | default |
|---|---|---|---|---|
| `eyebrow` | Data | Eyebrow | 0 | `About` |
| `title` | Small Text | Title | 1 | seed |
| `lede` | Text Editor | Lede | 0 | seed |
| `situation_eyebrow` | Data | Situation Eyebrow | 0 | seed |
| `situation_body` | Text Editor | Situation Body | 0 | seed |
| `days_without_title` | Data | Without Column Title | 0 | seed |
| `days_with_title` | Data | With Column Title | 0 | seed |
| `day_entries` | Table → `About Day Entry` | Day Entries | 0 | seed |
| `days_closing` | Text Editor | Days Closing | 0 | seed |
| `contrast_title` | Small Text | Contrast Title | 0 | seed |
| `contrast_lede` | Text Editor | Contrast Lede | 0 | seed |
| `contrast_rows` | Table → `About Contrast Row` | Contrast Rows | 0 | seed |
| `contrast_closing` | Text Editor | Contrast Closing | 0 | seed |
| `stats` | Table → `About Stat` | Stats | 0 | seed |
| `principles_title` | Data | Principles Title | 0 | `What we hold to` |
| `principles` | Table → `About Principle` | Principles | 0 | seed |
| `timeline_title` | Data | Timeline Title | 0 | `How it got here` |
| `timeline` | Table → `About Timeline Entry` | Timeline | 0 | seed |
| `cta_title` | Data | CTA Title | 0 | seed |
| `cta_body` | Small Text | CTA Body | 0 | seed |
| `cta_label` | Data | CTA Label | 0 | `Request access` |
| `cta_url` | Data | CTA URL | 0 | `/signup` |
| `trademark` | Small Text | Trademark | 0 | seed |
| `meta_title` | Data | Meta Title | 0 | `About Benchpress` |
| `meta_description` | Small Text | Meta Description | 0 | seed |
| `og_image` | Attach Image | OG Image | 0 | — |

Child tables:

| Doctype | Fields |
|---|---|
| `About Day Entry` | `column` Select `Without BenchPress\nWith BenchPress` reqd default `Without BenchPress`; `time_label` Data reqd; `text` Small Text reqd |
| `About Contrast Row` | `not_text` Small Text reqd; `is_text` Small Text reqd |
| `About Stat` | `value` Data reqd; `label` Small Text reqd |
| `About Principle` | `icon` Data; `title` Data reqd; `body` Small Text |
| `About Timeline Entry` | `period` Data reqd; `title` Data reqd; `body` Small Text |

### 2.5 `Contact Page Settings` (Single)

| fieldname | Fieldtype | Label | reqd | default |
|---|---|---|---|---|
| `eyebrow` | Data | Eyebrow | 0 | `Contact` |
| `title` | Small Text | Title | 1 | seed |
| `intro_body` | Small Text | Intro Body | 0 | seed |
| `channels` | Table → `Contact Channel` | Channels | 0 | seed |
| `form_title` | Data | Form Title | 0 | `Send a message` |
| `form_subtitle` | Small Text | Form Subtitle | 0 | seed |
| `form_topic_label` | Data | Topic Label | 0 | `Topic` |
| `topics` | Table → `Contact Topic` | Topics | 0 | seed |
| `form_submit_label` | Data | Submit Label | 0 | `Send message` |
| `form_success_title` | Data | Success Title | 0 | `Message sent` |
| `form_success_body` | Small Text | Success Body | 0 | seed |
| `sla_title` | Data | SLA Title | 0 | `Response times` |
| `response_times` | Table → `Contact Response Time` | Response Times | 0 | seed |
| `selfhost_title` | Data | Self-host Title | 0 | seed |
| `selfhost_body` | Text Editor | Self-host Body | 0 | seed |
| `selfhost_links` | Small Text | Self-host Links | 0 | seed |
| `notify_email` | Data | Notify Email | 0 | `hello@benchpress.dev` |
| `acknowledge_sender` | Check | Send Acknowledgement To Sender | 0 | `1` |
| `meta_title` | Data | Meta Title | 0 | `Contact Benchpress` |
| `meta_description` | Small Text | Meta Description | 0 | seed |
| `og_image` | Attach Image | OG Image | 0 | — |

Child tables:

| Doctype | Fields |
|---|---|
| `Contact Channel` | `icon` Data; `title` Data reqd; `body` Small Text; `meta` Data; `url` Data |
| `Contact Topic` | `label` Data reqd; `route_to_email` Data; `is_default` Check default `0` |
| `Contact Response Time` | `subject` Data reqd; `window` Data reqd |

`ContactPageSettings.validate()` throws when more than one topic sets `is_default`.
`notify_email` is the fallback when a topic has no `route_to_email`.

### 2.6 `Contact Message` (Normal)

`"autoname": "hash"` — the row is written by a guest, so nothing about it may be
enumerable and nothing user-supplied may become the key.

| fieldname | Fieldtype | Label | reqd | default |
|---|---|---|---|---|
| `sender_name` | Data | Name | 1 | — |
| `email` | Data (`options: Email`) | Email | 1 | — |
| `topic` | Data | Topic | 0 | — |
| `column_break_identity` | Column Break | — | — | — |
| `status` | Select `New\nAnswered\nSpam` | Status | 1 | `New` |
| `answered_on` | Datetime (read_only) | Answered On | 0 | — |
| `answered_by` | Link `User` (read_only) | Answered By | 0 | — |
| `message_section` | Section Break | Message | — | — |
| `message` | Text | Message | 1 | — |

`sort_field: creation`, `sort_order: DESC`, `track_changes: 1`.
`in_list_view`: `sender_name`, `email`, `topic`, `status`.
`in_standard_filter`: `status`, `topic`.

No IP address, no user agent: rate limiting already bounds abuse and neither field would
be read by a human. `topic` is `Data` and not a `Link`, because `Contact Topic` is a child
table; the controller validates it against the configured labels and blanks anything else.

**Field-level clipping** (server-side, before insert): `sender_name` 140, `email` 140,
`topic` 60, `message` 4000.

---

## 3. Endpoints

The app's guest inventory grows from **two to three**. Every other endpoint below is
role-guarded.

### 3.1 `benchpress.waitlist.join` — EXTENDED, `allow_guest=True`

```python
@frappe.whitelist(allow_guest=True)  # nosemgrep -- reviewed, see the note above
@rate_limit(key="email", limit=JOINS_PER_HOUR, seconds=60 * 60, ip_based=True)
def join(
	email: str,
	full_name: str | None = None,
	company: str | None = None,
	use_case: str | None = None,
	team_size: str | None = None,
	intent: str | None = None,
	expected_apps: str | None = None,
	consented: int | str | None = None,
	source: str | None = None,
) -> dict:
```

Rules, all of which already hold and must keep holding:

- `require_waitlist_open()` first, before validation and before any write.
- `clip()` every free-text argument to its column width.
- `team_size`, `intent` and `source` are **matched against the Select options** and
  silently replaced with the field default when they do not match. A guest-supplied string
  never reaches a Select column unchecked.
- `consented` is coerced with `cint`. It is recorded, not enforced: the browser enforces
  it, and refusing here would tell a scripted caller which shape the form wants.
- `insert_once()` inside a savepoint, swallowing `frappe.DuplicateEntryError`.
- **Return value changes** — one new key:

```python
return {
    "joined": True,
    "reference": derive_reference(email),
    "message": _("You're on the list. We'll email you when a slot opens."),
}
```

`reference` is derived from the argument, not from a fetched row, so the response is
byte-identical for a first-time and a repeat address. Do not read the row back.

Email side effects fire from `insert_once`'s success path only (§6), so a duplicate
submission never re-mails anyone.

Justification comment stays as written in `waitlist.py` today, extended with one sentence:
"It now also carries the signup form's structured fields; every one of them is clipped or
matched against its Select options before it reaches the database."

### 3.2 `benchpress.contact.submit` — NEW, `allow_guest=True`

```python
DOCTYPE = "Contact Message"
MESSAGES_PER_HOUR = 3
NAME_LIMIT = 140
TOPIC_LIMIT = 60
MESSAGE_LIMIT = 4000


# Deliberately open to Guest: this is the contact form's only endpoint, and a contact form
# that needs an account is not a contact form. It writes one row of clipped text, stores no
# address or fingerprint of the sender beyond what they typed, answers identically for every
# caller, and is rate limited per IP and address like the waitlist.
# `test_api_authorization` asserts this is one of the app's three `allow_guest` methods.
@frappe.whitelist(allow_guest=True)  # nosemgrep -- reviewed, see the note above
@rate_limit(key="email", limit=MESSAGES_PER_HOUR, seconds=60 * 60, ip_based=True)
def submit(name: str, email: str, message: str, topic: str | None = None) -> dict:
	"""Record one contact message. Always answers the same way."""
```

- `email` goes through `normalise_email` (raises `ValidationError` on a bad address — that
  is a form error, not an oracle).
- `topic` is matched against the configured `Contact Topic` labels; anything else becomes
  the default topic.
- `message` is required; an empty message throws a plain validation error.
- Insert with `ignore_permissions=True`; **no** savepoint/duplicate swallow — repeat
  contact messages are legitimate and each one gets its own row.
- Returns `{"sent": True, "message": <Contact Page Settings.form_success_body>}`.
- Fires the two emails in §6.4.

### 3.3 `benchpress.contact.mark_answered` — admin

```python
@frappe.whitelist()
def mark_answered(messages: str | list) -> dict:
	"""Desk bulk action: close the selected messages. Admins only."""
	require_admin()
```

Sets `status = "Answered"`, `answered_on = now_datetime()`, `answered_by =
frappe.session.user` for each name in `frappe.parse_json(messages)`. Returns
`{"answered": <count>}`.

### 3.4 `benchpress.waitlist.reject` — NEW, admin

```python
@frappe.whitelist()
def reject(entries: str | list, reason: str = "") -> dict:
	"""Decline the selected entries and tell each one. Desk bulk action, admins only."""
	require_admin()
```

Per entry: `WaitlistEntry.reject(reason)` sets `status = "Rejected"`,
`rejected_on = now_datetime()`, `rejection_reason = clip(reason, TEXT_LIMIT)`, saves with
`ignore_permissions=True`, and sends the decline email (§6.3). Returns
`{"rejected": <count>}`.

`WaitlistEntry.validate()` must be extended to clear `rejected_on` when status is not
`Rejected`, mirroring the existing `approved_on` rule.

### 3.5 Unchanged

`benchpress.waitlist.approve`, `benchpress.waitlist.notify_of_signup`,
`benchpress.signup.sign_up`. `approve()` on the document is unchanged; the new
approval email hangs off it (§6.2).

### 3.6 No read endpoints

The five pages render server-side. There is **no** whitelisted method that returns
`Landing Page Settings`, `About Page Settings` or `Contact Page Settings`. Do not add one.

### 3.7 `test_api_authorization.py` — exactly how it must change

File: `benchpress/tests/test_api_authorization.py`.

1. **Rename** `test_only_the_two_signup_doors_are_open_to_guests` →
   `test_only_the_three_public_form_doors_are_open_to_guests`.
2. **Change the asserted set** to:

```python
self.assertEqual(
    _guest_endpoints(),
    {
        "benchpress.waitlist.join",
        "benchpress.signup.sign_up",
        "benchpress.contact.submit",
    },
)
```

3. **Rewrite the docstring** to argue the third door, in the same voice as the existing
   one: three methods have been argued for — `waitlist.join`, which the access-request
   form posts to; `signup.sign_up`, which replaces a method Frappe already exposes to
   guests and only narrows it; and `contact.submit`, which is the contact form's only
   endpoint and writes one clipped row. Anything else appearing in this inventory means
   somebody opened an endpoint to the internet without saying so.
4. **Add** `from benchpress import api, contact, waitlist` to the imports.
5. **Add a positive control**, next to `test_guest_can_reach_the_waitlist`:

```python
def test_guest_can_reach_the_contact_form(self):
    frappe.set_user("Guest")
    self.addCleanup(_delete_contact_messages, GUEST_CONTACT_EMAIL)
    self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
    frappe.flags.mute_emails = True

    self.assertTrue(contact.submit("Authz Guest", GUEST_CONTACT_EMAIL, "hello")["sent"])
```

with `GUEST_CONTACT_EMAIL = "authz-guest-contact@example.com"` beside
`GUEST_WAITLIST_EMAIL`, and a `_delete_contact_messages(email)` helper alongside
`_delete_waitlist_entry`.

6. **Add three denial tests**:

```python
def test_guest_denied_from_the_contact_admin_endpoints(self):
    frappe.set_user("Guest")
    self.assert_denied(lambda: contact.mark_answered(["nonexistent"]))

def test_guest_denied_from_rejecting_the_waitlist(self):
    frappe.set_user("Guest")
    self.assert_denied(lambda: waitlist.reject([GUEST_WAITLIST_EMAIL]))

def test_non_admin_denied_from_reading_contact_messages(self):
    frappe.set_user(self.user_a)
    self.assertFalse(frappe.has_permission("Contact Message", "read"))
```

7. **Nothing else in the file changes.** `_guest_endpoints()` already walks every module
   in the package, so `benchpress/contact.py` is picked up without touching the helper.

---

## 4. Pages

All five are Jinja `www` pages. Every one:

- lives at `benchpress/www/<name>.html` with a sibling `benchpress/www/<name>.py`;
- sets `no_cache = 1` at module level (theme + form state are per-visitor);
- extends `templates/web.html` and blanks `navbar`, `breadcrumbs`, `sidebar`, `footer`,
  putting the branded chrome inside `page_content`;
- includes `benchpress/templates/includes/public_header.html` and
  `public_footer.html` (owned by another phase — see §7);
- links `/assets/benchpress/css/brand.css` (owned by another phase) from `head_include`,
  with the `?v=` cache-busting token produced the same way `www/home.py.asset_version()`
  produces it today;
- carries `context.mode_default = "dark"`, `context.meta_title`, `context.meta_description`,
  `context.og_image`, `context.repo_url`, `context.contact_email`.

`benchpress/www/<name>.py` reads its Single with `frappe.get_cached_doc(...)` — never
`get_doc` — so a page hit costs no query once warm.

### 4.1 `/` — landing

- Route: `/` (Frappe resolves `/` to `www/index.html`; see §7 for the Website Settings
  `home_page` note).
- Template: `benchpress/www/index.html`
- Controller: `benchpress/www/index.py`
- Context keys: `settings` (`Landing Page Settings` doc), `phases` (list of phase dicts
  each carrying its own `steps` list, grouped by `phase_key` in the controller),
  `footer_columns` (list of `{heading, links}` grouped from `footer_links`),
  `default_phase`, `show_agents`, `show_testimonials`, `repo_url`, `signup_route`.
- `signup_route` is `/signup` while `Credit Settings.waitlist_open` is on, and
  `benchpress.credits.config.SIGNUP_ROUTE` when it is off — one value resolved once, as
  `home.py.start_route()` already does.
- Sections, in order: `hero`, `templates-marquee`, `paths`, `bento`, `pipeline`,
  `console`, `agents`, `compare`, `services`, `testimonials`, `faq`, `cta`, `footer`.

### 4.2 `/signup` — request access

- Template: `benchpress/www/signup.html`
- Controller: `benchpress/www/signup.py`
- Context keys: `settings` (`Signup Page Settings`, folded into `Landing Page Settings`?
  **No** — see below), `waitlist_open`, `signup_route`.

`/signup` copy lives on its own Single, **`Signup Page Settings`**, with the fields listed
in §1.3 and one child table `Signup Step` (`step_number` Int, `title` Data reqd, `body`
Small Text) plus `Signup Pending Link` (`icon` Data, `text` Small Text reqd, `url` Data).

**Redirect rule.** When `credits_enabled()` and **not** `waitlist_open()`, self-serve
signup has replaced the queue, so `get_context` raises `frappe.Redirect` to
`config.SIGNUP_ROUTE` (`/login#signup`). There must never be two live front doors.

Sections, in order: `intro`, `form` **xor** `pending`, `footer`.

The form posts to `benchpress.waitlist.join` with `frappe.call`; on success the page swaps
to the `pending` block client-side and fills `reference` and `email` from the response.
No page reload, no query string carrying an address.

### 4.3 `/login` — log in (shadows Frappe's)

- Template: `benchpress/www/login.html`
- Controller: `benchpress/www/login.py`

**Why it shadows.** `TemplatePage.set_template_path` iterates
`reversed(frappe.get_installed_apps())`, so `benchpress/www/login.html` is found before
`frappe/www/login.html`. Nothing else is needed — no route rule, no `page_renderer`.

**`benchpress/www/login.py` must not reimplement the flow.** It calls Frappe's own
`get_context` and then decorates it:

```python
from frappe.www.login import get_context as frappe_login_context

no_cache = True


def get_context(context):
	frappe_login_context(context)
	context.update(branded_context())
	return context
```

`frappe_login_context` raises `frappe.Redirect` for an already-signed-in visitor and
sanitises `redirect-to`; letting it run keeps both behaviours for free.

**Context keys the branded template MUST reproduce.** Every one is set by
`frappe/www/login.py`; dropping any breaks a real path:

| Key | Why it is load-bearing |
|---|---|
| `provider_logins` | the OAuth buttons; each entry has `name`, `provider_name`, `auth_url`, `icon`. `auth_url` already carries the sanitised `redirect-to`. |
| `social_login` | truthy when at least one provider is configured; gates the whole OAuth block **and** the extra `section.for-email-login` that `login.js` toggles. |
| `disable_signup` | hides the signup affordances. Follows `Credit Settings.waitlist_open` via `CreditSettings.follow_waitlist_switch`, so on an invite-only site this is `1`. |
| `disable_user_pass_login` | hides the email/password body and the Continue button. |
| `ldap_settings` | when `.enabled`, renders `.btn-ldap-login`; `login.js` posts `ldap_settings.method`. |
| `login_with_email_link` | renders the magic-link button and its section. |
| `login_label` | the email field's label — becomes "Email or Mobile or Username" per System Settings. |
| `signup_form_template` | pre-rendered HTML of the signup form; must be emitted verbatim inside `section.for-signup`. |
| `logo`, `app_name`, `title` | chrome. |
| `show_footer_on_login` | `login.js` reads `window.show_footer_on_login`. |
| `no_header`, `hide_login` | keep `templates/web.html` from adding its own login link. |

**DOM contract `login.js` depends on** — reproduce every one of these exactly:

- Sections, all five present even if visually restyled:
  `section.for-login`, `section.for-email-login` (only when `social_login`),
  `section.for-signup` (add `signup-disabled` when `disable_signup`),
  `section.for-forgot`, `section.for-login-with-email-link`.
  `login.js` shows and hides these by class; a missing one makes its hash route a no-op.
- Forms: `form.form-login` (submits `cmd=login`), `form.form-signup`, `form.form-forgot`,
  `form.form-login-with-email-link`. The last three carry class `hide` in markup;
  `login.js` removes it on `frappe.ready`.
- Inputs by **id**: `login_email`, `login_password`, `forgot_email`,
  `login_with_email_link_email`, `signup_fullname`, `signup_email` (the last two come from
  `signup_form_template`).
- Structure per field: an ancestor `.form-group` containing a `p.field-error`, inside a
  `.page-card-body`. `login.show_field_error` walks `#<id>.closest(".form-group")` and
  writes into `.field-error`; `login.reset_sections` clears `.page-card-body.invalid`.
- Error banner: `.login-error-banner` with a `span` inside, per login section.
- Buttons by class: `.btn-login` (type submit inside `.form-login`), `.btn-signup`,
  `.btn-forgot`, `.btn-login-with-email-link`, `.btn-ldap-login`,
  `a.btn-login-option.btn-login-with-email-link`.
- Anchors: `href="#forgot"`, `href="#signup"`, `href="#login"`,
  `href="#login-with-email-link"` — `login.route()` reads `location.hash` and calls
  `login[route.replaceAll("-","_")]()`, so an unknown hash throws.
- Status indicator: a `.indicator` carrying `data-text`, inside each section.
- `.login-success-banner` and `.resend-link` inside the email-link section.
- `.login-content` wrapper — `request_otp()` empties `.login-content:visible` and injects
  the 2FA form into it. Without it, two-factor login renders nowhere.

**Scripts and styles the page must load:**

```jinja
{% block head_include %}
{{ include_style('login.bundle.css') }}
<link rel="stylesheet" href="/assets/benchpress/css/brand.css?v={{ asset_version }}">
{% endblock %}

{% block script %}
<script>{% include "templates/includes/login/login.js" %}</script>
{% endblock %}
```

`login.bundle.css` comes first and `brand.css` second, so brand rules win. It cannot be
dropped: `.hide`, `.invalid`, `.field-error`, `.indicator` and the 2FA markup all get their
styling from it. `login.js` is a Jinja file — it must be `{% include %}`d, not linked, so
its `{{ _(...) | tojson }}` calls render.

Extending `templates/web.html` is mandatory: `frappe-web.bundle.js` (jQuery, `frappe.call`,
`frappe.ready`, `frappe.utils.sanitise_redirect`, `frappe.msgprint`) comes from its
`base_scripts` block, and `login.js` is nothing without them.

**The GitHub button.** The mockup's `Continue with GitHub` is rendered **but not wired** —
no `href`, `type="button"`, `disabled` attribute absent so it still looks live, and a
`data-bp-unwired="github"` hook so a later phase can find it. It must not be given a
`provider_logins` `auth_url`: the real OAuth buttons render from `provider_logins` in a
separate block. If a `Social Login Key` for GitHub is ever enabled, the real button appears
next to the decorative one; that is acceptable and expected, and the decorative one is what
a later phase deletes.

**The signup link.** `login.signup_prompt`'s link points at `#signup` when
`disable_signup` is falsy, and at `/signup` (the branded access-request page) when it is
truthy. On an invite-only site Frappe refuses to render the signup section, so `#signup`
would be a dead hash.

Sections, in order: `form`, `after_login_panel`, `footer`.

### 4.4 `/about`

- Template: `benchpress/www/about.html`
- Controller: `benchpress/www/about.py`
- Context: `settings` (`About Page Settings`), `days_without` and `days_with` (the
  `day_entries` child rows split by `column`, order preserved), `signup_route`.
- Sections, in order: `hero`, `situation`, `two-days`, `is-is-not`, `stats`, `principles`,
  `timeline`, `cta`, `trademark`, `footer`.

### 4.5 `/contact`

- Template: `benchpress/www/contact.html`
- Controller: `benchpress/www/contact.py`
- Context: `settings` (`Contact Page Settings`), `topics` (child rows), `default_topic`
  (the `is_default` row's label, else the first row's), `repo_url`.
- Sections, in order: `hero`, `channels`, `form`, `sidebar`, `footer`.
- The form posts to `benchpress.contact.submit`; on success the form block is replaced
  client-side with `form_success_title` / `form_success_body`. No redirect, no query string.

---

## 5. Palette — Cobalt

### 5.1 The conflict, and which value wins

Three sources disagree:

1. `handoff 2/README.md` documents `--brand` / `--m-blue` as `#1F5CF5`.
2. `handoff 2/_ds/*/tokens/marketing.css` ships `--m-blue: #2490EF` — the **Espresso**
   product blue, not the marketing navy.
3. Every page's inline `<style>` block overrides `:root` with the Cobalt set.

**The inline Cobalt values are authoritative.** `marketing.css` is the design system's
default and is deliberately overridden on every page in the handoff. Ship one
`brand.css` that redeclares the marketing tokens at `:root` with the Cobalt values below;
do not edit `marketing.css`, and do not load it and hope.

Two further disagreements between `landing.html` and `pages.html`, resolved here so the
two never fork:

| Token | landing.html | pages.html | **Ship** | Why |
|---|---|---|---|---|
| `--fg2` dark | `rgba(255,255,255,.70)` | `rgba(255,255,255,.68)` | `rgba(255,255,255,.70)` | matches README ("70%") |
| `--fg3` dark | *broken, see below* | `rgba(255,255,255,.44)` | `rgba(255,255,255,.45)` | matches README ("45%") |
| `--cardb` light | `#DFE7FA` | `#E0E8FA` | `#DFE7FA` | README + landing agree |
| `--hair` light | `#E3EAFB` | `#E0E8FA` | `#E3EAFB` | README + landing agree |

`landing.html` line 32 contains two self-referential declarations —
`--fg3:var(--fg3)` and `--hair:var(--hair)` — which resolve to nothing. They are a bug in
the export. Fill them from the README: `--fg3: rgba(255,255,255,.45)`,
`--hair: rgba(255,255,255,.12)`.

### 5.2 `.bp[data-mode="…"]` — the page palette

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg0` | `#06091A` | `#F6F8FF` | Page ground; also `body` background |
| `--bg1` | `#0A1024` | `#FFFFFF` | Section band (hero, pipeline, agents, CTA) |
| `--bg-alt` | `#FFFFFF` | `#F1F5FF` | Alternating light band — console, compare, services, testimonials, FAQ. Text on it is `--m-ink`, not `--fg`. |
| `--card` | `rgba(78,139,251,.07)` | `#FFFFFF` | Card fill |
| `--cardb` | `rgba(78,139,251,.22)` | `#DFE7FA` | Card border; also the "on" state of a diagram node |
| `--fg` | `#FFFFFF` | `#0A1024` | Body text, headings |
| `--fg2` | `rgba(255,255,255,.70)` | `#4E5A7C` | Muted text, nav links, card bodies |
| `--fg3` | `rgba(255,255,255,.45)` | `#8B94AE` | Dim text, assurance strip, inactive tab |
| `--hair` | `rgba(255,255,255,.12)` | `#E3EAFB` | Hairline rules and section top borders |
| `--panel` | `#080E20` | `#0A1024` | Code / terminal panels — constant dark in both modes |
| `--accent` | `#4E8BFB` | `#1F5CF5` | Eyebrows, icons, links, active diagram node border |
| `--codefg` | `#9FC3FF` | `#9FC3FF` | Mono text on `--panel` |
| `--grid` | `rgba(120,160,255,.10)` | `rgba(31,92,245,.10)` | Hero dot-grid |
| `--glow` | `rgba(31,92,245,.45)` | `rgba(31,92,245,.14)` | Radial hero glow, button and film shadow |
| `--dock` | `rgba(10,16,36,.84)` | `rgba(255,255,255,.9)` | Floating nav dock, behind `backdrop-filter` |
| `--cta-fg` | `#0A1024` | `#FFFFFF` | Text on the inverted final-CTA button |
| `--cta-bg` | `#FFFFFF` | `#1F5CF5` | Fill of the inverted final-CTA button |

The four non-landing pages add these (from `pages.html`,
`.bp[data-th="cobalt"][data-mode="…"]`), and the landing page needs them too — ship one set:

| Token | Dark | Light | Use |
|---|---|---|---|
| `--brand` | `#1F5CF5` | `#1F5CF5` | Primary action fill. Constant across modes. |
| `--brand2` | `#4E8BFB` | `#0F3FCB` | Primary action hover |
| `--onbrand` | `#FFFFFF` | `#FFFFFF` | Text on `--brand` |
| `--tint` | `rgba(31,92,245,.18)` | `#E8EEFF` | Selected chip / swatch background |
| `--input` | `rgba(255,255,255,.05)` | `#FFFFFF` | Form-control fill |
| `--code` | `#080E20` | `#0A1024` | Inline code chip background (same role as `--panel`) |
| `--lime` | `#4CDD2E` | `#2FB714` | **Status only, never decoration** |

### 5.3 `:root` marketing overrides

Declared once, mode-independent. Left column is what Cobalt ships; right column is the
`marketing.css` value it replaces, listed so nobody "fixes" one back.

| Token | Cobalt (ship this) | marketing.css (overridden) | Use |
|---|---|---|---|
| `--m-ink` | `#0A1024` | `#0A0D14` | Text on the always-light `--bg-alt` bands |
| `--m-blue` | `#1F5CF5` | `#2490EF` | Marketing primary — same hex as `--brand` |
| `--m-blue-hover` | `#0F3FCB` | `#1579D0` | Marketing primary hover |
| `--m-accent-soft` | `#E8EEFF` | `#E6F3FE` | Soft accent wash |
| `--m-panel` | `#F2F6FF` | `#F4F8FC` | Light panel inside a light band |
| `--m-cta-band` | `#E8EEFF` | `#EDF3F8` | CTA band fill (landing only) |
| `--m-line` | `#E0E8FA` | `#E5EAF1` | Light-band hairline |
| `--m-line-strong` | `#C9D6F4` | `#D3DDE8` | Console tab border, table rules |
| `--m-thead` | `#EFF4FF` | `#F1F5F9` | Console table head (landing only) |
| `--m-zebra` | `#F6F9FF` | `#F7F9FC` | Console table zebra (landing only) |
| `--m-muted` | `#4E5A7C` | `#5C6675` | Muted text on light bands |
| `--m-eyebrow-dark` | `#7FA8FF` | `#A7DCF5` | Eyebrow on a dark band |
| `--m-code-cyan` | `#9FC3FF` | `#7FD3F0` | Mono accent on a dark panel |

Landing-only extras, also at `:root`: `--bp-panel: #080E20`, `--bp-accent: #4E8BFB`.

`pages.html` omits `--m-cta-band`, `--m-thead`, `--m-zebra` and the `--bp-*` pair. Ship the
full set on every page; the unused ones cost nothing.

### 5.4 Espresso tokens used as-is

The console mock on the landing page is a picture of the product and uses
`_ds/*/tokens/colors.css` **unmodified**: `--gray-1..5`, `--ink-3..9`, `--ink-white`,
`--green-1 / --green-3 / --green-ink`, `--blue-1 / --blue-3`, `--amber-1 / --amber-2 /
--amber-ink`, `--red-1 / --red-4 / --red-ink`. The `info` status pill is the one exception:
the mockup hardcodes `#EDF1FF` / `#1B2CC1` / `#1B2CC1` rather than the Espresso blue ramp.
Reproduce those three literals; do not substitute `--blue-1` / `--blue-3`.

Do not mix the two palettes anywhere else. Espresso is for the console screenshot; Cobalt
is for the page around it.

### 5.5 On-dark islands

Any surface that stays dark in both modes carries `data-ondark`, which re-pins the text
tokens for all its descendants. Never hardcode white text; add the attribute.

```css
.bp [data-ondark]{
  --fg:#FFFFFF;
  --fg2:rgba(255,255,255,.72);
  --fg3:rgba(255,255,255,.45);
  --hair:rgba(255,255,255,.14);
  --card:rgba(255,255,255,.06);
  --cardb:rgba(255,255,255,.16);
  color:#FFFFFF;
}
```

### 5.6 Type, motion, breakpoints

- Headings: **Poppins 800**. Body: Poppins 400–600. `--font-display` already resolves to
  `"Poppins","Inter",system-ui,sans-serif`. Poppins is loaded from Google Fonts in the
  handoff — **vendor it locally** for production; `Inter` is already shipped in
  `_ds/*/assets/fonts/`.
- Every machine string — IDs, IPs, commands, log lines, the `REQ-…` reference — uses
  `--font-mono` (`ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`).
- Keyframes to port verbatim: `bp-pulse`, `bp-line`, `bp-rise`, `bp-caret`, `bp-float`,
  `bp-marquee`, `bp-bar`, `flow-down`.
- Breakpoints, keyed on `data-r` hooks:
  - `≤900px` — gutters 18px, section padding 56px, `[data-r~="split"]` → one column,
    `[data-r="bento"]` → one column, `[data-r="nav"]` hidden, tab strips full width,
    `[data-r="float"]` un-floats, `h1` 34px / `h2` 26px / `h3` 24px.
  - `≤560px` — gutters 14px.
- Respect `prefers-reduced-motion`: the marquee, the pulse and the line-in animations all
  stop. The mockup does not do this; add it.

---

## 6. Email

All six templates are **`Email Template`** rows, seeded by the install hook and editable in
Desk. `Email Template` autonames on `Prompt`, so the name **is** the title given below.
Render with:

```python
template = frappe.get_cached_doc("Email Template", TEMPLATE_NAME)
body = template.get_formatted_email(context)   # -> {"subject": ..., "message": ...}
frappe.sendmail(recipients=[...], subject=body["subject"], message=body["message"], delayed=True)
```

`frappe.sendmail(template=...)` is **not** this — that argument names a file under
`templates/emails/`. Use `get_formatted_email`.

Every send goes through `benchpress.notifications.email_owner`-style best-effort handling:
a mail failure must never roll back the transition that caused it. Wrap in `try/except`,
`frappe.log_error` on failure, never re-raise.

**Admin recipients.** One helper, `benchpress.public_site_mail.admin_recipients()`:
enabled `User` rows holding `BenchPress Admin` or `System Manager`, built with `frappe.qb`
over `tabHas Role` joined to `tabUser` (`enabled = 1`, `user_type = "System User"`),
deduplicated. Never `frappe.db.sql`. Falls back to
`Contact Page Settings.notify_email` when the query returns nothing.

### 6.1 Access request submitted

Fires from `waitlist.join`, on the **insert** path only — inside `insert_once`, after the
savepoint commits, and never on the swallowed `DuplicateEntryError`. A repeat submission
mails nobody, which is also why the response is unchanged.

**a. Acknowledgement to the requester**

- Template: `BenchPress Access Request Received`
- To: the requester
- Subject: `Your BenchPress access request — {{ reference }}`
- Variables: `full_name`, `email`, `reference`, `company`, `team_size`, `intent`,
  `expected_apps`, `use_case`, `repo_url`, `docs_url`, `site_url`
- Body must name the reference, say the review is by a person, give the one-business-day
  window, and link the self-hosting path so a waiting requester is not stuck.

**b. Notice to admins**

- Template: `BenchPress Access Request Filed`
- To: `admin_recipients()`
- Subject: `Access request from {{ full_name }} ({{ company }})`
- Variables: all of the above plus `desk_url` (the Desk form URL for the row) and
  `submitted_on`
- Body carries every submitted field verbatim so a decision needs no click, plus the link.

### 6.2 Approved

Fires from `WaitlistEntry.approve()`, after `invite_user()` returns.

- Template: `BenchPress Access Approved`
- To: the requester
- Subject: `Your BenchPress account is open`
- Variables: `full_name`, `email`, `reference`, `login_url`, `free_credits`
  (`Credit Settings.signup_grant_credits`), `docs_url`, `site_url`

**Two emails go out on approval, and that is deliberate.** `create_user()` sets
`send_welcome_email = 1`, so Frappe sends the credential-bearing welcome mail with the
password-set link. This template carries the decision — approved, here is the balance, here
is what to do first — and never carries a credential. Do not fold them together and do not
turn off the welcome mail; a single mail would either leak a password link into a template
an operator can edit in Desk, or drop the only way the account can be claimed.

When the `User` already existed (`invite_user` took the `grant_access_role` branch), only
this template fires — there is no welcome mail to pair with. The body must therefore read
correctly in both cases: point at `login_url`, and say "if you have not set a password yet,
use the link in the separate welcome email".

### 6.3 Rejected

Fires from `WaitlistEntry.reject()`.

- Template: `BenchPress Access Declined`
- To: the requester
- Subject: `About your BenchPress access request`
- Variables: `full_name`, `email`, `reference`, `rejection_reason`, `repo_url`, `docs_url`
- Body gives the plain answer the signup page promises ("you will get a plain answer
  instead of silence"), includes `rejection_reason` when set, and points at self-hosting,
  which needs no approval. Never says why in terms of the person.

No email fires when an entry is flipped to `Rejected` from the Desk form directly — only
`waitlist.reject` mails. That keeps a bulk correction from spraying declines; the Desk
list view's bulk action calls `waitlist.reject`.

### 6.4 Contact message

Both fire from `contact.submit`, after the insert.

**a. Acknowledgement to the sender** — only when
`Contact Page Settings.acknowledge_sender` is checked.

- Template: `BenchPress Contact Message Received`
- To: the sender
- Subject: `We got your message`
- Variables: `sender_name`, `email`, `topic`, `message`, `response_window` (the
  `Contact Response Time.window` whose `subject` matches the topic, else the first row's),
  `repo_url`, `site_url`

**b. Notice to admins**

- Template: `BenchPress Contact Message Filed`
- To: the topic's `route_to_email` when set, otherwise
  `Contact Page Settings.notify_email`, otherwise `admin_recipients()`
- Subject: `[{{ topic }}] {{ sender_name }}`
- Variables: `sender_name`, `email`, `topic`, `message`, `submitted_on`, `desk_url`
- Set `reply_to=<sender email>` on this one so a reply goes to the person, not to the site.

### 6.5 Unchanged

`waitlist.announce_signup` keeps its inline `frappe.sendmail`. Migrating it to an
`Email Template` is out of scope for this work and would change a one-shot that has already
run on some sites.

---

## 7. Notes for other phases

These are changes this spec depends on in files it does not cover.

### hooks_changes — `benchpress/hooks.py`

1. **Nothing is required for `/login` to shadow Frappe's.** `TemplatePage` already searches
   `reversed(get_installed_apps())`. Do not add a `website_route_rules` entry for it; a
   route rule would bypass `frappe/www/login.py` and break the OAuth and redirect paths.
2. `website_route_rules` needs **no** new entries. `/`, `/signup`, `/about` and `/contact`
   all resolve from `benchpress/www/` by filename.
3. `after_install` (`benchpress.install.after_install`) must call a new
   `benchpress.public_site.seed.seed_public_site()` — seeds the three Singles, their child
   tables and the six `Email Template` rows, only where they are empty.
4. A patch entry is needed so an existing site gets the same seed:
   `benchpress.patches.v1_0.seed_public_site`, calling the same idempotent function.
5. Consider adding `Email Template` to `fixtures` filtered to the six names, so an
   operator's wording edits are exportable. This is a judgement call for the fixtures
   phase, not a requirement.
6. `benchpress/www/home.py`, `home.html` and `home_content.py` are **superseded** by
   `www/index.*`. Do not delete them in this work — `home_content.PHASES` is the accurate
   pipeline description and may be worth folding into the seed later. Decide their fate in
   a follow-up; until then `/home` and `/` both exist and `/home` is unlinked.
7. `Website Settings.home_page` must be empty (or `index`) for `/` to resolve to
   `www/index.html`. If any install step sets it to `home`, that must change.

### CLAUDE.md

Add `Landing Page Settings`, `Signup Page Settings`, `About Page Settings`,
`Contact Page Settings`, `Contact Message` to the doctype list, and a line noting that
`benchpress/www/login.html` deliberately shadows Frappe's and must keep its context and DOM
contract (§4.3) in step with the framework on every Frappe upgrade.

### brand.css — `benchpress/public/css/brand.css`

Ships §5 in full: the `:root` marketing overrides, both `.bp[data-mode="…"]` blocks, the
`[data-ondark]` block, the eight keyframes and the two breakpoints. It must **not**
`@import` `marketing.css`. `login.bundle.css` loads before it on `/login`.

### templates/includes/

`public_header.html` needs, in context: `nav_items` (each `{label, anchor, is_cta}`),
`signup_route`, `mode_default`, `is_landing` (bool — the landing header is a floating pill
dock, the other four a plain bar), and the session keys `is_signed_in`, `login_route`,
`console_route`, `logout_method`, `csrf_token`. Both of Frappe's logout endpoints are
POST-only, so the sign-out control is a form, not a link.
`public_footer.html` needs: `footer_columns` (`[{heading, links:[{label,url}]}]`),
`footer_tagline`, `footer_copyright`, `footer_trademark`, `footer_trademark_short`,
`is_landing` (the four non-landing pages use the compact footer).

### fixtures/

Roles are already fixtured. If §7.5 is adopted, add the `Email Template` filter there.

### Other

- `benchpress.credits.config.SIGNUP_ROUTE` is `/login#signup` and now collides in meaning
  with the new `/signup` page. This spec resolves it at runtime (§4.2 redirect rule)
  without changing the constant. If a later phase wants one name, change the constant and
  the redirect together — never one of them.
- `docs_assets.DocsAssetRenderer` is a `page_renderer` and runs **before** `TemplatePage`.
  Confirm it does not claim `/about` or `/contact`; it currently serves `/docs` assets only.
- `assets/logo/*` and `assets/app-icons/*` from the handoff must be copied into
  `benchpress/public/images/logo/` and `benchpress/public/images/app-icons/`. The URLs in
  this spec assume that location.
