# Contributing to BenchPress

Thanks for your interest in contributing to BenchPress! This guide will help you get started.

## Licence and the CLA

BenchPress is licensed under the **GNU Affero General Public License v3.0 only**
([license.txt](license.txt)). Contributions are accepted under the same licence.

Before your first pull request can be merged you must sign the
[Contributor License Agreement](.github/CLA.md). It is a one-time, in-thread
signature: open a PR, and a bot comments with the document and a line to reply
with. **You keep the copyright in your work** — the CLA is a broad, sublicensable
licence grant, not an assignment. [.github/CLA.md](.github/CLA.md) explains why a
CLA rather than a DCO.

The BenchPress name and logo are *not* covered by the AGPL grant — see
[TRADEMARKS.md](TRADEMARKS.md).

## Development Setup

```bash
cd /path/to/your/frappe-bench

# Get the app
bench get-app https://github.com/Venkateshvenki404224/benchpress --branch develop
bench pip install docker
bench --site your-site.localhost install-app benchpress
bench --site your-site.localhost migrate

# Frontend dev server (hot-reload)
cd apps/benchpress/frontend
yarn install
yarn dev
```

BenchPress declares `required_apps = ["vpn_management"]` and will not install
without it; `bench get-app` resolves it automatically from
[Venkateshvenki404224/vpn_management](https://github.com/Venkateshvenki404224/vpn_management).

## Branch Strategy

Three long-lived branches, promoted in one direction and never the other:

- **`develop` — development.** Feature and fix branches start here and merge back
  here. This is where work lands first.
- **`version-16` — staging.** What the staging deployment runs, and the
  repository's default branch. `develop` merges here once it holds together.
- **`main` — production.** A release *is* a merge into `main` plus a `vX.Y.Z` tag.
  The README's install instructions point here, so whatever is on `main` is what
  a new user gets.

Work branches take the commit type as their prefix: `feat/<name>`, `fix/<name>`,
`docs/<name>`, `refactor/<name>`, `test/<name>`, `chore/<name>`.

Never commit directly to any of the three. Note that GitHub will offer
`version-16` as the base for a new PR because it is the default branch — change
it to `develop`.

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

feat(device): add persistent VPN device management
fix(deploy): prevent duplicate container on rapid double-click
refactor(api): migrate queries to frappe.qb
test(lab): add tests for build validation
docs(readme): update API reference
chore(deps): upgrade frappe-ui to v0.90
perf(stats): cache container stats in Redis
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

## Verification before you push

Run these three, in this order. Together they are what CI checks.

**1. Formatting and linting — everything, Python and frontend:**

```bash
uvx pre-commit@4.3.0 run --all-files
```

This is the formatter of record: ruff for Python, prettier and eslint for
JavaScript and Vue. **Do not run `yarn lint`** — it runs biome with a different
style than the repo has ever used and will rewrite every frontend file.

**2. Backend tests:**

```bash
bench --site <your-site> run-tests --app benchpress
```

**3. Frontend unit tests:**

```bash
cd frontend && yarn test:run
```

End-to-end tests are optional locally, and must be run from `e2e/` — invoking
Playwright from the app root resolves no config and every test fails
unauthenticated:

```bash
cd e2e && FRAPPE_BASE_URL=http://localhost:8080 \
  FRAPPE_ADMIN_USER=administrator FRAPPE_ADMIN_PASSWORD=<password> \
  npx playwright test
```

## Key Rules

- Use `frappe.qb` Query Builder for all database queries — never `frappe.db.sql`
- Use `createDocumentResource` / `createListResource` from frappe-ui for data fetching
- Every `@frappe.whitelist()` endpoint must check permissions
- No `console.log` in production JS code
- No hardcoded credentials or API keys

## Dependencies

Adding, removing, or upgrading a dependency means the notices file is stale.
Regenerate it in the same PR:

```bash
docker compose exec backend bash -lc \
  'cd apps/benchpress && ./scripts/generate-third-party-notices.sh'
```

Do not hand-edit [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Prefer dependencies under permissive or GPL-compatible licences. A dependency
under a licence incompatible with AGPL-3.0 (SSPL, BUSL, or anything
source-available with a commercial-use restriction) cannot be merged.

## Pull Requests

1. Create a branch from `develop`
2. Make your changes with conventional commit messages
3. Run the three verification commands above before pushing
4. Open a PR targeting `develop` — GitHub will preselect `version-16`, so change it
5. Describe **what** changed and **why** in the PR description
6. Link any related issues
7. Sign the CLA when the bot asks

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Frappe version and environment details
- Screenshots if applicable

**Security bugs do not go in issues** — see [SECURITY.md](SECURITY.md).
