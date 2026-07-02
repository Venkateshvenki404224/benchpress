# Getting Started with BenchPress

This guide walks you through your first BenchPress setup — from installation to deploying your first Frappe bench.

---

## Prerequisites

Before installing BenchPress, ensure your host machine has:

| Requirement | Version | Purpose |
|------------|---------|---------|
| Frappe Bench | v16 | The bench environment to install BenchPress into |
| Docker Engine | 20+ | Container management |
| Docker Compose | v2+ | Manages shared MariaDB + Redis infrastructure |
| vpn_management app | version-16 | VPN control plane (required app — provides the wg-agent and VPN DocTypes) |

> MariaDB and Redis for bench containers are managed automatically via Docker Compose. You only need them on the host for Frappe itself.

---

## Installation

### Step 1: Install the app

```bash
cd /path/to/your/frappe-bench

bench get-app https://github.com/Venkateshvenki404224/benchpress --branch develop
bench pip install docker
bench --site your-site.localhost install-app benchpress
bench --site your-site.localhost migrate
```

### Step 2: Run the setup script

```bash
bash apps/benchpress/setup.sh your-site.localhost
```

The setup script is idempotent (safe to run multiple times) and handles three steps:

1. **Docker group** — Adds your user to the `docker` group
2. **Shared infrastructure** — Starts `benchpress-mariadb` and `benchpress-redis` via docker-compose
3. **IP forwarding** — Enables kernel IP forwarding for VPN routing

> VPN (the WireGuard interface, peers, and IPs) is provisioned by the
> **vpn_management** app and its wg-agent — see [WireGuard Setup](wireguard-setup.md).

> If the Docker group was just added, log out and back in before starting bench.

### Step 3: Build the frontend

```bash
cd apps/benchpress/frontend
yarn install
yarn build
```

### Step 4: Configure BenchPress Settings

![Settings](images/settings.png)

1. Start the bench: `bench start`
2. Open BenchPress Settings in your browser: `/app/benchpress-settings`
3. Set the **Base Domain** and review the container resource limits.

VPN configuration (server, pool, peers) lives in the vpn_management
DocTypes in Desk — see [WireGuard Setup](wireguard-setup.md).

### Step 5: Open firewall

```bash
sudo ufw allow 44556/udp
```

### Step 6: Access the dashboard

Open your browser to:

```
http://your-site.localhost:8000/frontend
```

---

## Your First Lab and Bench

Once BenchPress is running, follow the [Creating Labs](creating-labs.md) guide to create your first lab template and deploy a bench instance.

---

## What's Next?

| Guide | Description |
|-------|-------------|
| [Creating Labs](creating-labs.md) | Create lab templates and deploy bench instances |
| [Connecting to Benches](connecting-to-benches.md) | SSH access, VPN setup, and connection info |
| [Logs and Monitoring](logs-and-monitoring.md) | Build logs, deploy logs, and container stats |
| [VPN Device Management](device-management.md) | Register devices for persistent WireGuard access |
| [WireGuard Setup](wireguard-setup.md) | How the vpn_management app runs the VPN plane |
| [Upgrading a BenchPress Install](upgrading.md) | Backup-gated upgrade and rollback runbook |
