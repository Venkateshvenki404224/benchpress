# BenchPress — Design Brief

Developer-to-designer context for the BenchPress frontend redesign.
Written 2026-08-16 against `version-16` branch.

**Hard constraint: mockups must be buildable with frappe-ui components only.**
No new component library, no Bootstrap, no Material UI. Details in *Constraints*.

---

## 1. What BenchPress is

BenchPress is a **self-hosted onboarding and dev-environment tool for Frappe
teams** — not a Frappe Cloud alternative; it solves a narrower, different
problem: getting a new developer or intern a working bench in minutes. A team
runs it on their own server. It lets people spin up isolated Frappe/ERPNext
development environments — each one a Docker container with its own database,
its own site, and browser-based VS Code — and reach them privately over a
WireGuard VPN.

The one-line version a new user should understand within five seconds of
landing: *"Create a Frappe environment, press deploy, get a working site and a
VS Code window."*

Today the app does not say that anywhere. A new user lands on an empty table.

---

## 2. Who uses it

Two roles exist in code (`benchpress/permissions.py`). They see different apps.

### BenchPress Admin (also: System Manager)

The person who runs the server. Small in number — often one person.

- Creates and edits Labs, builds Docker images
- Manages the template catalog and global Settings
- Sees **every** Lab, bench, log and device in the system
- Can delete bench instances (destructive; drops databases and volumes)
- Can jump to the Frappe Desk backend

### BenchPress User

A developer who just wants an environment. The majority of seats.

- Sees **only bench instances they own** (row-level filter on `owner`)
- Can deploy, start, stop, restart their own benches
- Can create sites on their benches
- Registers their own VPN devices and downloads WireGuard configs
- Reads deploy logs for their own benches
- Cannot: create Labs, build images, edit templates, open Settings, delete
  benches, or see build logs

Design implication: the same screens render with fewer controls for a User.
Mockups should show both states for any screen with admin-only actions, or the
User view will end up as an afterthought with holes in the layout.

---

## 3. The object model

This is the spine of the product. Everything on every screen is one of these.

```text
Lab  ──build image──▶  Docker image  ──deploy──▶  Bench Instance  ──▶  Bench Site
 │                                                     │
 │                                                     ├── Database Server (shared MariaDB)
 └── Lab App[] (git url + branch)                      ├── VPN Peer (WireGuard IP)
                                                       └── Bench App[]
```

### Lab — *the recipe*

A named, reusable definition of an environment. It is **not** running. It
builds into a Docker image.

Fields the user cares about: `lab_id` (slug, is the primary key), `title`,
`description`, `frappe_version` (version-14 / version-15 / version-16 /
develop), `apps` (child table of app name, label, git URL, branch),
`memory_limit`, `cpu_cores`, `iops_limit`, `bps_limit`, `pids_limit`,
`enable_ssh`, `enable_code_server`, `shell`, `image_tag`.

**Status: `Draft` → `Building` → `Ready` → `Error`**

### Bench Instance — *the running container*

One live container built from a Lab. A Lab can have several over its life.
This is the object a User actually cares about day to day.

Fields: `bench_name`, `lab`, `frappe_version`, `site_name`, `domain`,
`container_id`, `container_image`, `container_ip`, `started_at`,
`ssh_username`, `ssh_password`, `admin_password`, `code_server_url`,
`code_server_password`, `wg_ip`, `vpn_peer`, `database_server`,
`cpu_usage` (%), `memory_usage` (%), `container_health`, `last_health_check`.

**Status: `Draft` → `Deploying` → `Running` → `Stopped` → `Error`**
**Health: `Healthy` / `Unhealthy` / `Unknown`** (separate axis from status)

Note: `container_health` is a *second* status axis. A bench can be `Running`
but `Unhealthy`. The current UI never shows this. It should.

### Bench Site — *the Frappe site inside the bench*

Fields: `site_name`, `bench`, `admin_password`,
`apps_installed`.

**Status: `Creating` → `Active` → `Inactive` → `Error`**

### Database Server — *shared MariaDB container*

Infrastructure, admin-only concern. Fields: `container_name`,
`mariadb_version`, `port`, `container_ip`, `memory_limit`, `volume_name`,
`error_message`.

**Status: `Pending` → `Active` → `Stopped` → `Error`**

### Build Log / Deploy Log — *streamed output*

Append-only lines with a `log_type` of `info`, `success`, `error`, `warning`,
or `step`. Build Log belongs to a Lab; Deploy Log belongs to a Bench Instance.
Both stream live over socket.io (`lab_build_log`, `bench_deploy_log`).

