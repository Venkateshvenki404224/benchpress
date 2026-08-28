# Changelog

All notable changes to BenchPress are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Why this file exists.** When you upgrade an install across more than one
> release, read every entry between your current version and the target version
> before running the upgrade — some changes need manual steps. The
> [upgrade runbook](docs/upgrading.md) points here for exactly that reason.
>
> This changelog was introduced partway through development, so it does not
> restate the project's full early history — for changes before the first entry
> below, see the git log and GitHub release notes.

**Maintaining this changelog**

- Add a bullet under `## [Unreleased]` in the same change that ships the work,
  grouped under one of: **Added**, **Changed**, **Deprecated**, **Removed**,
  **Fixed**, **Security**. Lead with what an operator would notice, and link the
  issue or PR.
- Flag anything that needs a manual step during upgrade (a schema change, a
  config or setting rename, a removed field) so multi-release upgrades stay safe.
- On a release, rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`, tag the
  commit `vX.Y.Z`, and open a fresh empty `## [Unreleased]` above it. Bump the
  version per Semantic Versioning: MAJOR for breaking changes, MINOR for
  backwards-compatible features, PATCH for fixes.

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-08-28

### Added

- Nightly MariaDB dumps are now copied to host disk
  (`sites/<site>/private/backups/mariadb/`), off the database volume, with 7-day
  retention enforced on the new location — losing the DB volume no longer loses
  the backups. A documented, once-verified restore runbook
  ([`docs/database-backup-restore.md`](docs/database-backup-restore.md)) and a
  console-only `restore_database_server()` helper close the loop.
  ([#96](https://github.com/Venkateshvenki404224/benchpress/issues/96))
- Documented, backup-gated upgrade path for installed instances: a manual
  runbook ([`docs/upgrading.md`](docs/upgrading.md)) and a scripted
  [`upgrade.sh`](upgrade.sh) that chains backup → app update → `bench migrate` →
  asset rebuild → restart → health verify. The pre-upgrade backup is a hard
  gate — the upgrade aborts if it fails, so there is always something to roll
  back to. ([#47](https://github.com/Venkateshvenki404224/benchpress/issues/47))
- This changelog, so installs can be upgraded safely across multiple releases.
  ([#47](https://github.com/Venkateshvenki404224/benchpress/issues/47))
- Deploys restore a prepared site instead of building one. The site is created once
  at image-build time, dumped, and verified by restoring it into a scratch
  database before the layer is kept — so a golden is never appended unverified.
  Site step 37.2s to 9.1s, whole deploy 43.3s to 13.3s, same image and lab. A dump
  from a different MariaDB major version is refused at deploy time with the reason
  in the log. ([#165](https://github.com/Venkateshvenki404224/benchpress/pull/165))
- Deploys no longer spend time correcting file ownership on every run, which left
  site creation as the whole remaining cost and set up the change above.
  ([#150](https://github.com/Venkateshvenki404224/benchpress/pull/150))
- Labs are described once and deployed by anyone: a `Lab Template` doctype, a
  catalog of Frappe v16 templates, and automatic patching of template app
  dependencies. ([#148](https://github.com/Venkateshvenki404224/benchpress/pull/148), [#149](https://github.com/Venkateshvenki404224/benchpress/pull/149), [#147](https://github.com/Venkateshvenki404224/benchpress/pull/147))
- Every bench answers on a real public hostname, and the requester chooses the
  site name. The name is claimed by insert before any work is queued, so two
  callers can no longer end up sharing one database.
  ([#140](https://github.com/Venkateshvenki404224/benchpress/pull/140), [#141](https://github.com/Venkateshvenki404224/benchpress/pull/141))
- A new bench costs no certificate issuance. Per-bench routers serve the wildcard
  certificate already in the store rather than requesting their own — Let's
  Encrypt allows five certificates per identifier per seven days, so
  issuance-per-spawn capped the platform at roughly five benches a week.
  ([#157](https://github.com/Venkateshvenki404224/benchpress/pull/157))
- Routing changes without restarting the proxy. Each bench owns one file in a
  host-bind directory, written on spawn and deleted on teardown, and a scheduled
  pass makes the directory converge on the database instead of accreting. A route
  names the container, so a recycled address cannot point a hostname at another
  tenant's bench. ([#158](https://github.com/Venkateshvenki404224/benchpress/pull/158))
- Benches spread across indexed network bridges instead of one. A single hard-coded
  `/24` would have refused the platform's 250th bench; placement now takes the
  lowest bridge with room and records which one a bench was built on.
  ([#164](https://github.com/Venkateshvenki404224/benchpress/pull/164))
- Per-plan cpu, memory, pids and disk limits, clamped inside the engine adapter,
  with the deploy log distinguishing an enforced quota from one the engine
  silently ignored. ([#246](https://github.com/Venkateshvenki404224/benchpress/pull/246))
- Per-bench request limits: separate routers for assets, the site and the IDE, each
  with its own rate limit keyed on the real client address behind Cloudflare, plus
  an in-flight cap on the render router. Saturating a bench's renders no longer
  affects its assets or its IDE session. **The in-flight ladder ships unset — see
  the upgrade notes.** ([#257](https://github.com/Venkateshvenki404224/benchpress/pull/257))
- Failures are reported rather than polled for. A `docker events` consumer feeds a
  worker that raises OOM, died and unhealthy notifications, benches carry a probe
  on `/api/method/ping`, and Traefik ejects an unhealthy bench from routing.
  ([#256](https://github.com/Venkateshvenki404224/benchpress/pull/256))
- One reconciliation loop owns the database-to-reality direction, and every reap
  reports what it issued against what actually went away. Teardown now frees the
  bench's VPN peer, which every reaped bench had previously held forever.
  ([#258](https://github.com/Venkateshvenki404224/benchpress/pull/258))
- Metering by lease, with preempting verbs and an age ceiling on reclaim. **Credits
  remain disabled unless you turn them on — see the upgrade notes.**
  ([#160](https://github.com/Venkateshvenki404224/benchpress/pull/160))
- A narrated hero film on the landing page, and a Start action for stopped benches.
  ([#155](https://github.com/Venkateshvenki404224/benchpress/pull/155), [#151](https://github.com/Venkateshvenki404224/benchpress/pull/151))

### Changed

- Bench containers run unprivileged by default. A tenant deploying through the SPA
  now gets a user-namespaced container (`uid_map 0 231072 65536`) rather than one
  sharing the host's user namespace. The runtime field sits at permission level 1,
  so a tenant cannot lower their own isolation, and an unavailable runtime fails
  before the image build rather than minutes into it. ([#159](https://github.com/Venkateshvenki404224/benchpress/pull/159))
- The shared MariaDB and Redis now read the configuration this project writes for
  them. Both mounted a config file and neither had ever read one, because the
  bind paths resolved inside a container the host could not see — so Redis had run
  unbounded with `noeviction` while destroyed benches still held keys in it. Redis
  is now capped at 256 MB with `allkeys-lru`, MariaDB at 500 connections.
  **Requires recreating both containers — see the upgrade notes.**
  ([#208](https://github.com/Venkateshvenki404224/benchpress/pull/208))
- Routing, addressing, bridge placement, site naming and the bench lifecycle each
  moved into their own module, out of the deploy orchestrator. The lifecycle change
  deletes a duplicate start path that had already drifted from the one beside it.
  Behaviour is unchanged; enqueued job names moved.
  ([#209](https://github.com/Venkateshvenki404224/benchpress/pull/209), [#226](https://github.com/Venkateshvenki404224/benchpress/pull/226), [#228](https://github.com/Venkateshvenki404224/benchpress/pull/228), [#233](https://github.com/Venkateshvenki404224/benchpress/pull/233))
- Scheduled Docker work is enqueued onto a queue whose worker actually mounts the
  Docker socket, instead of running where the socket is absent.
  ([#200](https://github.com/Venkateshvenki404224/benchpress/pull/200))
- Corrected how the project describes itself, refreshed the brand, and fixed stale
  documentation, in preparation for the source being public. ([#139](https://github.com/Venkateshvenki404224/benchpress/pull/139))
- Install instructions point at `main`, which now tracks the released code.
  `develop` is the integration branch and `version-16` the staging branch; a
  release is what lands on `main` and gets tagged. Pin an install with
  `--branch v0.1.0`.
- The landing page serves its own web fonts and carries the new logo lockup, and
  the documentation screenshots were recaptured against the current interface.
  ([#162](https://github.com/Venkateshvenki404224/benchpress/pull/162), [#152](https://github.com/Venkateshvenki404224/benchpress/pull/152), [#153](https://github.com/Venkateshvenki404224/benchpress/pull/153))

### Removed

- `Bench Site.full_domain`. It duplicated the site name and drifted from it, which
  is why teardown used to drop both candidate names to avoid orphaning a database.
  **Requires `bench migrate`.** ([#228](https://github.com/Venkateshvenki404224/benchpress/pull/228))
- `Database Server.custom_config` and its section. It fed a configuration path that
  never reached the database server. ([#208](https://github.com/Venkateshvenki404224/benchpress/pull/208))

### Fixed

- Concurrent requests can no longer over-admit. A slot is now a row whose name is
  its primary key, claimed under a lock every contender must take. Measured with
  twelve simultaneous callers against a cap of one: twelve were admitted before
  this change, one after. Credits became a hold rather than a check, and the start
  path the interface actually uses came behind the same decision.
  ([#161](https://github.com/Venkateshvenki404224/benchpress/pull/161))
- The shared database is resolved by container name rather than a stored container
  id, which changes on every recreate. Applying the configuration above used to
  break every subsequent bench deploy until the stored id was refreshed by hand.
  ([#224](https://github.com/Venkateshvenki404224/benchpress/pull/224))
- Shell quoting in the bench user setup, and reconciliation of containers that had
  died. ([#156](https://github.com/Venkateshvenki404224/benchpress/pull/156))
- Four test modules asserted against every row on the site, so they failed on any
  host with real data. They now use their own fixtures. ([#206](https://github.com/Venkateshvenki404224/benchpress/pull/206))

### Security

- No secret reaches the Docker event stream. File contents are uploaded as an
  archive instead of echoed through a shell heredoc, database users are created
  from a password hash rather than the plaintext, and the bench SSH password
  travels in the environment rather than the command line. Verified across a live
  deploy: 85 exec events, and no hit for the SSH, code-server or admin passwords,
  the WireGuard private key, or the site's database password.
  ([#207](https://github.com/Venkateshvenki404224/benchpress/pull/207))
- The MariaDB root password is no longer on the database container's command line,
  where `docker inspect` published it to anyone with Docker access. The exposed
  password has been rotated.
  ([benchpress_devops#6](https://github.com/Venkateshvenki404224/benchpress_devops/pull/6))
- Recorded the rule that no component may assume a port can be opened inward to a
  bench host. ([#189](https://github.com/Venkateshvenki404224/benchpress/pull/189))

### Upgrade notes

Read all of these before upgrading an existing install.

1. **Run `bench migrate`.** This release removes `Bench Site.full_domain` and adds
   fields and doctypes for admission and per-plan limits.
2. **Recreate the shared services** so the MariaDB and Redis settings take effect:
   `cd benchpress/config && docker compose up -d`. This briefly interrupts every
   running bench's database connection — Frappe opens a connection per request, so
   a request in flight fails and the next succeeds.
3. **The in-flight request cap ships unset.** Until you seed
   `Instance Size.inflight_limit`, no bench has one. This is deliberate: the ladder
   is a capacity decision. Setting a tier to 0 means no cap; values are clamped at
   24.
4. **Credits stay off** until `BenchPress Settings.enable_credits` is enabled.
   Nothing meters or refuses while it is off.
5. **Health probes apply at container creation.** Benches that predate this release
   report no health status until they are redeployed.
6. **Two pieces of this release are host work, and BenchPress ships neither.**
   The events listener needs a long-running process for
   `benchpress.docker_events.run` that carries the Docker socket and comes back
   after a reboot — a compose service, a systemd unit, or a supervisor entry. And
   a dense fleet needs its kernel ceilings raised once, under `/etc/sysctl.d`:
   `kernel.pid_max`, `kernel.pty.max`, `fs.file-max`, `fs.nr_open`,
   `net.netfilter.nf_conntrack_max`, `net.ipv4.neigh.default.gc_thresh{1,2,3}`,
   `net.core.netdev_max_backlog` and `net.ipv4.tcp_max_syn_backlog`. Each target
   scales with the bench count. Verify by reading `/proc/sys` afterwards, not the
   file you wrote — a drop-in is a request, not a value. The reference deployment
   of both lives in a separate orchestration repository that is not public.

[Unreleased]: https://github.com/Venkateshvenki404224/benchpress/compare/v0.1.0...version-16
[0.1.0]: https://github.com/Venkateshvenki404224/benchpress/releases/tag/v0.1.0
