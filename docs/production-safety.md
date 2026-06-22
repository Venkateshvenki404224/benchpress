# Production Safety & Compatibility

This page tells you, before you install, **whether BenchPress is safe to run on your
host** and **which platform and tool versions are supported**. Read it first if you
are evaluating BenchPress for anything beyond a throwaway machine.

> This is the first slice of the production-readiness docs (see issue
> [#36](https://github.com/Venkateshvenki404224/benchpress/issues/36)). A full
> troubleshooting guide (symptom → cause → fix) and an uninstall/rollback runbook
> are tracked there and will follow.

---

## Production readiness

**BenchPress is alpha software. Do not run it on a host you cannot afford to lose.**

It is built for developers and small teams spinning up disposable Frappe/ERPNext
environments — not yet for production hosting of customer data. Concretely:

- **Host-level privilege.** `setup.sh` adds your user to the `docker` group, edits
  `/etc/sudoers.d`, enables IP forwarding via `/etc/sysctl.d`, and brings up a
  WireGuard interface. These are real, persistent changes to the host.
- **Privileged containers.** Bench containers currently run with elevated Docker
  privileges to support in-container networking. Treat every bench as having host
  reach until that is hardened.
- **No backup/restore guarantees yet.** Bench data lives in Docker volumes. Take
  your own backups; there is no built-in restore path you should rely on.
- **Single-tenant assumption.** Quotas, rate limits, and audit trails are still in
  progress. Run BenchPress for people you trust, on a host dedicated to it.

Use it on a dedicated dev box, a VM, or a cloud instance you can rebuild — not on
your daily-driver workstation or a shared production server.

---

## Supported host platforms

BenchPress installs onto an existing Frappe Bench and drives the host's Docker and
WireGuard. The setup script is Linux-only (it uses `apt`, `systemd`/`sysctl`,
`/etc/sudoers.d`, and the WireGuard kernel module).

| Platform | Status | Notes |
|----------|--------|-------|
| Ubuntu 22.04 / 24.04 | Supported | Primary target; CI and development happen here. |
| Debian 12+ | Supported | Same `apt` + systemd toolchain as Ubuntu. |
| Windows 11 via WSL2 (Ubuntu) | Experimental | App and Docker work; WireGuard/kernel-module steps depend on your WSL kernel. See issue [#26](https://github.com/Venkateshvenki404224/benchpress/issues/26). |
| Other Linux (Fedora, Arch, …) | Untested | Likely workable, but `setup.sh` assumes `apt`; adapt package install steps manually. |
| macOS / native Windows | Not supported as a host | No `apt`/systemd/WireGuard kernel module. On Windows, use WSL2. |

> A browser on **any** OS can reach a deployed bench over VPN or (later) a public
> URL — the platform table above is only about the **host that runs BenchPress**.

---

## Compatibility matrix

These are the versions BenchPress is built and tested against. Pinned values come
from the project's CI and packaging config.

| Component | Required / Tested | Where it's enforced |
|-----------|-------------------|---------------------|
| Frappe Framework (host bench) | v16 | `bench get-app` target; README badge |
| Python | 3.14+ | `pyproject.toml` (`requires-python`), CI |
| Node.js | 24 | CI (`ci.yml`) — for the frontend build |
| Docker Engine | 20+ | Container management |
| Docker Compose | v2+ | Shared MariaDB + Redis infrastructure |
| WireGuard | Any recent | Optional; required only for VPN access |
| Vue (frontend) | 3.5+ | `frontend/package.json` |
| frappe-ui | 0.1.270+ | `frontend/package.json` |

### Frappe versions available to deployed benches

A bench you deploy can target a different Frappe version than the host. Lab
definitions accept:

| Frappe version | Lab support |
|----------------|-------------|
| version-16 | Available |
| version-15 | Available (default for starter templates) |
| version-14 | Available |
| develop | Available (unstable; tracks Frappe nightly) |

---

## See also

- [Getting Started](getting-started.md) — install and deploy your first bench
- [WireGuard Setup](wireguard-setup.md) — VPN configuration and troubleshooting
- [Connecting to Benches](connecting-to-benches.md) — SSH and connection info
