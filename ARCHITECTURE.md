# BenchPress — Architecture & Code Flow Guide

> "Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured."

## What BenchPress Does

BenchPress automates the entire Frappe bench lifecycle through a web UI:
1. **Define** a Lab (template) with Frappe version, apps, and resource limits
2. **Build** a Docker image from the Lab
3. **Deploy** a containerized Frappe bench from that image
4. **Connect** via WireGuard VPN to SSH into the bench
5. **Manage** sites, apps, and resources inside the bench

---

## Directory Structure

```
apps/benchpress/
├── benchpress/
│   ├── hooks.py               # App config, scheduler, routes
│   ├── api.py                 # REST API (~20 endpoints)
│   ├── lifecycle.py           # Bench transitions: running, and the deploy that reaches it
│   ├── deploy_manager.py      # Image building, site creation, stop and teardown
│   ├── docker_manager.py      # Docker SDK wrapper
│   ├── vpn_adapter.py         # Seam to the vpn_management VPN plane
│   ├── stats_collector.py     # Container stats cron job
│   ├── lab-templates/         # Dockerfile & shell scripts
│   │   ├── Dockerfile         # 5-layer cached image build
│   │   ├── entry.sh           # Container entrypoint
│   │   ├── create-site.sh     # Site creation during build
│   │   ├── setup-site.sh      # Site creation post-deploy
│   │   └── install-apps.sh    # App installation script
│   └── benchpress/doctype/    # 9 DocTypes (data model)
└── frontend/                  # Vue 3 SPA (frontend)
    └── src/
        ├── main.js            # App bootstrap
        ├── router/index.js    # Routes
        ├── pages/             # 8 pages
        └── components/        # Shared UI components
```

---

## DocTypes (Data Model)

| DocType | Purpose | Key Fields |
|---------|---------|------------|
| **Lab** | Reusable template | `lab_id`, `title`, `frappe_version`, `status` (Draft/Building/Ready/Error), `image_tag`, `memory_limit`, `cpu_cores` |
| **Lab App** | Child of Lab | `app_name`, `git_url`, `branch` |
| **Bench Instance** | Running container | `bench_name`, `lab`, `status` (Draft/Deploying/Running/Stopped/Error), `container_id`, `wg_ip`, `vpn_peer` (Link to VPN Peer), `cpu_usage`, `memory_usage` |
| **Bench App** | Child of Bench Instance | `app_name`, `git_url`, `branch` |
| **Bench Site** | Frappe site in a bench | `site_name`, `bench`, `status`, `admin_password` |
| **Site App** | Child of Bench Site | `app_name`, `app_label` |
| **BenchPress Settings** | Global config (singleton) | `docker_socket`, `base_domain`, `container_memory_limit`, `container_cpu_quota` |
| **Deploy Log** | Deployment event logs | `bench`, `message`, `log_type`, `timestamp` |
| **Build Log** | Image build logs | `lab`, `message`, `log_type`, `timestamp` |
| **VPN Peer** (vpn_management) | VPN identity for benches and user devices — owned by the vpn_management app (with WireGuard Server, Network Pool, IP Allocation) | `peer_name` (device type encoded as a `[Laptop] ` prefix for devices), public key, assigned IP |

---

## Backend Files — What Each Does

### `api.py` (~300 lines) — REST API Layer

All endpoints use `@frappe.whitelist()`. Long-running ops are enqueued to the `"long"` queue.

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `get_labs()` | GET | List all labs with app_count, bench_count |
| `get_lab(name)` | GET | Single lab with apps list |
| `build_lab_image(lab_name)` | POST | Enqueue background Docker image build |
| `get_benches()` | GET | All benches with CPU/memory stats |
| `create_bench(data)` | POST | Create bench from lab, enqueue deploy |
| `bench_action(bench_name, action)` | POST | start / stop / restart / delete |
| `get_deploy_logs(bench_name)` | GET | Last 100 deploy log entries |
| `create_site(data)` | POST | Create site, enqueue setup in container |
| `add_device(data)` | POST | Register a persistent VPN device (wrapper over a vpn_management VPN Peer, via `vpn_adapter`) |
| `remove_device(device_name)` | POST | Remove a VPN device — deletes its VPN Peer |
| `list_devices()` | GET | List the current user's device VPN Peers |
| `get_device_wg_config(device_name)` | GET | WireGuard client .conf for a device (routes only the pool subnet `172.27.0.0/16`) |

### `deploy_manager.py` (302 lines) — Orchestration

This is the **brain** of BenchPress. It coordinates builds and deployments.

**Key functions:**

