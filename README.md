<div align="center">

<img src="benchpress/public/images/logo/logo.png" alt="BenchPress Logo" width="80" />

# BenchPress

**Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Frappe Framework](https://img.shields.io/badge/Built%20on-Frappe%20v16-blue)](https://frappeframework.com)
[![FOSS Hack 2026](https://img.shields.io/badge/FOSS%20Hack-2026-orange)](https://fossunited.org)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-3776AB.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3-4FC08D.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Powered-2496ED.svg)](https://docker.com)
[![WireGuard](https://img.shields.io/badge/WireGuard-VPN-88171A.svg)](https://wireguard.com)

</div>

---

## The Problem

Setting up a Frappe/ERPNext development environment is painful:

1. **Manual setup** -- Install bench CLI, MariaDB, Redis, Node.js, wkhtmltopdf, and a dozen other dependencies
2. **Dependency conflicts** -- Different projects need different Frappe versions and your OS gets polluted
3. **No isolation** -- One broken bench can affect everything on your machine
4. **No remote access** -- Team members cannot SSH into each other's dev environments
5. **Repetitive work** -- Every new project means repeating the same 30-minute setup ritual

There is no simple way to say *"Give me a fresh Frappe bench with ERPNext and HRMS"* and have it running in minutes.

## The Solution

BenchPress is a **self-hosted Frappe Cloud alternative** built entirely as a Frappe app. It automates the entire bench lifecycle through a modern web UI:

1. **Create a Lab** -- Define a reusable template with your desired Frappe apps (CRM, ERPNext, HRMS, LMS, Helpdesk, Wiki, etc.), the Frappe version, and resource limits (CPU, memory)
2. **Build once** -- Docker image with all apps baked in via a 5-layer cached Dockerfile, rebuilt only when configuration changes
3. **Deploy in clicks** -- Each bench runs in its own Docker container with MariaDB, Redis, SSH, and all services included
4. **SSH via WireGuard** -- Secure kernel-level VPN access into any container, no exposed ports on the public internet
5. **Real-time logs** -- Watch Docker image builds and container deployments stream live in the browser via WebSocket
6. **Manage everything** -- Start, stop, restart, delete benches. Create multiple Frappe sites per bench. Monitor CPU and memory usage in real time.

---

## Architecture

```
                              +---------------------------+
                              |       User's Browser      |
                              |  Vue 3 SPA (frappe-ui)    |
                              +-------------+-------------+
                                            |
                                   HTTPS / WebSocket
                                            |
                              +-------------v-------------+
                              |      Frappe Web Server     |
                              |  (BenchPress Frappe App)   |
                              |                            |
                              |  api.py ---- REST API      |
                              |  hooks.py -- Scheduler     |
                              |  wg_manager -- WireGuard   |
                              +---+--------+----------+---+
                                  |        |          |
                   +--------------+   +----v----+  +--v--------------+
                   |                  |  Redis   |  | deploy_manager  |
                   |                  |  Queue   |  | (Background     |
                   |                  |  (RQ)    |  |  Workers)       |
                   |                  +----+-----+  +--+---------+---+
                   |                       |           |         |
            +------v------+         +------v------+    |   +-----v--------+
            |  WireGuard  |         |   Docker    |<---+   | stats_       |
            |  (wg0)      |         |   Engine    |        | collector    |
            |  10.10.0.0  |         |   (SDK)     |        | (cron 2min) |
            |  /24 subnet |         +------+------+        +--------------+
            +------+------+                |
                   |              +--------v---------+
                   |              |  benchpress       |
                   |              |  Docker Network   |
                   |              |  172.30.0.0/24    |
                   |              +---+-----+-----+--+
                   |                  |     |     |
               DNAT Routing     +-----v-+ +-v---+ +v-------+
               (iptables)       | Bench | |Bench| | Bench  |
               22,8000,9000     | Ctr 1 | |Ctr 2| | Ctr N  |
                   |            |       | |     | |        |
                   +----------->| MariaDB| |MariaDB|MariaDB|
                                | Redis | |Redis| | Redis  |
                                | SSH   | |SSH  | | SSH    |
                                | Frappe| |Frappe| | Frappe |
                                +-------+ +-----+ +--------+
```

### How the Pieces Fit Together

| Component | Role |
|-----------|------|
| **Frappe Web Server** | Hosts the BenchPress app, serves the Vue 3 SPA, handles REST API calls, and publishes real-time WebSocket events |
| **Redis Queue (RQ)** | Processes long-running background jobs: Docker image builds (up to 60 min) and container deployments |
| **Docker Engine** | Builds images from the 5-layer Dockerfile template, creates and manages containers with CPU/memory limits |
| **WireGuard (wg0)** | Kernel-level VPN on the host. Each bench gets a unique IP (10.10.0.X). iptables DNAT rules route ports 22, 8000, and 9000 from the WG IP to the container |
| **Stats Collector** | Cron job running every 2 minutes that polls Docker stats API for all running containers and updates CPU/memory metrics |
| **Each Container** | A self-contained Frappe bench with MariaDB, Redis, SSH server, and all pre-installed apps. Users SSH in and run `bench start` |

---

## Container Lifecycle

```
  CREATE LAB            BUILD IMAGE              DEPLOY BENCH                ACCESS
  (Template)           (Docker Build)          (Container + VPN)          (SSH + Web)
 +-----------+     +------------------+     +---------------------+     +-------------+
 |           |     |                  |     |                     |     |             |
 | Lab ID    |     | Layer 1: apt     |     | 1. Check image      |     | WireGuard   |
 | Frappe v  +---->| Layer 2: SSH     +---->| 2. Create container +---->| client .conf|
 | Apps[]    |     | Layer 3: bench   |     | 3. Start container  |     |             |
 | CPU/Mem   |     | Layer 4: apps    |     | 4. Setup WireGuard  |     | ssh frappe@ |
 |           |     | Layer 5: site    |     | 5. Set SSH password |     | 10.10.0.X   |
 +-----------+     +------------------+     +---------------------+     +-------------+
   Status:            Cached layers            Logs streamed via          Ports:
   Draft              rebuild only             WebSocket in               22   -> SSH
                      when config              real-time                  8000 -> Web
                      changes                                             9000 -> Socket.io
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.14 + Frappe Framework v16 | REST API, background jobs, ORM, permissions |
| **Frontend** | Vue 3 + Vite + TailwindCSS + frappe-ui | Modern SPA dashboard with real-time updates |
| **Containers** | Docker Engine (Python SDK) | Image builds, container lifecycle, resource limits |
| **VPN** | WireGuard (kernel-level) | Secure SSH/web access to containers without exposed ports |
| **Database** | MariaDB (per container) | Each bench has its own isolated database |
| **Cache/Queue** | Redis + RQ (per container + host) | Background job processing and caching |
| **Real-time** | Socket.io via Frappe | Live log streaming during builds and deployments |
| **Routing** | iptables DNAT | Routes WireGuard peer IPs to container Docker IPs |

---

## Features

- **Lab Templates** -- Define reusable bench configurations with apps, Frappe version (v14, v15, v16, develop), and resource limits
- **5-Layer Cached Docker Builds** -- System deps, SSH config, bench init, app install, and site creation each cached separately. Only changed layers rebuild.
- **One-Click Deploy** -- Background job handles image build, container creation, WireGuard setup, SSH password, and site configuration
- **Live Build & Deploy Logs** -- GitHub Actions-style collapsible log viewer with status indicators (success/error/running), streamed in real-time via WebSocket
- **WireGuard VPN** -- Auto-generates keypair, allocates IP from 10.10.0.2-254 pool, adds peer to wg0, configures iptables DNAT routing
- **Resource Controls** -- CPU cores and memory limits per lab, enforced by Docker `--cpus` and `--memory` flags
- **Container Management** -- Start, stop, restart, redeploy, and delete benches from the dashboard
- **Multi-Site Support** -- Create multiple Frappe sites per bench container, each with its own set of installed apps
- **Stats Monitoring** -- CPU and memory usage polled every 2 minutes from Docker stats API, displayed as progress bars
- **Connection Info Panel** -- Shows VPN IP, SSH command, username, and password with one-click copy to clipboard
- **Search & Filters** -- Filter labs by status, Frappe version, or search by lab ID, title, and app name

---

## Data Model (DocTypes)

| DocType | Type | Purpose | Key Fields |
|---------|------|---------|------------|
| **Lab** | Document | Reusable bench template | `lab_id`, `title`, `frappe_version`, `status` (Draft/Building/Ready/Error), `image_tag`, `memory_limit`, `cpu_cores` |
| **Lab App** | Child Table | Apps to install in a Lab | `app_name`, `app_label`, `git_url`, `branch` |
| **Bench Instance** | Document | Running container | `bench_name`, `lab`, `status` (Draft/Deploying/Running/Stopped/Error), `container_id`, `wg_ip`, `wg_config`, `cpu_usage`, `memory_usage` |
| **Bench App** | Child Table | Apps installed in a Bench | `app_name`, `app_label`, `git_url`, `branch` |
| **Bench Site** | Document | Frappe site inside a bench | `site_name`, `bench`, `status` (Creating/Active/Inactive/Error), `full_domain`, `admin_password` |
| **Site App** | Child Table | Apps installed on a Site | `app_name`, `app_label` |
| **BenchPress Settings** | Single | Global configuration | `docker_socket`, `base_domain`, `wg_server_*` keys, `next_wg_ip`, `container_memory_limit`, `container_cpu_quota` |
| **Deploy Log** | Log | Deployment event log | `bench`, `message`, `log_type`, `timestamp` |
| **Build Log** | Log | Image build log | `lab`, `message`, `log_type`, `timestamp` |

---

## API Reference

All endpoints require authentication and use `@frappe.whitelist()`.

### Lab Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `benchpress.api.get_labs` | GET | List all labs with app count and bench count |
| `benchpress.api.get_lab` | GET | Get single lab with full apps list |
| `benchpress.api.create_lab` | POST | Create a new lab with apps as child rows |
| `benchpress.api.build_lab_image` | POST | Enqueue background Docker image build (queue: long, timeout: 3600s) |

### Bench Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `benchpress.api.get_benches` | GET | List all benches with CPU/memory stats |
| `benchpress.api.get_bench` | GET | Get single bench with apps, sites, and WireGuard config |
| `benchpress.api.create_bench` | POST | Create bench from lab template and enqueue deploy |
| `benchpress.api.bench_action` | POST | Execute action: `start`, `stop`, `restart`, `delete` |
| `benchpress.api.get_deploy_logs` | GET | Get last 100 deploy log entries for a bench |
| `benchpress.api.get_build_logs` | GET | Get last 20 build log entries for a lab |
| `benchpress.api.get_wg_config` | GET | Download WireGuard client `.conf` file |
| `benchpress.api.get_bench_stats` | GET | Get live CPU/memory stats from Docker |

### Site Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `benchpress.api.get_sites` | GET | List all sites in a bench |
| `benchpress.api.create_site` | POST | Create a new site and enqueue setup inside the container |
| `benchpress.api.site_action` | POST | Execute action: `enable`, `disable`, `drop`, `backup` |

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `benchpress.api.get_available_apps` | GET | Returns list of 8 supported Frappe ecosystem apps |
| `benchpress.api.get_settings` | GET | Get global BenchPress settings |
| `benchpress.api.health_check` | GET | Check Docker and WireGuard connectivity status |
| `benchpress.wg_manager.setup_wg_server` | POST | One-time WireGuard server initialization |

---

## Frontend Pages

The frontend is a Vue 3 Single Page Application built with Vite, TailwindCSS, and the `frappe-ui` component library.

| Page | Route | Description |
|------|-------|-------------|
| **Labs** | `/frontend/labs` | Searchable, filterable list of lab templates with status badges. Create new labs, trigger builds. |
| **New Lab** | `/frontend/labs/new` | Form to create a lab: set Lab ID, title, Frappe version, resource limits, and add apps with Git URL and branch. |
| **Lab Detail** | `/frontend/labs/:labId` | Tabbed view with Dashboard (lab info, connection panel, container stats), Sites (create/manage Frappe sites), and Build Log (collapsible step viewer). |
| **Bench Instances** | `/frontend/bench-instances` | Table of all bench containers with status badges, WG IPs, CPU/memory percentages. |
| **Deploy Logs** | `/frontend/deploy-logs` | Select a bench to view deployment log steps with success/error/running indicators. |
| **Build Logs** | `/frontend/build-logs` | Expandable list of image build logs with collapsible Docker build steps. |
| **Settings** | `/frontend/settings` | Configure Docker socket, base domain, Traefik network, WireGuard server parameters, and container resource defaults. |

### Key Components

| Component | Description |
|-----------|-------------|
| `LogViewer` | Parses raw build logs or structured deploy logs into collapsible steps with status indicators |
| `LogStep` | Single collapsible log step with colored status dot (green/amber/red), chevron toggle, monospace output, and auto-scroll |
| `Sidebar` | App navigation with Lucide icons: Labs, Bench Instances, Deploy Logs, Build Logs, Settings |

---

## Prerequisites

Before installing BenchPress, ensure your host machine has:

| Requirement | Version | Purpose |
|------------|---------|---------|
| Frappe Bench | v15+ | The bench environment to install BenchPress into |
| Python | 3.14+ | Backend runtime |
| Node.js | 24+ | Frontend build toolchain |
| Docker Engine | 20+ | Container management (must be running) |
| WireGuard | Any | VPN (`wg` and `wg-quick` commands available) |
| MariaDB | 10.6+ | Host database for Frappe |
| Redis | 6+ | Host queue and cache for Frappe |

The bench user (e.g., `frappe`) must be in the `docker` group:
```bash
sudo usermod -aG docker frappe
```

IP forwarding must be enabled for WireGuard routing:
```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

---

## Installation

### 1. Get the app and install dependencies

```bash
cd /path/to/your/frappe-bench

# Clone and install BenchPress
bench get-app https://github.com/Venkateshvenki404224/benchpress --branch develop

# Install the Docker Python SDK (required dependency)
bench pip install docker

# Install the app on your site
bench --site your-site.localhost install-app benchpress

# Run migrations to create DocTypes
bench --site your-site.localhost migrate
```

### 2. Build the frontend

```bash
# Install frontend dependencies and build
cd apps/benchpress/frontend
yarn install
yarn build

# Or use bench build
cd /path/to/your/frappe-bench
bench build --app benchpress
```

### 3. Configure BenchPress Settings

1. Navigate to **BenchPress Settings** in the Frappe Desk (`/app/benchpress-settings`)
2. Set the **Docker Socket** path (default: `unix:///var/run/docker.sock`)
3. Set the **Base Domain** for your bench instances
4. Configure WireGuard:
   - **WG Server IP**: `10.10.0.1` (default)
   - **WG Server Port**: `51820` (default)
   - **WG Server Endpoint**: Your server's public IP or hostname

### 4. Initialize WireGuard Server

From the Frappe console or via the Settings page, run the one-time WireGuard server setup:

```bash
bench --site your-site.localhost console
```

```python
from benchpress.wg_manager import setup_wg_server
setup_wg_server()
```

This generates server keys, writes `/etc/wireguard/wg0.conf`, enables IP forwarding, and brings up the `wg0` interface.

### 5. Start BenchPress

```bash
bench start
```

Access the dashboard at: `http://your-site.localhost:8000/frontend`

---

## Usage Workflow

### Step 1: Create a Lab

Navigate to **Labs > New Lab** and configure:
- **Lab ID**: A unique slug (e.g., `crm-lab`)
- **Title**: Human-readable name
- **Frappe Version**: `version-14`, `version-15`, `version-16`, or `develop`
- **Resource Limits**: Memory (e.g., `512m`, `1g`) and CPU cores
- **Apps**: Add apps with their Git URL and branch (e.g., ERPNext from `https://github.com/frappe/erpnext`, branch `version-15`)

### Step 2: Build the Docker Image

From the Lab Detail page, the image will be built automatically on first deploy, or you can trigger a standalone build. The build uses a 5-layer cached Dockerfile:

1. **System deps** (apt: MariaDB, Redis, SSH, WireGuard tools) -- rarely changes
2. **Service config** (SSH hardening, sudoers) -- rarely changes
3. **bench init** (Frappe framework) -- changes only when Frappe version changes
4. **App install** (bench get-app for each app) -- changes when app list changes
5. **Site creation** (bench new-site + install-app) -- changes when site/apps change

Build logs stream to the browser in real-time via WebSocket.

### Step 3: Deploy a Bench Instance

Click **Deploy** on the Lab Detail page. The background worker will:

1. Verify or build the Docker image
2. Create a container with resource limits on the `benchpress` Docker network (172.30.0.0/24)
3. Start the container (MariaDB, Redis, and SSH start automatically via `entry.sh`)
4. Generate a WireGuard keypair, allocate a VPN IP (10.10.0.X), add the peer, and configure iptables DNAT routing
5. Set the SSH password for the `frappe` user inside the container
6. Mark the bench as **Running**

All deployment steps stream to the Deploy Logs page in real-time.

### Step 4: Connect via WireGuard

1. Copy the WireGuard client configuration from the Lab Detail page
2. Import it into your WireGuard client (available on macOS, Windows, Linux, iOS, Android)
3. Activate the VPN tunnel

### Step 5: SSH and Develop

```bash
# SSH into your bench
ssh frappe@10.10.0.X

# Start the Frappe development server
cd frappe-bench
bench start

# Access your Frappe site
# http://10.10.0.X:8000
```

### Step 6: Manage Sites

From the Lab Detail page's **Sites** tab, create additional Frappe sites inside the running bench. Select which apps to install on each site. Sites can be enabled, disabled, backed up, or dropped.

---

## Development Setup

### Clone and set up for development

```bash
cd /path/to/your/frappe-bench

# Get the app
bench get-app https://github.com/Venkateshvenki404224/benchpress --branch develop
bench pip install docker
bench --site your-site.localhost install-app benchpress
bench --site your-site.localhost migrate
```

### Frontend development (hot-reload)

```bash
cd apps/benchpress/frontend
yarn install
yarn dev
```

The Vite dev server starts with hot module replacement. The Vue SPA is served at `/frontend` via the website route rule in `hooks.py`.

### Backend development

```bash
# Clear cache after Python/DocType changes
bench --site your-site.localhost clear-cache

# Run migrations after DocType JSON changes
bench --site your-site.localhost migrate

# Run linters
cd apps/benchpress
python -m ruff check .
python -m ruff format .

# Frontend linting
cd frontend
yarn lint
```

### Running tests

```bash
bench --site your-site.localhost run-tests --app benchpress
```

---

## Project Structure

```
benchpress/
+-- benchpress/
|   +-- api.py                    # REST API layer (~20 endpoints)
|   +-- deploy_manager.py         # Build & deploy orchestration (brain of BenchPress)
|   +-- docker_manager.py         # Docker SDK wrapper (build, create, exec, stats)
|   +-- wg_manager.py             # WireGuard VPN management (keys, peers, routing)
|   +-- stats_collector.py        # Cron job: poll Docker stats every 2 minutes
|   +-- hooks.py                  # App config: routes, scheduler, ignore_links_on_delete
|   +-- lab-templates/
|   |   +-- Dockerfile            # 5-layer cached image build
|   |   +-- scripts/
|   |       +-- entry.sh          # Container entrypoint (starts MariaDB, Redis, SSH)
|   |       +-- install-apps.sh   # Install apps during Docker build
|   |       +-- create-site.sh    # Create site during Docker build
|   |       +-- setup-site.sh     # Create additional sites post-deploy
|   +-- benchpress/
|   |   +-- doctype/
|   |       +-- lab/              # Lab template DocType
|   |       +-- lab_app/          # Lab App child table
|   |       +-- bench_instance/   # Running container DocType
|   |       +-- bench_app/        # Bench App child table
|   |       +-- bench_site/       # Frappe site DocType
|   |       +-- site_app/         # Site App child table
|   |       +-- benchpress_settings/  # Global config singleton
|   |       +-- deploy_log/       # Deployment log DocType
|   |       +-- build_log/        # Build log DocType
|   +-- public/
|       +-- images/               # App logos, favicons, Frappe ecosystem app icons
+-- frontend/
    +-- src/
        +-- App.vue               # Root component with sidebar navigation
        +-- router.js             # Vue Router with 8 routes
        +-- socket.js             # Socket.io client for real-time events
        +-- pages/
        |   +-- Labs.vue          # Lab list with search, status/version filters
        |   +-- NewLab.vue        # Lab creation form
        |   +-- LabDetail.vue     # Tabbed view: Dashboard, Sites, Build Log
        |   +-- BenchInstances.vue # Bench instance table
        |   +-- DeployLogs.vue    # Deploy log viewer per bench
        |   +-- BuildLogs.vue     # Build log viewer with expandable entries
        |   +-- Settings.vue      # Global settings dialog
        +-- components/
            +-- LogViewer.vue     # Parses logs into collapsible steps
            +-- LogStep.vue       # Single log step with status dot and auto-scroll
```

---

## Real-Time Communication

BenchPress uses Frappe's WebSocket system (`frappe.publish_realtime`) to stream logs to the frontend during long-running operations:

| Event | Trigger | Consumer |
|-------|---------|----------|
| `bench_deploy_log` | Each deployment step in `deploy_manager.py` | Deploy Logs page, Lab Detail page |
| `lab_build_log` | Each Docker build line in `deploy_manager.py` | Build Logs page, Lab Detail Build Log tab |

**Backend pattern:**
```python
frappe.publish_realtime("bench_deploy_log", message={
    "bench": bench_name,
    "log": "Starting container...",
    "type": "info"
}, user=frappe.session.user, after_commit=False)
```

**Frontend pattern:**
```javascript
socket.on("bench_deploy_log", (data) => {
    this.logs.push(data);
});
```

---

## Networking

| Network | Subnet | Purpose |
|---------|--------|---------|
| `benchpress` (Docker bridge) | `172.30.0.0/24` | Internal communication between containers |
| WireGuard (`wg0`) | `10.10.0.0/24` | VPN subnet for user access (server: `10.10.0.1`, clients: `10.10.0.2`-`10.10.0.254`) |

**DNAT port mapping** (per bench, via iptables):

| WireGuard IP Port | Container Port | Service |
|-------------------|----------------|---------|
| `10.10.0.X:22` | `container:22` | SSH |
| `10.10.0.X:8000` | `container:8000` | Frappe Web Server |
| `10.10.0.X:9000` | `container:9000` | Frappe Socket.io |

---

## Supported Frappe Apps

BenchPress comes pre-configured with support for the Frappe ecosystem:

| App | Repository | Default Branch |
|-----|-----------|----------------|
| Frappe Framework | `github.com/frappe/frappe` | version-15 |
| ERPNext | `github.com/frappe/erpnext` | version-15 |
| HRMS | `github.com/frappe/hrms` | version-15 |
| LMS | `github.com/frappe/lms` | develop |
| Helpdesk | `github.com/frappe/helpdesk` | develop |
| Wiki | `github.com/frappe/wiki` | develop |
| Webshop | `github.com/frappe/webshop` | version-15 |
| CRM | `github.com/frappe/crm` | develop |

You can also add **any custom Frappe app** by providing its Git URL and branch when creating a Lab.

---

## Configuration Reference

### BenchPress Settings

| Field | Default | Description |
|-------|---------|-------------|
| `docker_socket` | `unix:///var/run/docker.sock` | Docker Engine socket URL |
| `default_image` | `frappe/bench:latest` | Base Docker image |
| `base_domain` | -- | Base domain for bench instances |
| `traefik_network` | -- | Docker network for Traefik (if used) |
| `wg_server_ip` | `10.10.0.1` | WireGuard server IP address |
| `wg_subnet` | `10.10.0.0/24` | WireGuard VPN subnet |
| `wg_server_port` | `51820` | WireGuard listen port |
| `wg_server_endpoint` | -- | Public IP/hostname for WireGuard clients to connect to |
| `wg_server_public_key` | Auto-generated | Server's WireGuard public key |
| `wg_server_private_key` | Auto-generated | Server's WireGuard private key (encrypted) |
| `next_wg_ip` | `2` | Next IP octet to allocate (auto-increments) |
| `container_memory_limit` | -- | Default memory limit for containers |
| `container_cpu_quota` | -- | Default CPU quota for containers |

---

## Contributing

1. Fork the repository
2. Create a feature branch from `develop`: `git checkout -b feature/my-feature`
3. Make your changes following Frappe coding conventions
4. Run tests: `bench --site your-site.localhost run-tests --app benchpress`
5. Run linters: `cd apps/benchpress && python -m ruff check . && python -m ruff format .`
6. Commit using Conventional Commits: `feat(lab): add batch deploy support`
7. Push and open a Pull Request against `develop`

### Commit Format

```
type(scope): short description

feat(lab):     add multi-app selection to lab creation form
fix(deploy):   prevent duplicate container on rapid double-click
refactor(wg):  migrate iptables rules to nftables
test(api):     add tests for site creation endpoint
docs(readme):  add architecture diagram
chore(deps):   bump frappe-ui to 0.1.192
```

---

## License

MIT License. See [LICENSE](license.txt) for details.

---

<div align="center">

Built for **FOSS Hack 2026** by [Venkatesh](https://github.com/Venkateshvenki404224)

[GitHub Repository](https://github.com/Venkateshvenki404224/benchpress)

</div>
