# benchpress

> Self-hosted Frappe dev environments, deployed from a template.

These docs ship inside the package so coding agents can read them offline. Open the topic file you need from the list below — paths are relative to this file.

## Overview

BenchPress deploys a Frappe bench from a template. An operator describes a lab
once — a Frappe version and a list of apps — and anyone with access deploys it,
works in it over SSH or a browser VS Code session, and destroys it when the task
is done.

- Self-hosted. One box, Docker, no external control plane.
- Every bench reachable only over WireGuard.
- Built on the Frappe framework, with a Vue 3 single-page app on the front.

## Best Starting Points

- [Quick tour](./docs/user/quick-tour.md): The five screens in the BenchPress sidebar, and every number the Overview dashboard reports.
- [Deploy from a template](./docs/user/deploy-from-template.md): Turn a catalog template into a running bench, and read the eleven pipeline steps while they run.

## User Track

- [BenchPress documentation](./docs/index.md): Start here. Three tracks — use a bench, run the server that hosts one, or read the data model and the API.
- [Quick tour](./docs/user/quick-tour.md): The five screens in the BenchPress sidebar, and every number the Overview dashboard reports.
- [Deploy from a template](./docs/user/deploy-from-template.md): Turn a catalog template into a running bench, and read the eleven pipeline steps while they run.
- [Create a lab](./docs/user/create-a-lab.md): Fill in the New lab form when no catalog template matches the app list you need.
- [Read a lab page](./docs/user/lab-detail.md): Every field on the lab page, and why container status and container health can disagree.
- [Start, stop and redeploy](./docs/user/lifecycle.md): The five actions on a running bench, which of them destroy work, and which are admin-only.
- [Register a VPN device](./docs/user/vpn-devices.md): Put a laptop or a phone on the WireGuard network, import the config, read the device status, and run the connection test when a site will not open.
- [Open the bench site](./docs/user/open-your-site.md): The Sites card, the three states of its Open button, and logging in to the Frappe site a deploy created.
- [Connect over SSH and the VPN](./docs/user/connect-ssh-vpn.md): The connection card on a lab page — two addresses, the SSH command, the three passwords, and which of them work without the tunnel.
- [Use code-server](./docs/user/code-server.md): Open the browser VS Code session on a bench, find its password, hand the session to a teammate, and restart it when it stops answering.
- [Read logs and container stats](./docs/user/logs-and-monitoring.md): The deploy stepper, the raw log and its step markers, the build log, and the CPU and memory bars on a running bench.
- [Leases and credits](./docs/user/leases-and-credits.md): The countdown on a running bench, the renew dialog and its plans, the credit meter, the ledger, and where a purchase hands off to the payment gateway.
- [Troubleshooting](./docs/user/troubleshooting.md): Every symptom a BenchPress user meets, its cause, and the page that fixes it — deploys, the VPN, SSH, code-server, logs and credits.

## Agent Guidance

Three tracks. Read `user/` for working inside a deployed bench, `operator/` for
running the host, and `reference/` for the data model and the HTTP API. Start
from the quick tour when you do not yet know which screen owns a task.

## User

### Start

- [Quick tour](./docs/user/quick-tour.md): The five screens in the BenchPress sidebar, and every number the Overview dashboard reports.

### Get a bench running

- [Deploy from a template](./docs/user/deploy-from-template.md): Turn a catalog template into a running bench, and read the eleven pipeline steps while they run.
- [Create a lab](./docs/user/create-a-lab.md): Fill in the New lab form when no catalog template matches the app list you need.
- [Read a lab page](./docs/user/lab-detail.md): Every field on the lab page, and why container status and container health can disagree.
- [Start, stop and redeploy](./docs/user/lifecycle.md): The five actions on a running bench, which of them destroy work, and which are admin-only.

### Get into the bench

- [Register a VPN device](./docs/user/vpn-devices.md): Put a laptop or a phone on the WireGuard network, import the config, read the device status, and run the connection test when a site will not open.
- [Open the bench site](./docs/user/open-your-site.md): The Sites card, the three states of its Open button, and logging in to the Frappe site a deploy created.
- [Connect over SSH and the VPN](./docs/user/connect-ssh-vpn.md): The connection card on a lab page — two addresses, the SSH command, the three passwords, and which of them work without the tunnel.
- [Use code-server](./docs/user/code-server.md): Open the browser VS Code session on a bench, find its password, hand the session to a teammate, and restart it when it stops answering.

### Watch it and pay for it

- [Read logs and container stats](./docs/user/logs-and-monitoring.md): The deploy stepper, the raw log and its step markers, the build log, and the CPU and memory bars on a running bench.
- [Leases and credits](./docs/user/leases-and-credits.md): The countdown on a running bench, the renew dialog and its plans, the credit meter, the ledger, and where a purchase hands off to the payment gateway.

### When it goes wrong

- [Troubleshooting](./docs/user/troubleshooting.md): Every symptom a BenchPress user meets, its cause, and the page that fixes it — deploys, the VPN, SSH, code-server, logs and credits.

## Operator

## Reference

## Other

- [PRODUCTION CHECKLIST](./docs/PRODUCTION_CHECKLIST.md): Reference page for production checklist.
- [SIZING](./docs/SIZING.md): Reference page for sizing.
- [Database Backup Restore](./docs/database-backup-restore.md): Reference page for database backup restore.
- [Getting Started](./docs/getting-started.md): Reference page for getting started.
- [Hosted Signup](./docs/hosted-signup.md): Reference page for hosted signup.
- [BenchPress documentation](./docs/index.md): Start here. Three tracks — use a bench, run the server that hosts one, or read the data model and the API.
- [Integration Notices](./docs/integration-notices.md): Reference page for integration notices.
- [DESIGN BRIEF](./docs/internal/DESIGN_BRIEF.md): Reference page for design brief.
- [SCREENSHOT CHECKLIST](./docs/internal/SCREENSHOT-CHECKLIST.md): Reference page for screenshot checklist.
- [DESIGN BRIEF](./docs/internal/design_handoff_benchpress_ui/DESIGN_BRIEF.md): Reference page for design brief.
- [Design Handoff Benchpress Ui](./docs/internal/design_handoff_benchpress_ui/README.md): Reference page for design handoff benchpress ui.
- [Lab Access Acceptance](./docs/lab-access-acceptance.md): Reference page for lab access acceptance.
- [Production Safety](./docs/production-safety.md): Reference page for production safety.
- [Upgrading](./docs/upgrading.md): Reference page for upgrading.
- [Wireguard Setup](./docs/wireguard-setup.md): Reference page for wireguard setup.
