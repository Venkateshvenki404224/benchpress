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

### Added

- Documented, backup-gated upgrade path for installed instances: a manual
  runbook ([`docs/upgrading.md`](docs/upgrading.md)) and a scripted
  [`upgrade.sh`](upgrade.sh) that chains backup → app update → `bench migrate` →
  asset rebuild → restart → health verify. The pre-upgrade backup is a hard
  gate — the upgrade aborts if it fails, so there is always something to roll
  back to. ([#47](https://github.com/Venkateshvenki404224/benchpress/issues/47))
- This changelog, so installs can be upgraded safely across multiple releases.
  ([#47](https://github.com/Venkateshvenki404224/benchpress/issues/47))

[Unreleased]: https://github.com/Venkateshvenki404224/benchpress/commits/develop
