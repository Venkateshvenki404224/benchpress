# Contributing to BenchPress

Thanks for your interest in contributing to BenchPress! This guide will help you get started.

## Licence and the CLA

BenchPress is licensed under the **GNU Affero General Public License v3.0 only**
([license.txt](license.txt)). Contributions are accepted under the same licence.

Before your first pull request can be merged you must sign the
[Contributor License Agreement](.github/CLA.md). Sign it by posting this comment
on your pull request:

```
I have read the CLA Document and I hereby sign the CLA.
```

One signature covers every contribution you make afterwards.

**What you are granting, plainly.** You keep the copyright in your work. The CLA
is a licence grant, not an assignment, so your own code stays yours to use, sell
or relicense however you like. But the grant is **sublicensable**: the project
owner may ship your contribution under licence terms other than AGPL-3.0,
including a commercial licence, without asking you again. That asymmetry is
real, and this is the place to weigh it.

**Why we ask for it.** A Developer Certificate of Origin grants no sublicensing
right, so under a DCO every contributed file would be locked to AGPL-3.0 for
good. If that trade is not one you want to make, open an issue and describe the
fix instead of sending a patch — that costs you nothing and still helps.

[.github/CLA.md](.github/CLA.md) is the full text.

The BenchPress name and logo are *not* covered by the AGPL grant — see
[TRADEMARKS.md](TRADEMARKS.md).

## Development Setup

```bash
cd /path/to/your/frappe-bench

# Get the dependency first, then the app
bench get-app https://github.com/Venkateshvenki404224/vpn_management --branch version-16
bench get-app https://github.com/Venkateshvenki404224/benchpress --branch version-16
bench pip install docker
bench --site your-site.localhost install-app benchpress
bench --site your-site.localhost migrate

# Frontend dev server (hot-reload)
cd apps/benchpress/frontend
yarn install
yarn dev
```

BenchPress declares `required_apps = ["vpn_management"]` in `hooks.py` and will
not install without it. `bench get-app` does **not** fetch it for you: the
`--resolve-deps` flag defaults to off, and without it bench prints an
`Ignoring dependencies of ...` warning and carries on. Fetch
[vpn_management](https://github.com/Venkateshvenki404224/vpn_management) first,
as above, or pass `--resolve-deps` to the `benchpress` get-app.

## Branch Strategy

**One trunk: `version-16`.** It is the default branch on GitHub, it carries the
`v0.1.0` tag, and it is what the install instructions in
[docs/operator/install.mdx](docs/operator/install.mdx) fetch. Branch from it,
merge back into it. GitHub already preselects it as the base for a new pull
request, so leave the base alone.

`main` and `develop` also exist. Both were left at the 0.1.0 release commit and
neither is updated any more. Do not branch from them, do not target them, and do
not treat anything on them as current.

A release is a `vX.Y.Z` tag on `version-16`.

Work branches take the commit type as their prefix: `feat/<name>`, `fix/<name>`,
`docs/<name>`, `refactor/<name>`, `test/<name>`, `chore/<name>`.

Never commit directly to `version-16`.

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

Run these four, in this order.

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

**4. End-to-end tests.** Run these from `e2e/`. Invoking Playwright from the app
root resolves no config, and every test then fails unauthenticated:

```bash
cd e2e && FRAPPE_BASE_URL=http://localhost:8080 \
  FRAPPE_ADMIN_USER=administrator FRAPPE_ADMIN_PASSWORD=<password> \
  npx playwright test
```

### What CI checks

Two workflows, five checking jobs. Commands 1 to 3 above are gated here.
Command 4 is not:

| Job | Workflow | What it runs |
|---|---|---|
| Frappe Linter | `linter.yml` | `pre-commit`, then the frappe semgrep rules plus `r/python.lang.correctness` |
| Vulnerable Dependency Check | `linter.yml` | `pip-audit` over the Python dependencies |
| Server | `ci.yml` | `run-tests --app benchpress` on a fresh bench, then a page-load check on `/frontend` |
| Frontend | `ci.yml` | `yarn install --frozen-lockfile`, `yarn test:run`, `yarn build` |
| Docs | `ci.yml` | `docs:build`, `docs:lint`, `docs:score`, `docs:links`, and a check that `docs-site/` and `docs-bundle/` are committed and current |

The Playwright suite is **local only**. It needs a running site with
administrator credentials, which no CI job provisions. Run it yourself against
your bench before you push anything that touches a page or a route.

`Server` and `Frontend` are path-filtered on pull requests. A change under
`frontend/` alone skips `Server`, and so does a docs-only change: the `Server`
filter excludes `docs/`, `docs-site/`, `docs-bundle/`, `internal/` and every
`.md` and `.mdx`. A change that touches neither `frontend/` nor
`.github/workflows/ci.yml` skips `Frontend`. A skipped job counts as passing.

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

1. Create a branch from `version-16`
2. Make your changes with conventional commit messages
3. Run the four verification commands above before pushing
4. Open a PR targeting `version-16` — GitHub preselects it, so leave the base alone
5. Describe **what** changed and **why** in the PR description
6. Link any related issues
7. Sign the CLA on your first PR, as described above

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Frappe version and environment details
- Screenshots if applicable

**Security bugs do not go in issues** — see [SECURITY.md](SECURITY.md).