### VPN Device / Peer

A user's laptop or phone registered on WireGuard. Fields: `device_name`,
`device_type`, `wg_ip`, `status`, `wg_rx_bytes`, `wg_tx_bytes`. Users download
a WireGuard config; the frontend already ships the `qrcode` package to render
it as a scannable QR.

### Lab Template — *canned recipes*

Seven ship in code (`benchpress/lab_templates.py`), catalog version 3:

| Template | Frappe | RAM | CPU | Apps |
|---|---|---|---|---|
| Frappe Framework | version-15 | 512m | 1 | — |
| ERPNext | version-15 | 2g | 2 | erpnext |
| Frappe CRM | version-15 | 1g | 1 | crm |
| Frappe HR | version-15 | 2g | 2 | hrms |
| Frappe Learning | version-15 | 1g | 1 | lms |
| Frappe Helpdesk | version-15 | 1g | 1 | helpdesk |
| ERPNext + India Compliance | version-15 | 2g | 2 | erpnext, india_compliance |

These are the best onboarding surface in the product and are currently buried
behind a secondary "From Template" button.

### BenchPress Settings — *singleton*

`base_domain`, `default_image`, `docker_socket`, `traefik_network`,
`container_memory_limit`, `container_cpu_quota`, `code_server_version`.

---

## 4. The deploy pipeline

Deploying is the product's centrepiece and takes minutes. These are the real
steps emitted by `benchpress/deploy_manager.py`, in order. This *is* a
sequence, so a numbered stepper is warranted here (and only here).

1. Check shared infrastructure (MariaDB + Redis reachable)
2. Build the lab image — or reuse the cached image
3. Create the container
4. Wait for the container to report running with an IP
5. Write `common_site_config.json`
6. Create the site (`bench new-site`)
7. Build assets
8. Provision the SSH user
9. Provision code-server
10. Configure the WireGuard VPN peer
11. Deploy complete

On failure the pipeline cleans up (removes the container it created, removes
the VPN peer) and writes an `error` line. Steps 2, 6 and 7 are the slow ones —
minutes each on a cold build.

Today this is a raw scrolling log. It should be a stepper with per-step state,
elapsed time, and the log collapsed underneath.

---

## 5. Screens that exist today

Nine routes, Vue Router, `/frontend` base path. `*` = admin-only.

| Route | Page | What it does |
|---|---|---|
| `/` and `/labs` | Labs | Table of all labs. Search + status filter + version filter. |
| `/labs/new` * | New Lab | Long form: identity, resources, app rows |
| `/labs/templates` * | Lab Templates | The 7 canned recipes |
| `/labs/:labId` | Lab Detail | Tabs: Dashboard, Sites, Deploy Log*. 1,001 lines. |
| `/bench-instances` | Bench Instances | Table of running containers |
| `/devices` | VPN Devices | Card grid; add device, download config |
| `/deploy-logs` | Deploy Logs | Flat log list |
| `/build-logs` * | Build Logs | Flat log list |
| `/settings` * | Settings | The singleton form |

Shell: frappe-ui `Sidebar` on the left with sections — *(Labs, Templates\*,
Bench Instances, VPN Devices)*, *Logs (Deploy Logs, Build Logs\*)*,
*Settings\**. Header has app title, current user, and a menu with Switch to
Desk\*, Toggle Theme, Logout.

**Lab Detail** is the most important screen and the most overloaded. Header
carries title, lab ID, description, and three badges (version, RAM, CPU). The
primary action button is contextual: Build Image / Deploy / Open VS Code /
Stop. Dashboard tab currently holds: Lab Information card, Container Status
card with CPU and Memory bars, and a Connection Information card with device
IP, SSH credentials and code-server link.

---

## 6. Screens that do not exist and should

- **Dashboard / overview.** There is no landing page. `/` redirects to a table.
- **Onboarding.** No first-run guidance anywhere.
- **Deploy progress.** The 11-step pipeline has no visual representation.
- **Activity feed.** No "what happened recently" across labs.
- **Health view.** `container_health` is collected and never displayed.

---

## 7. Journeys to design for

**A. Admin, first hour.** Fresh install → set base domain in Settings → pick
ERPNext from templates → build image (slow, needs progress) → deploy (slow,
needs progress) → site is live → hand the URL and credentials to a developer.

