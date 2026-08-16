# Handoff: BenchPress frontend redesign

## Overview

A complete UI redesign of the BenchPress frontend — the self-hosted Frappe Cloud
alternative that spins up isolated Frappe/ERPNext environments in Docker
containers and exposes them over WireGuard.

The redesign covers all ten existing routes plus the five screens
`DESIGN_BRIEF.md` §6 says are missing (overview, onboarding, deploy progress,
activity feed, health), and it fixes all nine problems listed in §8.

## About the design files

`Benchpress.dc.html` is a **design reference, not production code**. It is a
single self-contained HTML prototype (plain inline styles, no build step, one
small runtime in `support.js`) that shows the intended look and behaviour of
every screen. Open it in a browser and click through it before writing code.

**Do not port this HTML into the app.** The task is to recreate these screens in
the existing BenchPress frontend — Vue 3 + Vite + **frappe-ui** + Tailwind,
`/frontend` base path — using frappe-ui components and Espresso semantic
classes. The mapping table below names the frappe-ui component for every piece
of UI in the prototype. Everything in the prototype is buildable with the
component list in `DESIGN_BRIEF.md` §9; nothing new is required.

## Fidelity

**High fidelity.** Colours, type sizes, spacing, radii, states and copy are all
final and are listed below. Match them. Where a hex here equals an Espresso
token, **use the token class, not the hex** (`text-ink-gray-7`, not `#525252`)
— the hexes are given so you can verify, and so dark mode keeps working.

## How to run the prototype

Put `Benchpress.dc.html`, `support.js` and `app-icons/` in the same folder and
open the HTML in a browser. Everything is clickable.

Three prototype-only switches exist at the top of the logic class
(`class Component extends DCLogic`) — `role`, `vpnConnected`, `firstRun`. In the
real app these come from the session user's role, the WireGuard peer status, and
"does this user own any bench instances".

- `role: 'user' | 'admin'` — BenchPress User vs BenchPress Admin (§2). The
  sidebar "Switch" button flips it live.
- `vpnConnected: boolean` — drives every unreachable/reachable state.
- `firstRun: boolean` — shows the onboarding panel on Overview.

---

## Information architecture

Sidebar is five items. The Logs section from the old app is **gone** — logs are
reached from the object they belong to.

| Sidebar item | Route | Roles | Notes |
|---|---|---|---|
| Overview | `/` | both | New. Replaces the redirect-to-table. |
| Labs | `/labs` | both | Admin also gets New lab + Build history. |
| Templates | `/labs/templates` | admin | |
| Instances | `/bench-instances` | both | Renamed from "Bench instances". |
| Devices | `/devices` | both | Renamed from "VPN devices". |

Reached from within, not from the sidebar:

| Screen | Route | Entry point |
|---|---|---|
| Lab detail | `/labs/:labId` | Labs row, Overview row, log rows |
| New lab | `/labs/new` | "New lab" on Labs / Overview (admin) |
| Deploy history | `/deploy-logs` | "Deploy history" button on Instances |
| Build history | `/build-logs` | "Build history" button on Labs (admin) |
| Settings | `/settings` | Sidebar footer (admin) |

Header is: breadcrumb (parent + current), a search affordance with ⌘K
(`CommandPalette`), the VPN status chip, and a `Dropdown` with Switch to Desk
(admin), Toggle theme, Keyboard shortcuts, Log out.

---

## Design tokens

Every value in the prototype maps to Espresso. Use the class, not the hex.

### Colour

