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

## Operator

## Reference

## Other

- [PRODUCTION CHECKLIST](./docs/PRODUCTION_CHECKLIST.md): Reference page for production checklist.
- [SIZING](./docs/SIZING.md): Reference page for sizing.
- [Connecting To Benches](./docs/connecting-to-benches.md): Reference page for connecting to benches.
- [Database Backup Restore](./docs/database-backup-restore.md): Reference page for database backup restore.
- [Device Management](./docs/device-management.md): Reference page for device management.
- [Getting Started](./docs/getting-started.md): Reference page for getting started.
- [Hosted Signup](./docs/hosted-signup.md): Reference page for hosted signup.
- [BenchPress documentation](./docs/index.md): Start here. Three tracks — use a bench, run the server that hosts one, or read the data model and the API.
- [Integration Notices](./docs/integration-notices.md): Reference page for integration notices.
- [DESIGN BRIEF](./docs/internal/DESIGN_BRIEF.md): Reference page for design brief.
- [SCREENSHOT CHECKLIST](./docs/internal/SCREENSHOT-CHECKLIST.md): Reference page for screenshot checklist.
- [DESIGN BRIEF](./docs/internal/design_handoff_benchpress_ui/DESIGN_BRIEF.md): Reference page for design brief.
- [Design Handoff Benchpress Ui](./docs/internal/design_handoff_benchpress_ui/README.md): Reference page for design handoff benchpress ui.
- [Lab Access Acceptance](./docs/lab-access-acceptance.md): Reference page for lab access acceptance.
- [Logs And Monitoring](./docs/logs-and-monitoring.md): Reference page for logs and monitoring.
- [Production Safety](./docs/production-safety.md): Reference page for production safety.
- [Upgrading](./docs/upgrading.md): Reference page for upgrading.
- [Wireguard Setup](./docs/wireguard-setup.md): Reference page for wireguard setup.
