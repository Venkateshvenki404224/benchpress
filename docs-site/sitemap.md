# Sitemap

Structured documentation sitemap for BenchPress.

## User

### Start

- [Quick tour](/docs/user/quick-tour): The five screens in the BenchPress sidebar, and every number the Overview dashboard reports.

### Get a bench running

- [Deploy from a template](/docs/user/deploy-from-template): Turn a catalog template into a running bench, and read the eleven pipeline steps while they run.
- [Create a lab](/docs/user/create-a-lab): Fill in the New lab form when no catalog template matches the app list you need.
- [Read a lab page](/docs/user/lab-detail): Every field on the lab page, and why container status and container health can disagree.
- [Start, stop and redeploy](/docs/user/lifecycle): The five actions on a running bench, which of them destroy work, and which are admin-only.

### Get into the bench

- [Register a VPN device](/docs/user/vpn-devices): Put a laptop or a phone on the WireGuard network, import the config, read the device status, and run the connection test when a site will not open.
- [Open the bench site](/docs/user/open-your-site): The Sites card, the three states of its Open button, and logging in to the Frappe site a deploy created.
- [Connect over SSH and the VPN](/docs/user/connect-ssh-vpn): The connection card on a lab page — two addresses, the SSH command, the three passwords, and which of them work without the tunnel.
- [Use code-server](/docs/user/code-server): Open the browser VS Code session on a bench, find its password, hand the session to a teammate, and restart it when it stops answering.

### Watch it and pay for it

- [Read logs and container stats](/docs/user/logs-and-monitoring): The deploy stepper, the raw log and its step markers, the build log, and the CPU and memory bars on a running bench.
- [Leases and credits](/docs/user/leases-and-credits): The countdown on a running bench, the renew dialog and its plans, the credit meter, the ledger, and where a purchase hands off to the payment gateway.

### When it goes wrong

- [Troubleshooting](/docs/user/troubleshooting): Every symptom a BenchPress user meets, its cause, and the page that fixes it — deploys, the VPN, SSH, code-server, logs and credits.

## Operator

### Start

- [Operator track](/docs/operator): Run BenchPress on your own box — install, the VPN plane, settings, the shared database, images, upgrades, safety and diagnostics.

### Stand a host up

- [Prerequisites](/docs/operator/prerequisites): What a BenchPress host needs before you install — supported platforms, versions, Docker socket access, IP forwarding, sysbox, and the measured CPU sizing.
- [Install](/docs/operator/install): Install BenchPress into a Frappe v16 bench — get-app, setup.sh, the frontend build, the base domain, and the first screen.
- [WireGuard and the VPN plane](/docs/operator/wireguard-setup): How the vpn_management app owns the tunnel, what BenchPress consumes from it, the measured server and pool values, and why userns-remap matters.

### Run it

- [Settings reference](/docs/operator/settings-reference): Every field on BenchPress Settings and Credit Settings, with the value measured on a live host, where each one is edited, and what changing it costs.
- [The shared database server](/docs/operator/database-server): One MariaDB holds every bench site's database — where it lives, how BenchPress drives it, what drift detection watches, and the four actions on the record.
- [Backup and restore](/docs/operator/backup-and-restore): Where the nightly MariaDB dumps land, how long they are kept, and the two restore paths — a scratch container for verification, and managed recovery from bench console.
- [Users and roles](/docs/operator/users-and-roles): The two BenchPress roles, what each one may read and write, which screens are admin-only, and how ownership rather than a role decides who sees a bench.

### Images and speed

- [Golden images](/docs/operator/golden-images): A lab's finished site is baked into its own image as a database dump, so a deploy restores it instead of creating tables — the measured numbers, the two settings, and why a golden gets refused.
- [The image cache](/docs/operator/image-cache): One image per lab, tagged benchpress/<lab_id>:lab — what it costs on disk, how the weekly prewarm and sweep work, and what is safe to prune.

### Keep it safe

- [Upgrading](/docs/operator/upgrading): Move a BenchPress install to a newer release — the backup gate, the five steps, the scripted path, rollback, and why lab images are a separate opt-in.
- [Production safety](/docs/operator/production-safety): What BenchPress is and is not ready to carry — the alpha verdict, the container privilege boundary, what is backed up, and the endpoint-by-endpoint release checklist.
- [Diagnostics](/docs/operator/diagnostics): The eleven read-only checks that ask Docker, MariaDB, Redis and the kernel what is true — how to run them, what each failure means, and the four things they do not cover.

### Optional — running it for a team

- [Credits and billing](/docs/operator/credits-and-billing): Optional and off by default — the metering half of BenchPress, covering leases, balances, the ledger, admin adjustments, and the optional Razorpay handoff.
- [Admission and limits](/docs/operator/admission-and-limits): Optional and off by default — concurrency caps, size ceilings, device and build quotas, how a slot is claimed as a row, and the acceptance run that proves access still works.
- [Self-serve signup](/docs/operator/hosted-signup): Optional and off by default — retire the waitlist and let people sign themselves up, with GitHub and Google as the primary paths and the abuse controls that make a free grant safe.

## Reference

## Other

- [BenchPress documentation](/docs): Start here. Three tracks — use a bench, run the server that hosts one, or read the data model and the API.
