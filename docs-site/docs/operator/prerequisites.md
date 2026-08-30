---
title: Prerequisites
description: What a BenchPress host needs before you install — the four
  preconditions, supported platforms, versions, Docker socket access, and the
  measured CPU and disk sizing.
lastModified: "2026-08-30T08:05:07-04:00"
lastAuthor: Venkatesh
---
# Prerequisites

What the machine must already have before [Install](/docs/operator/install)
will work, and how much of it to buy.

**Who this is for.** Whoever is choosing or preparing the host.

**Before you start.** BenchPress installs into an existing Frappe bench and
drives that host's Docker. It is not a standalone service, and it is Linux
only — the setup script uses `apt` and `sysctl`.

## The four preconditions

Get these four before you read anything else on this page. Each one blocks the
install or the first deploy, and none of them can be fixed from inside the app.

|Precondition|Why it blocks|Set it in|
|--|--|--|
|`sysbox-runc` registered with Docker|`default_bench_runtime` is `sysbox`, so a deploy has no runtime without it. `runc` without `userns-remap` makes in-container root host root|[Step 5](#steps)|
|`net.ipv4.ip_forward = 1`|The kernel drops tunnel traffic on its way to a bench, so a deploy fails on the network step|[Step 4](#steps)|
|44556/UDP open, on `ufw` **and** on any cloud firewall|A WireGuard peer never handshakes, so nothing reaches a bench over the tunnel|[Step 7](#steps)|
|A domain you control, for `base_domain`|`base_domain` is `reqd` on **BenchPress Settings**, so the settings form will not save without it. Sites are addressed as `<instance id>.<base domain>`|[Install, step 5](/docs/operator/install)|

Size the host before you buy it as well. [Sizing](#sizing) holds the CPU floor
and [Disk](#disk) the disk floor. Disk is the one that fails a default VPS.

## Steps

1. **Confirm the platform is supported.** See the table under
   [Supported platforms](#supported-platforms).

2. **Confirm the versions.** See [Versions](#versions). The host bench must be
   Frappe v16.

3. **Give the bench user the Docker socket.** BenchPress creates containers,
   networks and volumes as itself.

   ```bash
   sudo usermod -aG docker "$USER"
   newgrp docker
   docker info >/dev/null && echo "socket ok"
   ```

   `setup.sh` does this for you. It is listed here because the group change
   only takes effect on a new login, and a bench started before that cannot
   reach Docker.

4. **Turn on IP forwarding.** Traffic from a laptop on the tunnel reaches a
   bench container through the host, and the kernel drops it without this.

   ```bash
   echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/99-benchpress.conf
   sudo sysctl --system
   sysctl net.ipv4.ip_forward        # net.ipv4.ip_forward = 1
   ```

5. **Install a container runtime that gives a bench its own kernel view.**
   BenchPress deploys with `sysbox-runc` by default, so a lab user gets root
   inside the bench without holding root on the host.

   ```bash
   docker info --format '{{.Runtimes}}' | grep -q sysbox && echo "sysbox ok"
   ```

   If `sysbox-runc` is not registered, either install it or change
   `default_bench_runtime` — and then read
   [Production safety](/docs/operator/production-safety) before you do,
   because `runc` without `userns-remap` makes in-container root host root.

6. **Raise the kernel ceilings if you plan to run many benches.** They are
   host-wide, and the machine image chose them, not you.

   ```bash
   sudo scripts/tune-host.sh --benches 1000
   ```

   The script lives in the `benchpress_devops` checkout, not in the app. Run
   it from there. It writes one drop-in under `/etc/sysctl.d/`, applies it,
   and re-reads `/proc/sys` to prove the raise took. Skip it on a small host
   and let [Diagnostics](/docs/operator/diagnostics) tell you when it matters.

7. **Open the WireGuard port.**

   ```bash
   sudo ufw allow 44556/udp
   ```

## Verify

Run all four. Every one must answer before you install.

```bash
docker info >/dev/null && echo "docker ok"
sysctl -n net.ipv4.ip_forward                 # 1
docker info --format '{{.Runtimes}}'          # includes sysbox-runc
bench version                                 # frappe 16.x
```

## Supported platforms

The table is about the **host that runs BenchPress**. A browser on any
operating system can reach a deployed bench over the tunnel.

|Platform|Status|Notes|
|--|--|--|
|Ubuntu 22.04 / 24.04|Supported|The primary target. Development and CI run here|
|Debian 12+|Supported|Same `apt` and `systemd` toolchain|
|Windows 11 via WSL2 (Ubuntu)|Experimental|The app and Docker work. The `vpn_management` wg-agent needs WireGuard support in the WSL kernel|
|Other Linux (Fedora, Arch)|Untested|Likely workable. `setup.sh` assumes `apt`, so adapt the package steps by hand|
|macOS, native Windows|Not supported as a host|No `apt`, no `systemd`, and no WireGuard kernel support for the wg-agent. On Windows, use WSL2|

## Versions

|Component|Required|Enforced by|
|--|--|--|
|Frappe framework (host bench)|v16|the `bench get-app` target|
|Python|3.14+|`pyproject.toml` (`requires-python`), CI|
|Node.js|24|CI, for the frontend build|
|Docker Engine|20+|container management|
|Docker Compose|v2+|the shared MariaDB and Redis pair|
|WireGuard|any recent|handled by `vpn_management`. The host needs kernel support only|
|Vue|3.5+|`frontend/package.json`|
|frappe-ui|0.1.270+|`frontend/package.json`|

A bench you deploy can target a different Frappe version than the host. A Lab
accepts `version-16`, `version-15`, `version-14` and `develop`. `develop`
tracks Frappe nightly and is unstable by definition.

## Sizing

The CPU floor was measured, not guessed. The benchmark ran on 2026-07-02 on a
two-vCPU KVM guest with an AMD EPYC 9355P host CPU and 7.8 GiB of RAM, on
Frappe 16.25.0. Docker's `--cpus` limit was applied to `benchpress_backend`
only — the service that runs migrations, authentication and API requests.
Database, Redis, nginx, websocket, scheduler and worker containers were not
capped, so these numbers describe the backend allocation, not a whole-host
limit.

Three criteria, each with its own minimum:

|Tier|Minimum CPU|Evidence at the minimum|
|--|--:|--|
|Boot and lifecycle|0.5|migration 13.22 s, login HTTP 200 in 192 ms, `/frontend` HTTP 200 in 27 ms|
|Test suite|0.5|the suite passed in 11.59 s, with every endpoint timing budget met. It held 124 tests that day. The suite has since grown by roughly an order of magnitude, so 11.59 s no longer describes a full run|
|Concurrent reads|0.5|`get_labs` p95 127 ms, `get_benches` p95 48 ms, 0 of 60 requests failed|

Concurrent reads at each candidate cap, 30 authenticated requests per endpoint
at 10-way concurrency:

|CPU cap|`get_labs` p95|`get_benches` p95|Errors|
|--:|--:|--:|--:|
|0.5|127 ms|48 ms|0|
|1|108 ms|60 ms|0|
|1.5|104 ms|57 ms|0|
|2|51 ms|71 ms|0|

**The enforced baseline is one CPU core.** The measured tier maximum is 0.5,
but `Lab.cpu_cores` is an integer field, so a fractional allocation cannot be
stored. One core is the smallest representable value at or above the measured
minimum.

Read that as a schema floor, not a performance claim. The 0.5-CPU candidate
did not visibly degrade this workload, so the measurements do not support
calling one core a minimum. Re-run the benchmark after the application grows,
or when you change the host class.

**Of the two resources measured here, disk is the constraint, not CPU.** Size
it before you buy the host. See [Disk](#disk).

**RAM was not sized.** The benchmark capped CPU only, so the 7.8 GiB above
describes the benchmark host and is not a floor. Watch `free -h` on your own
host until someone measures it.

## Disk

**A 20 GB or 40 GB VPS root disk fails mid-build.** No setting in the app
compensates for it, and the failure lands in the middle of an image build
rather than at install.

Measured on this host with `docker images` and `docker system df`, and listed
per image in [The image cache](/docs/operator/image-cache):

|Measurement|Value|
|--|--:|
|Smallest lab image|5.5 GB|
|Largest lab image|19.7 GB|
|Twelve lab images together|54.74 GB|
|Reclaimable from that set|19.12 GB|

Three costs sit on top of that image figure. A build holds the new image while
its base layers are still on disk. Every bench has its own container layer and
volumes — one deploy costs roughly 0.2 GB to 1 GB, measured in
[The image cache](/docs/operator/image-cache). The shared MariaDB carries its
data volume. The build headroom and the MariaDB volume are not measured.

So provision against the catalog you will hold, not against one image:

|The host will carry|Free disk to provision|Basis|
|--|--:|--|
|One lab image|100 GB|19.7 GB for the largest measured image, with room to rebuild it beside the copy in use|
|A catalog the size of this host's|250 GB|54.74 GB measured for twelve images, plus the same rebuild headroom, plus bench volumes|

Those two rows are recommendations derived from the measurements above. They
are not themselves measured. Watch `df -h /` and `docker system df` on your own
host, and raise them if either climbs.

Building is also the slowest thing a fresh host does. Full builds on this host
ran **4 to 26 minutes**, and the golden pass 5 to 11 — see
[The image cache](/docs/operator/image-cache). The build job's own timeout is
10,800 s, three hours, which is a ceiling and not an expected duration.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`docker info` says permission denied|The group change has not taken effect|Log out and back in, or run `newgrp docker`, then restart the bench|
|A deploy fails on the network step|IP forwarding is off|Step 4, then `sudo sysctl --system`|
|Diagnostics reports `container_runtimes` as failed|`sysbox-runc` is not registered with Docker|Install sysbox, or set `default_bench_runtime` to `runc` and read [Production safety](/docs/operator/production-safety)|
|Diagnostics reports `kernel_ceilings` as failed|The host ceilings are below what the fleet needs|`sudo scripts/tune-host.sh --benches <n>`, from the `benchpress_devops` checkout|
|A peer never handshakes|UDP 44556 is closed|Step 7, and check the cloud firewall as well as `ufw`|
|A build fails part-way with no space left|The host was sized for the OS, not for lab images|[Disk](#disk). Never run `docker image prune -a` on this host|
|**BenchPress Settings** will not save|`base_domain` is required and empty|Point a domain you control at this host, then fill it in [Install, step 5](/docs/operator/install)|

## Reference

|Requirement|Value|Where it is set|
|--|--|--|
|Docker group membership|the bench user|`setup.sh`, step 1 of 4|
|IP forwarding|`net.ipv4.ip_forward = 1`|`/etc/sysctl.d/99-benchpress.conf`|
|Default bench runtime|`sysbox`|`BenchPress Settings.default_bench_runtime`|
|WireGuard port|44556/UDP|the `WireGuard Server` document in `vpn_management`|
|Frappe version, host bench|v16|the bench itself|
|CPU floor per bench|1 core|`Lab.cpu_cores`, an integer field|
|Base domain|required, no default|`BenchPress Settings.base_domain`, `reqd`|
|Free disk, one lab image|100 GB recommended|the host you buy|
|Free disk, a full catalog|250 GB recommended|the host you buy|

## Related

* [Install](/docs/operator/install) — the next page, once every check above passes.
* [Production safety](/docs/operator/production-safety) — what this host is and is not ready for.
* [Diagnostics](/docs/operator/diagnostics) — the same checks, run by the app against the live host.