| Role | Hex | Espresso class |
|---|---|---|
| Page background | `#F9F9F9` | `bg-surface-gray-1` |
| Card / panel | `#FFFFFF` | `bg-surface-white` |
| Sidebar | `#F4F4F4` | `bg-surface-gray-2` |
| Table header fill | `#F9F9F9` | `bg-surface-gray-1` |
| Hairline / card border | `#E2E2E2` | `border-outline-gray-1` |
| Row divider | `#F4F4F4` | `border-outline-gray-modals` equivalent — use the lightest divider |
| Primary text | `#171717` | `text-ink-gray-9` |
| Secondary text | `#525252` | `text-ink-gray-7` |
| Tertiary text | `#666666` | `text-ink-gray-6` |
| Muted / meta | `#808080` | `text-ink-gray-5` |
| Placeholder / disabled | `#999999`, `#B3B3B3` | `text-ink-gray-4`, `text-ink-gray-3` |
| Link | `#2490EF` (hover `#1579D0`) | `text-ink-blue-3` |
| Solid button | bg `#171717`, hover `#2F2F2F`, text `#FFF` | `Button variant="solid"` |
| Subtle button | bg `#FFF`, border `#E2E2E2`, hover `#F4F4F4` | `Button variant="subtle"` |

### Status colours — the §8.1 fix

Never render a status as grey text again. Every status is a `Badge`.

| Meaning | Badge theme | bg | fg | dot |
|---|---|---|---|---|
| Success / Ready / Running / Active / Healthy | green | `#E7F5EE` | `#167C4A` | `#30A66D` |
| In progress / Building / Deploying / Creating | blue | `#EFF6FE` | `#1579D0` | `#2490EF` |
| Warning / VPN off | orange | `#FEF6E7` | `#9A6700` | `#E5A544` |
| Error / Failed / Unhealthy | red | `#FDF0EF` | `#C7291F` | `#E03636` |
| Neutral / Stopped / Unknown / Idle | gray | `#F4F4F4` | `#666666` | `#B3B3B3` |

Pill shape: `border-radius: 999px`, `padding: 2px 8px`, `font-size: 11px`,
`font-weight: 500`, 5px round dot at 5px gap before the label.

### Type — Inter, shipped locally

| Use | Size / weight | Notes |
|---|---|---|
| Page title | 19px / 600 | `letter-spacing: -0.02em` |
| Section / card title | 13px / 600 | |
| Body, table cell | 12.5px / 450–500 | |
| Meta, helper | 11–11.5px / 400 | `text-ink-gray-5` |
| Table column header | 11px / 600 | `text-ink-gray-5` |
| Eyebrow (onboarding) | 11px / 600 | uppercase, `letter-spacing: 0.08em` |
| Big stat | 22px / 600 | `letter-spacing: -0.02em`, tabular numerals |
| Monospace | 11.5px | IDs, IPs, git URLs, image tags, log lines |

Any number that changes in place — usage %, durations, counts — gets
`font-variant-numeric: tabular-nums`.

### Spacing, radius, elevation

- Page padding `22px 24px 40px`; card padding `15–18px`; card gap `16px`; grid gap `14px`.
- Content max widths: 1180px standard, 1080px for New lab and history tables, 960px for Devices, 760px for Settings, 820px for the pipeline card.
- Radius: pills 999px, controls/buttons/inputs 7px, cards 11px, dialogs 12px.
- Borders are 1px, always. Cards are outlined, not shadowed.
- Shadow only on: dropdown `0 8px 24px rgba(0,0,0,.12)`, dialog `0 20px 46px rgba(0,0,0,.2)`, card hover `0 2px 8px rgba(0,0,0,.06)`, active sidebar item `0 1px 2px rgba(0,0,0,.06)`.
- Controls: buttons/inputs 32px tall (28–30px for secondary/inline), 6px icon-to-label gap.
- Motion: 120–180ms ease-out. Only two animations exist — a 0.8s spinner on the active pipeline step, and a 1.8s pulse on the disconnected VPN dot.

---

## Screens

### 1. Overview — `/` (new)

Fixes §8.2 "no orientation" and §6 "no dashboard / no activity feed".

