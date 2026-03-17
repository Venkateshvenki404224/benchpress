<div align="center">

# BenchPress

**Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Frappe Framework](https://img.shields.io/badge/Built%20on-Frappe%20Framework-blue)](https://frappeframework.com)
[![FOSS Hack 2026](https://img.shields.io/badge/FOSS%20Hack-2026-orange)](https://fossunited.org)

</div>

---

## The Problem

Setting up a Frappe/ERPNext development environment is painful:

1. **Manual setup** — Install bench CLI, MariaDB, Redis, Node.js, wkhtmltopdf, and a dozen other dependencies
2. **Dependency conflicts** — Different projects need different versions, and your OS gets polluted
3. **No isolation** — One broken bench can affect everything on your machine
4. **No remote access** — Team members can't SSH into each other's dev environments
5. **Repetitive work** — Every new project means repeating the same 30-minute setup ritual

There's no simple way to say *"Give me a fresh Frappe bench with ERPNext and HRMS"* and have it running in minutes.

## The Solution

BenchPress is a **self-hosted Frappe Cloud alternative** built as a Frappe app. It automates the entire bench lifecycle through a web UI:

1. **Create a Lab** — Define a template with your desired apps (CRM, ERPNext, HRMS, etc.) and resource limits
2. **Build once** — Docker image with all apps baked in, cached for instant reuse
3. **Deploy in clicks** — Each bench runs in its own Docker container with MariaDB, Redis, and all services included
4. **SSH via WireGuard** — Secure VPN access into any container, no exposed ports
5. **Real-time logs** — Watch Docker builds and deployments stream live in the browser

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   BenchPress (Frappe App)             │
│                                                      │
│  Labs (Templates)          Bench Instances           │
│  ┌──────────────┐         ┌─────────────────────┐    │
│  │ CRM Lab      │─deploy─→│ Container           │    │
│  │ • frappe+crm │         │ • MariaDB + Redis   │    │
│  │ • 512m, 1cpu │         │ • SSH + WireGuard   │    │
│  └──────────────┘         │ • bench start       │    │
│  ┌──────────────┐         └─────────────────────┘    │
│  │ ERP Lab      │─deploy─→│ Container           │    │
│  │ • frappe+erp │         │ • Full ERP stack    │    │
│  │ • 1g, 2cpu   │         │ • WG IP: 10.10.0.3 │    │
│  └──────────────┘         └─────────────────────┘    │
│                                                      │
│  Docker Engine ←──── Docker SDK (Python)             │
│  WireGuard     ←──── wg CLI (subprocess)             │
└──────────────────────────────────────────────────────┘
```

### How It Works

- **Lab** = A reusable template defining which Frappe apps to install, the Frappe version, and resource limits (CPU, memory). Created via the Desk UI.
- **Build** = Docker image with all apps baked in during `docker build`. Built once per lab, cached for all future deploys.
- **Deploy** = Spin up a container from the lab image → start MariaDB/Redis/SSH → configure WireGuard VPN → create Frappe site → install apps.
- **Access** = SSH into the container via WireGuard VPN (`ssh frappe@10.10.0.X`), run `bench start`, and access your Frappe site.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Frappe Framework (Python) |
| Frontend | HTML/CSS/JS + Bootstrap 5 (no build step) |
| Containers | Docker (Python SDK) |
| VPN | WireGuard (kernel-level, host-managed) |
| Database | MariaDB (inside each container) |
| Queue | Redis + RQ (inside each container) |
| Realtime | Frappe WebSocket (`frappe.publish_realtime`) |

## Features

- **Lab Templates** — Define reusable bench configurations with apps, versions, and resource limits
- **One-Click Deploy** — Background job handles image build, container creation, site setup
- **Live Build Logs** — GitHub CI-style log viewer with realtime streaming via WebSocket
- **WireGuard VPN** — Auto-configured per container, SSH access without exposing ports
- **Resource Controls** — CPU and memory limits per lab, configurable from the UI
- **Container Management** — Start, stop, restart, delete benches from the dashboard
- **Stats Monitoring** — CPU and memory usage polled every 2 minutes
- **Site Management** — Create multiple Frappe sites per bench, install apps per site

## Installation

### Prerequisites

- A running Frappe bench (v15+)
- Docker Engine installed and running
- WireGuard installed on the host (`wg` and `wg-quick` commands)
- The bench user must be in the `docker` group

### Setup

```bash
# Get the app
bench get-app https://github.com/user/benchpress --branch develop
bench --site your-site install-app benchpress
bench --site your-site migrate

# Install the Docker SDK
bench pip install docker

# Start the bench
bench start
```

### Configure

1. Go to **BenchPress Settings** in the Desk
2. Set the Docker socket path (default: `unix:///var/run/docker.sock`)
3. Set the base domain and WireGuard server details
4. Create your first **Lab** with the desired apps
5. Click **Actions > Build Image** to build the Docker image
6. Create a **Bench Instance** from the lab and deploy

## Development

```bash
# Clear cache after changes
bench --site your-site clear-cache

# Run migrations after DocType changes
bench --site your-site migrate

# Run linters
cd apps/benchpress
pre-commit run --all-files
```

## License

MIT License. See [LICENSE](license.txt) for details.

---

<div align="center">
Built for <b>FOSS Hack 2026</b> by Venkatesh
</div>