| Function | Called By | What It Does |
|----------|-----------|--------------|
| `build_lab(lab_name)` | Background job from `build_lab_image` API | Builds Docker image for a Lab. Creates Build Log doc, streams logs via WebSocket (`lab_build_log` event). Sets Lab status to Ready or Error. |
| `lifecycle.deploy_bench(bench_name)` | Background job from `create_bench` API | **Main deploy pipeline**: check image → remove stale container → create container → start → register VPN Peer + configure container tunnel (via `vpn_adapter`) → set SSH password → mark Running |
| `lifecycle.stopped(bench_name)` | Background job from `bench_action` | Stop container |
| `lifecycle.redeploy_bench(bench_name)` | Background job from `bench_action` | Stop + remove container, reset to Draft, call deploy_bench |
| `log_deploy(bench_name, msg, type)` | Internal helper | Saves Deploy Log + publishes `bench_deploy_log` WebSocket event |

### `docker_manager.py` (191 lines) — Docker SDK Wrapper

Talks to Docker Engine via Python SDK.

| Function | What It Does |
|----------|--------------|
| `get_client()` | Returns Docker client (reads socket URL from Settings) |
| `build_lab_image(lab_doc, ...)` | Builds image from `lab-templates/Dockerfile`. Tag: `benchpress/{lab_id}:latest`. Streams build logs. |
| `create_bench_container(bench_doc, lab_doc)` | Creates container with: named volume, CPU/memory limits, privileged mode, `benchpress` network. Does NOT start it. |
| `start_container(id)` | Starts a stopped container |
| `stop_container(id)` | Stops with 30s timeout |
| `restart_container(id)` | Restart with 30s timeout |
| `remove_container(id)` | Force remove + volumes |
| `exec_in_container(id, cmd)` | Run bash command inside container (as frappe user) |
| `write_file_to_container(id, content, path)` | Write file via heredoc in bash |
| `get_container_stats(id)` | Returns `{cpu_percent, memory_percent, memory_usage_mb}` |

### `vpn_adapter.py` (209 lines) — Seam to the vpn_management VPN Plane

Thin adapter over the **vpn_management** app, which owns everything VPN (WireGuard Server, Network Pool, VPN Peer, IP Allocation, and the privileged wg-agent sidecar — the only thing allowed to run `wg`). BenchPress never runs WireGuard commands itself.

| Function | What It Does |
|----------|--------------|
| `create_container_peer(bench)` | Generate keypair locally, register a VPN Peer (insert atomically claims an IP from the pool). Private key is never persisted |
| `remove_bench_peer(bench)` | Delete the bench's VPN Peer (frees its IP allocation) |
| `configure_container(container_id, private_key, assigned_ip)` | Write `wg0.conf` into the container and run `wg-quick up wg0` inside it |
| `register_device(device_name, device_type, ...)` | Create a device VPN Peer (device type encoded as a `[Laptop] ` prefix on `peer_name`) |
| `unregister_device(device_docname)` | Delete a device VPN Peer |
| `list_devices()` | List the current user's device VPN Peers |
| `get_device_config(device_docname)` | Render the device's client .conf (AllowedIPs = pool subnet only) |

### `stats_collector.py` (51 lines) — Cron Job

Runs every minute. Polls Docker stats (CPU/memory/health) for all running benches, updates `cpu_usage` and `memory_usage` fields on Bench Instance docs. VPN rx/tx counters are polled by vpn_management's own `poll_status` job.

### `hooks.py` (39 lines) — App Configuration

- Registers `/frontend/<path>` route for Vue SPA
- Schedules stats collector cron
- Sets `ignore_links_on_delete` for Deploy Log and Build Log

---

## Docker Build Pipeline (`lab-templates/`)

The Dockerfile uses **5 cached layers**:

```
Layer 1: System dependencies
         apt-get: mariadb-server, redis-server, openssh-server, wireguard-tools, git, node, yarn

Layer 2: Service configuration
         SSH setup, sudoers for frappe user, directory creation

Layer 3: bench init
         bench init --frappe-branch {version} /home/frappe/frappe-bench

Layer 4: Install apps (install-apps.sh)
         For each app in APPS_JSON: bench get-app --branch {branch} {git_url}

Layer 5: Create site (create-site.sh)
         bench new-site {site_name} --admin-password {password}
         bench --site {site_name} install-app {each_app}
```

**Container entrypoint** (`entry.sh`): Starts MariaDB, Redis, SSH, then `tail -f /dev/null` to keep alive.

**Site creation on deploy** (`setup-site.sh`): the deploy execs this inside the new container,
and it takes one of three paths.

