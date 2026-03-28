# Contributing to BenchPress

Thanks for your interest in contributing to BenchPress! This guide will help you get started.

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

## Branch Strategy

- `main` — production, always deployable
- `develop` — integration branch
- `feature/<name>` — feature branches from `develop`
- `fix/<name>` — bug fix branches from `main`

Never commit directly to `main` or `develop`.

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

## Code Style

**Python:**
```bash
cd apps/benchpress
python -m ruff check .
python -m ruff format .
```

**JavaScript/Vue:**
```bash
cd apps/benchpress/frontend
npx prettier --write src/
```

## Key Rules

- Use `frappe.qb` Query Builder for all database queries — never `frappe.db.sql`
- Use `createDocumentResource` / `createListResource` from frappe-ui for data fetching
- Every `@frappe.whitelist()` endpoint must check permissions
- No `console.log` in production JS code
- No hardcoded credentials or API keys

## Pull Requests

1. Create a branch from `develop`
2. Make your changes with conventional commit messages
3. Run linters before pushing
4. Open a PR targeting `develop`
5. Describe **what** changed and **why** in the PR description
6. Link any related issues

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Frappe version and environment details
- Screenshots if applicable