**B. Developer, every morning.** Log in → see my environments and whether they
are running → click one → open VS Code or open the site → work → stop it at
the end of the day to free resources.

**C. First-time device setup.** Register laptop → get WireGuard config, as file
or QR → connect → confirm the lab is now reachable. This is the step most
likely to strand a new user, because until VPN is up, nothing is reachable and
the app gives no feedback about it.

**D. A build failed.** See the Error state → understand *which* step failed →
read the relevant log lines → fix the git URL or branch → rebuild.

---

## 8. Known problems to solve

Audited against the live app on 2026-08-16.

1. **Status has no colour.** `Ready`, `Building`, `Error` all render as
   identical grey text in the Labs table. It is the most important column and
   carries the least visual weight. `Badge` with a theme is already available.
2. **No orientation.** A new user's first screen is a bare table with no
   explanation of what a "Lab" is or what to do next.
3. **Wrong columns.** The Labs table spends two columns on `Memory 512m` and
   `CPU 1` — values nobody scans — and omits whether the lab is deployed, its
   site URL, and when it last ran.
4. **Empty states are a sentence.** "No labs found." with no call to action.
5. **Destructive action is the loudest element.** On Lab Detail, a solid red
   `Stop` button top-right is the highest-contrast thing on the page. The
   primary action should be *Open Site*; Stop and Delete belong in an
   overflow menu behind confirmation.
6. **Duplicate content.** The "Lab Information" card repeats the description
   already shown in the header, and is otherwise near-empty.
7. **Two status axes collapsed into one.** Bench status and container health
   are independent and only one is shown.
8. **Secrets are plain text.** SSH password, admin password and code-server
   password sit on the Connection Information card. They need a masked state
   with reveal and copy.
9. **Lab Detail is one 1,001-line file.** Not a design problem directly, but
   the mockups should be structured as separable regions so the split is clean.

---

## 9. Constraints the mockups must respect

**Stack.** Vue 3, Vite, `frappe-ui@0.1.270` (bump to `0.1.278` pending),
Tailwind CSS 3. Icons: `lucide` via `~icons/lucide/*` and `feather-icons`.
Font: Inter, shipped locally.

**Design tokens.** frappe-ui's Espresso system. Use its semantic classes, not
raw Tailwind colours: `text-ink-gray-9` / `-7` / `-6` / `-5` for text,
`bg-surface-white` / `bg-surface-gray-1` / `-2` for surfaces,
`border-outline-gray-1` for rules. Dark mode switches on a `data-theme`
attribute on `<html>` and must keep working.

**Components available in frappe-ui** (verified in the installed package —
mockups may use any of these and should not invent others):

Alert, Autocomplete, Avatar, Badge, Breadcrumbs, Button, Calendar, Card,
Charts (AxisChart, DonutChart, FunnelChart, NumberChart), Checkbox,
CircularProgressBar, Combobox, CommandPalette, ConfirmDialog, DatePicker,
Dialog, Divider, Dropdown, ErrorMessage, FeatherIcon, FileUploader,
FormControl, FormLabel, Input, ItemList, KeyboardShortcut, ListFilter,
ListItem, ListView, LoadingIndicator, LoadingText, MonthPicker, MultiSelect,
Password, Popover, Progress, Rating, Select, Sidebar, Slider, Spinner, Switch,
TabButtons, Tabs, TextEditor, TextInput, Textarea, TimePicker, Toast, Tooltip,
Tree, VueGridLayout.

Notably already available and unused: **the four chart types**, `Progress`,
`CircularProgressBar`, `CommandPalette`, `Breadcrumbs`, `ConfirmDialog`,
`Password`, `Tooltip`, `ListFilter`, `VueGridLayout`.

**Data layer.** `createResource`, `createListResource`,
`createDocumentResource` from frappe-ui handle fetching, auth, permissions and
mutations. Every mockup's data should map to one of these. Live log streaming
comes over socket.io, not polling.

**Reference point.** Frappe Cloud (`frappe/press`) is the closest well-designed
comparable and is built on the same frappe-ui. It is a reasonable source of
patterns for site lists, deploy progress and resource cards.

---

## 10. What good looks like

A developer who has never seen BenchPress should be able to, without asking
anyone:

- Say what the product does, from the first screen
- Tell at a glance which environments are running, broken, or building
- Get from zero to a deployed ERPNext site using a template
- Know what to do when a build fails
- Connect a device to the VPN and confirm it worked

None of that requires a new component library. All of it requires information
architecture, status legibility, progress feedback, and empty-state guidance.
