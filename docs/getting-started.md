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
| WireGuard | Any | VPN access (optional but recommended) |

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

The setup script is idempotent (safe to run multiple times) and handles six steps:

1. **Docker group** — Adds your user to the `docker` group
2. **Shared infrastructure** — Starts `benchpress-mariadb` and `benchpress-redis` via docker-compose
3. **IP forwarding** — Enables kernel IP forwarding for VPN routing
4. **Sudoers** — Configures passwordless sudo for WireGuard commands
5. **WireGuard tools** — Installs `wireguard-tools` if missing
6. **WireGuard server** — Generates keys and brings up the `wg0` interface

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
3. Fill in the WireGuard fields (values are printed by the setup script):
   - **WG Server Public Key**
   - **WG Server Endpoint** — Your server's public IP (`curl -s ifconfig.me`)
   - **WG Server Port** — `51820`

### Step 5: Open firewall

```bash
sudo ufw allow 51820/udp
```

### Step 6: Access the dashboard

Open your browser to:

```
http://your-site.localhost:8000/frontend
```

---

## Troubleshooting

If any step above failed — or a deploy errors out with a cryptic message — **run the doctor first**. It inspects the same host surface `setup.sh` configures (Docker, WireGuard, IP forwarding, sudoers, ports, shared infrastructure) and prints a `pass / warn / fail` report with the exact command to fix each problem. Its output is redaction-safe, so you can paste it straight into a GitHub issue.

Two equivalent ways to run it:

```bash
bench --site your-site.localhost execute benchpress.doctor.run
bench benchpress doctor --site your-site.localhost
```

> `bench benchpress doctor` is registered at app load; if bench does not recognise it yet, run `bench restart` once.

Flags (on either path):

| Flag | Effect |
|------|--------|
| `--json` | Emit the results as machine-readable JSON instead of the text report. With `execute`: `--kwargs "{'as_json': 1}"`. |
| `--strict` | Exit non-zero when any check is `FAIL` — use it as a CI / pre-deploy gate. With `execute`: `--kwargs "{'strict': 1}"`. |

Sample report:

```
BenchPress readiness check
site: frontend  bench: /home/frappe/frappe-bench  running on: host

[PASS] Operating system: Ubuntu 22.04.4 LTS
[PASS] Docker daemon: reachable, server version 24.0.7
[WARN] WireGuard interface: wg0 is not up
        fix: sudo wg-quick up wg0
[FAIL] IP forwarding: net.ipv4.ip_forward = 0
        fix: sudo sysctl -w net.ipv4.ip_forward=1

Summary: 9 pass, 1 warn, 1 fail
```

Host-only checks (IP forwarding, sudoers, the `wg0` interface, listening ports) need direct host access. Run the doctor **on the host bench**, not inside a container — in a container those rows degrade to `[WARN] skipped (run on the host)` rather than failing.

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
| [WireGuard Setup](wireguard-setup.md) | Detailed WireGuard configuration and troubleshooting |