| Path | When | Cost on a CRM lab |
|------|------|-------------------|
| **Adopt** | The container already has `sites/<site>/site_config.json` — a redeploy that kept its data | Re-sets the admin password, nothing else |
| **Restore** | The image carries `/opt/benchpress/golden/site.sql.gz` and the deploy allows it | `bench new-site --source-sql`, **9.1 s** |
| **Create** | Anything else | `bench new-site` plus `install-app` per app, **37.2 s** |

The golden dump is baked by `benchpress/golden.py` at the end of every image build: it runs the
lab's site once in a throwaway container, dumps that database, restores the dump into a scratch
database to prove it before trusting it, and appends one `FROM <tag>` + `COPY` layer to the tag
the build just produced. It never rebuilds the image.

Two switches in **BenchPress Settings** govern it, and they are separate on purpose:
`enable_golden_images` decides whether a build bakes one, `restore_from_golden` whether a deploy
reads one. A host that turns baking off keeps restoring from the images it already has.

`deploy_manager._golden_matches_server` is the last gate. The dump is the one artefact in an
image whose validity depends on something outside it, so a deploy compares the MariaDB **major**
version the dump came from against the server it is restoring into and takes the create path
with the reason in the log when they differ. A patch-level difference is not a mismatch —
refusing on one would take every golden on the host out of service on a routine server update.

---

## Frontend (Vue 3 Dashboard)

**Tech**: Vue 3 + Vite + TailwindCSS + frappe-ui + socket.io (via doppio)

### Pages

| Page | Route | What It Shows |
|------|-------|---------------|
| **Labs** | `/labs` | Searchable list of lab templates with status/version filters |
| **NewLab** | `/labs/new` | Form to create a lab with apps |
| **LabDetail** | `/labs/:labId` | Tabbed: Dashboard, Sites, Deploy/Build Log. Confirmation dialogs for Deploy/Stop |
| **BenchInstances** | `/bench-instances` | Table of all bench containers with status, IP, CPU/memory |
| **DeployLogs** | `/deploy-logs` | Deploy log list with expandable entries |
| **BuildLogs** | `/build-logs` | Build log list with expandable entries |
| **Devices** | `/devices` | VPN device management: add, remove, download config |
| **Settings** | `/settings` | Global settings dialog using createDocumentResource |

### Components

| Component | Purpose |
|-----------|---------|
| **DeployPipeline** | The eleven deploy steps, their state and their durations, derived from the log |
| **DeployStepRow** | One deploy step with its status and elapsed time |
| **RawLogPanel** | The unparsed deploy log, with a download |
| **LogViewer** | Parses raw logs into collapsible steps (build logs, which have no steps of ours) |
| **LogStep** | Single log step with status indicator |
| **CodeServerDialog** | The IDE password, surfaced at the moment the IDE tab is opened |

### Real-Time Communication

The frontend listens for WebSocket events published by the backend:

- **`bench_deploy_log`** — During deployment, appended to LabDetail's live buffer and rendered by `DeployPipeline` / `DeployStepRow` / `RawLogPanel`
- **`lab_build_log`** — During image build, triggers LabsPage refresh

Pattern:
```python
# Backend publishes
frappe.publish_realtime("bench_deploy_log", message={...}, after_commit=False)
```
```javascript
// Frontend listens
this.$socket.on("bench_deploy_log", (data) => { this.logs.push(data) })
```

---

## Shell Access — Where the Terminal Actually Is

There is **no web terminal in this app**: no `ttyd`, no `xterm.js`, no PTY endpoint. A user gets a shell
in exactly two ways, both over the WireGuard tunnel:

1. **SSH** — `ssh <ssh_username>@<wg_ip>` with the SSH password from Connection details. `linkuser.sh`
   renames the image's `frappe` user to the lab's own username, sets the password, grants passwordless
   `sudo` for `bench`/`supervisord`/`supervisorctl`/`service` only, and appends the nvm node path plus
   `frappe-bench/env/bin` to its `.bashrc` — so `bench` resolves on login with no PATH fix.
2. **The terminal inside code-server** — `restart.sh` launches code-server against
   `/home/<ssh_username>/frappe-bench`, so its integrated terminal opens in the bench directory as the
   same user, with the same PATH.

The deploy log is not a terminal either. It is a stored `Deploy Log` document plus a `bench_deploy_log`
socket stream, rendered by the components in the table above.

The terminal windows in [site/index.html](site/index.html) and `www/home.html` are **marketing mockups** —
static markup of a session that is not running anywhere.