- **Onboarding panel** (only when the user owns no benches). Eyebrow "GETTING STARTED", then the positioning line verbatim: *"Create a Frappe environment, press deploy, get a working site and a VS Code window."* Sub-line explains Lab → container → site → IDE. Three numbered cards: Pick a lab recipe / Deploy it / Connect over VPN. Buttons: "Start from a template" (solid), "Set up VPN first" (subtle).
- **Greeting row** — "Good morning, {first name}", sub-line counts. Right: "From template" (subtle) and a solid CTA — "New lab" for admin (→ `/labs/new`), "New environment" for a user (→ templates, since Users cannot create labs).
- **VPN warning banner** when the tunnel is down: orange, one sentence, "Connect device" button. This is the §7C fix — the app now says why nothing is reachable.
- **Stat row** — 4 `NumberChart`-style tiles: Running, Stopped, Needs attention (red when > 0), Deploy time (avg). Label 11.5px, value 22px/600.
- **Environments list** — the user's benches (admin: all). Row = app icon, bench name + site, health as plain coloured text, status `Badge`, contextual button (Open / Start / View). Row click → Lab detail.
- **Recent activity** — coloured dot, message, relative time. §6 gap.
- **Shared infrastructure** (admin only) — MariaDB / Redis / Traefik with status badges.

### 2. Labs — `/labs`

Fixes §8.3 (wrong columns) and §8.4 (empty states).

Columns: **Lab** (icon + title + mono `lab_id`), **Version**, **Apps** (chips),
**Status** (`Badge`), **Deployed as** (site URL in blue + bench name/state),
**Last run**. Memory and CPU are gone from the table — they live on the detail
header. Header actions: Build history (admin), From template, New lab (admin).
Filters: search input + three `ListFilter` dropdowns (Status, Version, Owner).

Empty state is not a sentence — it is the onboarding panel plus a "Start from a
template" button.

### 3. Lab detail — `/labs/:labId`

The §8.5–§8.8 fixes all land here.

- **Header**: 40px app icon, title, status `Badge`, mono `lab_id`, description,
  and spec chips (version, RAM, vCPU, code-server, ssh). Right side, in order:
  "Open VS Code" (subtle, only when Running), the **primary** button, and a `⋯`
  `Dropdown`.
  - Primary is contextual: `Deploy` → `Deploying…` (disabled) → `Open site`;
    `Rebuild image` when the lab errored. When the VPN is off it reads
    **"Open site — VPN off"** and is disabled.
  - **Stop and Delete moved into the `⋯` menu behind `ConfirmDialog`** (§8.5).
- **Tabs** (`Tabs`): Dashboard · Sites · Deploy log · Build log (admin).
- **Error banner** (when the lab failed) — red card naming the failing step, the
  reason in mono, and two buttons: "Edit apps and rebuild", "View failing log
  lines" (jumps to the Deploy log tab). This is journey §7D.
- **Container status card** — §8.7 fix: bench status and `container_health` are
  shown as **two separate** signals. Health badge sits next to a "checked 30s
  ago" timestamp. Two `Progress` meters: CPU (green) and Memory (amber above
  60%), each with a caption ("quota 2 vCPU", "68% of limit"). Not running →
  em-dash values and a "container not running" caption.
- **Sites card** — domain, installed apps, status badge, Open button (disabled
  and labelled "Unreachable" when the VPN is down). Empty state: "No site yet —
  one is created automatically when this lab is deployed."
- **Connection card** (right) — green when reachable, amber when not, with a
  "Register this device" button in the amber state.
- **Connection details** — §8.8 fix: site URL, WireGuard IP, code-server, SSH,
  SSH password, admin password. Passwords render as `••••••••••` behind one
  "Reveal secrets" toggle; every row has a copy button. Use frappe-ui
  `Password` + `Tooltip`("Copied").
- The old "Lab Information" card is deleted — it duplicated the header (§8.6).

### 4. Deploy log tab — the 11-step pipeline (§6, §4)

The centrepiece. A `Steps`-style list of the eleven real steps from
`deploy_manager.py`, in order, each with:

- state icon — green check (done), blue spinning ring (active), grey dot (pending), red `!` (failed);
- label 12.5px, active/failed at 600;
- a mono sub-line with the real detail (`container_ip 172.19.0.7`, `bench new-site …`);
- elapsed time right-aligned, or "running" / "failed".

Header: run title, result badge, total elapsed. **Raw log is collapsed
underneath** with a Download button and line count — colour-coded by
`log_type` (`error` red, `success` green, `step`/`info` blue/grey).

