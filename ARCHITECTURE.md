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
│   ├── deploy_manager.py      # Build & deploy orchestration
│   ├── docker_manager.py      # Docker SDK wrapper
│   ├── wg_manager.py          # WireGuard VPN management
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
| **Bench Instance** | Running container | `bench_name`, `lab`, `status` (Draft/Deploying/Running/Stopped/Error), `container_id`, `wg_ip`, `wg_config`, `cpu_usage`, `memory_usage` |
| **Bench App** | Child of Bench Instance | `app_name`, `git_url`, `branch` |
| **Bench Site** | Frappe site in a bench | `site_name`, `bench`, `status`, `full_domain`, `admin_password` |
| **Site App** | Child of Bench Site | `app_name`, `app_label` |
| **BenchPress Settings** | Global config (singleton) | `docker_socket`, `wg_server_*` keys, `base_domain`, `next_wg_ip` |
| **Deploy Log** | Deployment event logs | `bench`, `message`, `log_type`, `timestamp` |
| **Build Log** | Image build logs | `lab`, `message`, `log_type`, `timestamp` |
| **VPN Device** | Persistent VPN device | `device_name`, `device_type`, `owner`, `wg_public_key`, `wg_ip`, `wg_config` |

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
| `add_device(data)` | POST | Register a persistent VPN device |
| `remove_device(device_name)` | POST | Remove a VPN device and its peer |
| `list_devices()` | GET | List all VPN devices for the current user |
| `get_device_wg_config(device_name)` | GET | WireGuard client .conf for a device |

### `deploy_manager.py` (302 lines) — Orchestration

This is the **brain** of BenchPress. It coordinates builds and deployments.

**Key functions:**

| Function | Called By | What It Does |
|----------|-----------|--------------|
| `build_lab(lab_name)` | Background job from `build_lab_image` API | Builds Docker image for a Lab. Creates Build Log doc, streams logs via WebSocket (`lab_build_log` event). Sets Lab status to Ready or Error. |
| `deploy_bench(bench_name)` | Background job from `create_bench` API | **Main deploy pipeline**: check image → remove stale container → create container → start → setup WireGuard → set SSH password → mark Running |
| `stop_bench(bench_name)` | Background job from `bench_action` | Stop container, remove WireGuard routing |
| `redeploy_bench(bench_name)` | Background job from `bench_action` | Stop + remove container, reset to Draft, call deploy_bench |
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

### `wg_manager.py` (211 lines) — WireGuard VPN

Manages VPN tunnels so users can SSH into bench containers.

| Function | What It Does |
|----------|--------------|
| `generate_keypair()` | Generate WG private/public key pair |
| `allocate_ip()` | Assign next IP from 10.10.0.2–254 pool |
| `add_peer_to_server(pubkey, ip)` | Add peer to wg0 interface |
| `remove_peer_from_server(pubkey)` | Remove peer from wg0 |
| `generate_peer_config(...)` | Generate client .conf file |
| `setup_wg_routing(wg_ip, container_id)` | Add DNAT rules: ports 22, 8000, 9000 → container IP |
| `remove_wg_routing(wg_ip, container_id)` | Remove DNAT rules |
| `setup_wg_server()` | One-time server setup (create wg0, enable IP forwarding) |
| `ensure_wg_running()` | Start wg0 if not running |

### `stats_collector.py` (35 lines) — Cron Job

Runs every 2 minutes. Polls Docker stats for all running benches, updates `cpu_usage` and `memory_usage` fields on Bench Instance docs.

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

**Post-deploy site creation** (`setup-site.sh`): Used when creating additional sites in a running container.

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
| **LogViewer** | Parses raw logs into collapsible steps |
| **LogStep** | Single log step with status indicator |

### Real-Time Communication

The frontend listens for WebSocket events published by the backend:

- **`bench_deploy_log`** — During deployment, streamed to DeployPage's Terminal component
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
│    api.create_bench() → enqueue deploy_manager.deploy_bench │
│    Status: Deploying                                        │
│    Pipeline:                                                │
│      a. Check image exists (build if not)                   │
│      b. Remove stale container                              │
│      c. docker_manager.create_bench_container()             │
│      d. docker_manager.start_container()                    │
│      e. wg_manager: allocate IP, add peer, setup routing    │
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
│    DNAT routes:                                             │
│      10.10.0.X:22   → container:22   (SSH)                 │
│      10.10.0.X:8000 → container:8000 (Frappe web)          │
│      10.10.0.X:9000 → container:9000 (WebSocket)           │
│    ssh frappe@10.10.0.X                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. MANAGE SITES                                             │
│    api.create_site() → enqueue → exec setup-site.sh         │
│    Inside container: bench new-site, install apps           │
│    Access: http://10.10.0.X:8000                            │
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
- **WireGuard subnet**: 10.10.0.0/24 (server: 10.10.0.1, clients: 10.10.0.2–254)
- **DNAT ports**: 22 (SSH), 8000 (Frappe web), 9000 (Frappe WebSocket)
- **Container volumes**: `benchpress-{bench_name}-data` → `/home/frappe`