## Complete Workflow: Lab → Bench → SSH

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CREATE LAB                                               │
│    User defines: Frappe version, apps[], CPU/memory limits  │
│    Status: Draft                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. BUILD IMAGE                                              │
│    api.build_lab_image() → enqueue deploy_manager.build_lab │
│    Status: Building → Ready (or Error)                      │
│    Docker image: benchpress/{lab_id}:latest                 │
│    Logs streamed via WebSocket → Build Log doc              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. DEPLOY BENCH                                             │
│    api.create_bench() → enqueue lifecycle.deploy_bench      │
│    Status: Deploying                                        │
│    Pipeline:                                                │
│      a. Check image exists (build if not)                   │
│      b. Remove stale container                              │
│      c. docker_manager.create_bench_container()             │
│      d. docker_manager.start_container()                    │
│      e. vpn_adapter: register VPN Peer (vpn_management      │
│         claims IP), write wg0 conf into container           │
│      f. Set SSH password                                    │
│    Status: Running                                          │
│    Logs streamed via WebSocket → Deploy Log doc             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ACCESS VIA WIREGUARD                                     │
│    User downloads .conf file from Bench Detail page         │
│    Imports into WireGuard client                            │
│    Direct tunnel to the container's wg0:                    │
│      172.27.0.X:22   (SSH)                                  │
│      172.27.0.X:8000 (Frappe web)                           │
│      172.27.0.X:9000 (WebSocket)                            │
│    ssh frappe@172.27.0.X                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. MANAGE SITES                                             │
│    api.create_site() → enqueue → exec setup-site.sh         │
│    Inside container: bench new-site, install apps           │
│    Access: http://172.27.0.X:8000                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Patterns

| Pattern | Usage |
|---------|-------|
| `@frappe.whitelist()` | All API endpoints |
| `frappe.enqueue(..., queue="long", timeout=3600)` | Long-running builds/deploys |
| `frappe.publish_realtime(event, message, after_commit=False)` | Live log streaming |
| `frappe.parse_json(data)` | Input parsing (never `json.loads`) |
| `frappe.get_cached_doc(doctype, name)` | Cached reads |
| `createDocumentResource` | Settings, Lab detail fetch |
| `createListResource` | Labs list, Bench list, Sites, Build logs |
| `ignore_links_on_delete` | Deploy Log, Build Log (safe to delete parent) |

## Networking

- **Docker network**: `benchpress` (172.30.0.0/24)
- **VPN pool**: 172.27.0.0/16 (vpn_management Network Pool `pool-wg0`), WireGuard port 44556, owned by the vpn_management app
- **VPN access**: direct tunnel to the container's `wg0` — ports 22 (SSH), 8000 (Frappe web), 8080 (code-server), 9000 (Frappe WebSocket)
- **code-server binds `0.0.0.0:8080` with `cert: false`** (`deploy_manager._start_code_server`), so it is
  plaintext HTTP on every interface of the container — including the shared `benchpress` bridge, not only
  the WireGuard address. Its password is the only control. That holds while WireGuard is the sole ingress;
  it is a prerequisite to fix before [#129](https://github.com/Venkateshvenki404224/benchpress/issues/129)
  puts a public hostname in front of it.
- **Container volumes**: `benchpress-{bench_name}-data` → `/home/frappe`
- **No component may assume a port can be opened inward to a bench host.** Control flows
  outward. Every bench-running process connects out to Redis and MariaDB, `lease.stop_queue_for`
  ([lease.py:325](benchpress/credits/lease.py#L325)) addresses a node by queue name and never by
  host, and `lease.assert_local` ([lease.py:336](benchpress/credits/lease.py#L336)) refuses a
  command that reached the wrong daemon. `BenchPress Settings.docker_socket` holds a **local**
  socket path (`unix:///var/run/docker.sock`), read at
  [docker_manager.py:132](benchpress/docker_manager.py#L132). Pointing it at a `tcp://` address on
  another host is the one edit that breaks the rule.
- **No secret may reach a `docker exec` command line, a healthcheck command line, or a file
  written through an exec.** Pass it as `environment=`, send a hash the server accepts, or upload
  it with `put_archive`. Docker publishes every exec command into its event stream in full and
  untruncated, and publishes no environment at all, so anything on that line is readable by
  anything holding the socket. A sentinel test guards each site
  ([test_docker_manager.py](benchpress/tests/test_docker_manager.py),
  [test_vpn_adapter.py](benchpress/tests/test_vpn_adapter.py),
  [test_mariadb_manager.py](benchpress/tests/test_mariadb_manager.py),
  [test_deploy_manager.py](benchpress/tests/test_deploy_manager.py)). Base64 is not a defence:
  `mariadb_manager.execute_sql` encodes its script and the encoding is on the line too.