Live runs stream over socket.io (`bench_deploy_log`, `lab_build_log`) — the
prototype fakes this on a timer. Failure shows the cleanup line explicitly
("Nothing to roll back — no container was created").

### 5. Deploy dialog

Shown when a deploy starts from anywhere (template card, New lab, lab detail).
`Dialog` with the same eleven steps, a 3-line rolling log tail, and a footer:
"Run in background" (subtle) + a solid CTA that is disabled "Deploying…" until
complete, then "Open site" — or "Connect VPN to open" if the tunnel is down, in
which case it routes to Devices instead of the site.

The site slug and the installed-app log lines derive from the template that was
clicked. Never hardcode ERPNext.

### 6. Templates — `/labs/templates`

The seven catalog entries from `lab_templates.py`. Card = official app icon,
name, version, "Most used" badge on ERPNext, one-line description, then
**app icon pills under the sentence** (icon + friendly label: ERPNext, HR, CRM,
Helpdesk, Learning) followed by grey resource chips (RAM, vCPU). Footer: ETA
left, "Use template" solid right → deploy dialog.

### 7. Instances — `/bench-instances`

Columns: Bench (icon, `bench-<lab_id>`, mono wg IP), Status `Badge`, Health,
CPU / memory (text + a 4px `Progress` bar), Site, Owner. Header carries the
"Deploy history" button. Admin sees all owners; a User sees only their own
(row-level `owner` filter) — the sub-line states which.

### 8. Devices — `/devices`

- Status banner: green "WireGuard is up on this device" with last handshake, or
  amber "This device is not on the VPN" with a pulsing dot; button toggles.
- **Device list** (full width, not cards): icon, name + OS/date, WireGuard IP,
  transfer (`wg_rx_bytes` / `wg_tx_bytes`), status badge, Config / QR / `⋯`.
  Last row is "Add another machine".
- Right column: "How this works" (3 numbered steps) and "A site will not open?"
  (3 checks + "Run connection test").
- **Add device dialog**: name input (focused), QR panel (use the `qrcode`
  package already shipped), explanation, "Download .conf", and "Register and
  connect" which registers the peer and flips the whole app to connected.

### 9. New lab — `/labs/new` (admin)

Three cards plus a sticky summary rail.

- **Identity** — Title; Lab ID (read-only, slugified from the title, mono, help: "Cannot change later — used in the container name and site domain"); Description; Frappe version as a `TabButtons` segmented control (version-14/15/16/develop).
- **Apps** — child table: App, Git URL (mono), Branch (mono), remove `×`. "Add app" below. Help: "Cloned at build time — frappe is always included".
- **Resources and access** — memory_limit, cpu_cores, iops_limit, bps_limit, pids_limit in a responsive grid; then two `Switch`es: Code server (on) and SSH access (off), each with a one-line explanation.
- **Summary rail** — "What gets built" recomputes live from the form (image tag, version + apps, code-server/SSH state, "a site is created on first deploy"). Buttons: "Save and build image" (solid, starts the pipeline) and "Save as draft".

### 10. Build history / Deploy history

Two tables, same shape. Build: Lab, Image tag (mono), Result badge, Last step,
Duration, Started. Deploy: Bench, Result, Last step, Duration, Started. Rows
open the lab. Both have a back link to their parent.

### 11. Settings — `/settings` (admin)

Three grouped cards on a 760px column — Domains (`base_domain`,
`default_image`), Docker (`docker_socket`, `traefik_network`), Container
defaults (memory, CPU quota, `code_server_version`) — then a save bar with
"Last saved by …", Discard, Save settings.

---

## Interactions & behaviour

- Row click opens the object; buttons inside rows never navigate.
- Hover: rows `bg-surface-gray-1`; subtle buttons `#F4F4F4`; solid `#2F2F2F`; template cards lift with the small shadow. No scale transforms anywhere.
- Anything unreachable is **disabled with an explanatory label**, never hidden — "Open site — VPN off", "Unreachable".
- Destructive actions are always `ConfirmDialog`; deleting a bench must spell out that databases and volumes are dropped.
- Every table has a real empty state: one sentence plus the action that fixes it.
- Responsive: sidebar is fixed 236px; content grids collapse via `auto-fit`/`minmax`; the wide tables scroll horizontally inside their card below ~900px rather than crushing the name column.

## State

| State | Source |
|---|---|
| `role` | session user roles (BenchPress Admin / System Manager vs User) |
| `vpnConnected` | current device's WireGuard peer status + last handshake |
| `firstRun` | user owns zero bench instances |
| selected lab / tab | route params |
| deploy progress | socket.io `bench_deploy_log`; derive the step from the emitted `step` lines, not a client timer |
| reveal secrets | local component state, resets on navigation |

Data layer: `createListResource` for Labs / Bench Instances / Devices / logs,
`createDocumentResource` for Lab detail and the Settings singleton,
`createResource` for actions (deploy, start, stop, build, register peer).

## Assets

`app-icons/` — official marks, copied from the upstream repos (SVG, all
public):

| File | Source |
|---|---|
| `frappe.svg` | `frappe/frappe` → `frappe/public/images/frappe-framework-logo.svg` |
| `erpnext.svg` | `frappe/erpnext` → `erpnext/public/images/erpnext-logo.svg` |
| `crm.svg` | `frappe/crm` → `crm/public/images/logo.svg` |
| `hrms.svg` | `frappe/hrms` → `hrms/public/images/frappe-hr-logo.svg` |
| `helpdesk.svg` | `frappe/helpdesk` → `desk/public/favicon.svg` |
| `lms.svg` | `frappe/lms` → `frontend/public/learning.svg` |

India Compliance has no mark upstream — it reuses the ERPNext icon. Icons are
rendered as CSS backgrounds in the prototype; in Vue use `<img>` from
`/assets`. All other iconography is Lucide via `~icons/lucide/*`, 2px stroke,
`currentColor`, 16px in buttons and rows, 20px in the onboarding chips.

## frappe-ui component mapping

| Prototype element | frappe-ui |
|---|---|
| Sidebar, nav items | `Sidebar` |
| Header breadcrumb | `Breadcrumbs` |
| Search + ⌘K | `CommandPalette` |
| Account menu, `⋯` menus | `Dropdown` |
| Every status pill | `Badge` (themes above) |
| All buttons | `Button` (`solid` / `subtle` / `ghost`) |
| Tables | `ListView` with custom cell slots |
| Filters | `ListFilter`, `Select`, `Autocomplete` |
| Tabs on Lab detail | `Tabs` |
| Frappe version picker | `TabButtons` |
| CPU / memory / bench usage bars | `Progress` |
| Stat tiles | `NumberChart` |
| Deploy dialog, Add device | `Dialog` |
| Stop / Delete confirmation | `ConfirmDialog` |
| Secrets | `Password` + copy `Tooltip` |
| Toggles on New lab | `Switch` |
| Form fields | `FormControl`, `FormLabel`, `TextInput`, `Textarea` |
| Copy feedback, save confirmation | `Toast` |
| Spinner on the active step | `Spinner` / `LoadingIndicator` |
| QR for a device | the `qrcode` package already in the frontend |

## Files in this bundle

| File | What it is |
|---|---|
| `Benchpress.dc.html` | The prototype — all screens, all states. Open in a browser. |
| `support.js` | Runtime the prototype needs. Keep it next to the HTML. Not part of the deliverable. |
| `app-icons/*.svg` | The six app marks. |
| `DESIGN_BRIEF.md` | The original developer brief this design answers (object model, pipeline, routes, §8 problem list). |

## Acceptance — §10 of the brief

A developer who has never seen BenchPress can, without asking anyone: say what
the product does from the first screen; tell at a glance which environments are
running, broken or building; get from zero to a deployed ERPNext site using a
template; know what to do when a build fails; and connect a device to the VPN
and confirm it worked. Check the build against those five, and against the nine
problems in §8 — each one has a named fix above.
