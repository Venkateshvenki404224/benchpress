---
title: CLI and scripts
description: Every command that drives BenchPress from a shell — entry.py, the
  bench commands, setup.sh and upgrade.sh, the four repository scripts and the
  documentation pipeline.
lastModified: "2026-09-05T14:27:54-04:00"
lastAuthor: Venkatesh
---
# CLI and scripts

What you can run from a terminal, and what each one changes.

**Who this is for.** Somebody working on the host, or on a checkout.

**Before you start.** BenchPress has no `bench` subcommands of its own. Nothing
registers a command in `hooks.py`. Everything below is either the parent
repository's `entry.py`, a plain Frappe command, or a script in this repository.

## entry.py, in the parent repository

`entry.py` orchestrates the whole control plane stack in Python standard
library only. It has no dependencies to install.

Run it from `benchpress_devops`, not from this app.

|Command|Does|
|--|--|
|`./entry.py --preset benchpress --frappe-version version-16`|first-time setup: clones apps, builds the image, brings everything up|
|`./entry.py --restart`|restarts the services|
|`./entry.py --stop`|stops the services|
|`./entry.py --destroy`|removes containers **and volumes**. This is data loss|
|`./entry.py --build --preset benchpress`|rebuilds the image after a preset change|
|`./entry.py --pull`|fetches the image and recreates containers, with no local build|
|`./entry.py --push`|publishes the tag in `IMAGE_NAME`|
|`./entry.py --check-host`|reports each kernel ceiling and exits non-zero if one is too low|

Public deployment is one flag. `--domain` layers the production overlay,
moves nginx to loopback, puts Traefik on 80 and 443, and issues a wildcard
certificate.

|Flag|Does|
|--|--|
|`--domain <fqdn>`|persists `PUBLIC_HOSTNAME` and covers `*.<fqdn>`|
|`--acme-email`|the Let's Encrypt contact address|
|`--cf-token`|the Cloudflare token for the DNS-01 challenge|
|`--acme-staging`|issues untrusted certificates with no rate limit to burn|
|`--acme-production`|switches back after `--acme-staging`|
|`--reload-proxy`|re-renders the Traefik configuration and recreates only Traefik|
|`--project <name>`|a second Compose project, to run staging beside production|

Use `--acme-staging` while proving out a domain or a new token. Let's Encrypt
allows five certificates for each identifier set every seven days, and a
failed attempt still spends one.

## Bench commands

Ordinary Frappe commands, run inside the `backend` container.

```bash
docker compose exec backend bench --site frontend migrate
docker compose exec backend bench --site frontend clear-cache
docker compose exec backend bench --site frontend console
docker compose exec backend bench --site bp_test_site run-tests --app benchpress
docker compose exec backend bench build --app benchpress
```

After a Python change, restart `backend` and any worker that imports the
changed module. After a frontend change, run `bench build --app benchpress`,
then restart `backend` and `frontend`.

**Never name `frontend` in a `run-tests` command.** That site carries no
`allow_tests`, so the runner refuses it. It refuses after it disables that
site's scheduler. The runner holds the old value in memory and puts it back only
on a clean exit. A site with the scheduler off composes mail and never sends it,
and no log says so.

Test against a site made for it, such as `bp_test_site`. Create one with
`bench new-site`, then set `allow_tests` in its site config. The `migrate`,
`clear-cache` and `console` lines above name `frontend` correctly. That is your
own site.

**A multi-line block piped to `bench console` fails silently.** The console is
IPython. A block arriving on a pipe is auto-indented until it no longer parses,
and it produces no output and no error, which reads exactly like a query that
found nothing.

Wrap it in a single `exec()` call, or use `bench execute` instead:

```bash
bench --site frontend execute frappe.client.get_list \
  --kwargs "{'doctype':'Lab','fields':['name','status'],'limit_page_length':0}"
```

Use `--kwargs`, never `--args`. There is no `set-value` command. Write a value
with `frappe.client.set_value` through the same `execute` call.

## Scripts in this repository

Two shell scripts run against an existing bench.

|Script|Usage|Does|
|--|--|--|
|`setup.sh`|`bash apps/benchpress/setup.sh <site> [--strict]`|the one-time post-install setup, after `bench install-app benchpress`|
|`upgrade.sh`|`bash apps/benchpress/upgrade.sh <site> [ref] [--dry-run]`|upgrades an install end to end, behind a backup gate|

`setup.sh --strict` exits non-zero when Docker userns-remap is absent or cannot
be verified. Use it on a production host. The default warns and continues, which
suits a development box.

`upgrade.sh` aborts on any failure and takes a backup first. `--dry-run` reports
what it would do. It follows [Upgrading](/docs/operator/upgrading) step for step.

Neither script owns the VPN. Tunnels, peers and address allocation belong to the
`vpn_management` app.

## The four Python scripts

|Script|Answers|
|--|--|
|`scripts/seed_docs_demo.py`|creates or removes the demo labs and users the documentation screenshots come from|
|`scripts/admission_drill.py`|how many of N parallel deploys the admission gate really admits|
|`scripts/density_drill.py`|how many endpoints a bridge of a given prefix length really takes|
|`scripts/golden_drill.py`|what a golden restore costs against a cold deploy|

The three drills are measurement harnesses. None of them reimplements the thing
it measures. Every request goes over HTTP to the shipped endpoint, and every
duration is read back out of the run's own Deploy Log.

All three share three safety properties, and they are worth knowing before you
run one on a host serving real users.

|Property|Means|
|--|--|
|They call the host's own nginx|the public name is behind Cloudflare, which answers a dozen machine clients with `1010` rather than with the endpoint. `BENCHPRESS_URL` overrides the target|
|They refuse the wrong site|`--i-know-this-is` must match the site's own `base_domain`, read back from the control plane|
|They clean up in a `finally`|and only ever touch what they created, never filtering on status|

`density_drill.py` fills a network it made, always named `bpdrill-<n>`, and
asserts the name before the first create. A drill that filled `benchpress-0`
would take every bench on that bridge offline at the moment it believed it was
measuring capacity.

`admission_drill.py` stops `queue-long` for the run unless `--allow-deploys`.
Every deploy is enqueued after commit, so nothing reaches Redis and the whole
admission decision stays measurable with no worker running.

`golden_drill.py --cold` is the control arm. It turns `restore_from_golden` off
for the run and puts it back afterwards, so both arms deploy the same lab.

`seed_docs_demo.py --destroy` removes only what the script creates and refuses
every other name.

## The frontend

```bash
cd frontend && yarn dev        # hot reload
cd frontend && yarn test:run   # unit tests
cd e2e && npx playwright test  # end to end
```

Playwright has its own configuration in `e2e/`. Running it from the app root
resolves nothing.

**Never run `yarn lint`.** That is biome, a different style than this repository
has ever used, and it rewrites every frontend file. Lint with pre-commit:

```bash
git add -A && uvx pre-commit@4.3.0 run --all-files
```

`git add` first. pre-commit skips untracked files, so a new file lints green
while it is invisible and then fails in CI.

## The documentation pipeline

Five commands build and gate these pages. Read the exit code, never the last
line of output.

```bash
npm run docs:build && npm run docs:lint && npm run docs:score && npm run docs:links; echo "exit=$?"
```

|Command|Does|
|--|--|
|`npm run docs:site`|generates `docs-site/`: `llms.txt`, `llms-full.txt`, search and sitemap|
|`npm run docs:bundle`|generates `docs-bundle/`: `AGENTS.md`, `SKILL.md` and a markdown mirror|
|`npm run docs:build`|both of the above|
|`npm run docs:lint`|`leadtype lint docs --max-warnings 0`|
|`npm run docs:score`|`leadtype score --src docs --out docs-site --min 100`|
|`npm run docs:links`|every `.md` link in `docs-site/` and `docs-bundle/` resolves to a generated file|

Three traps are already handled by the scripts, and each cost a debugging
session to find.

1. **Lint the source folder positionally.** `leadtype lint --src .` walks the
   whole project root, finds the generated `AGENTS.md`, `SKILL.md` and
   `sitemap.md`, and reports errors because none of them carries a `title`.
   Generated files are not pages.
2. **The config is `docs.config.mjs`, not `.ts`.** A TypeScript config needs the
   optional peer dependency `jiti`. Do not convert it.
3. **Only `.mdx` belongs under `docs/`.** leadtype lists every `.md` it finds
   there in `llms.txt` but converts only `.mdx`, so a working note left in
   `docs/` is published as a link to a page that was never written. Internal
   notes live in `internal/`, and `npm run docs:links` fails on the dead link.

Never hand-edit anything under `docs-site/` or `docs-bundle/`. They are
generated, and a gate regenerates and fails on any difference.

## Verify

Confirm the whole pipeline is clean:

```bash
npm run docs:build && npm run docs:lint && npm run docs:score && npm run docs:links; echo "exit=$?"
```

`exit=0` is the only passing result.

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|`bench console` printed nothing|A piped multi-line block was truncated|Wrap it in one `exec()`, or use `bench execute`|
|`bench execute` rejects its arguments|`--args` was used|Use `--kwargs` with a dict|
|Lint fails on files you did not write|`lint --src .` scanned generated output|Run `npm run docs:lint`, which lints `docs` positionally|
|Lint passes locally and fails in CI|The new file is untracked|`git add -A` first|
|`docs:links` reports a dead link|A `.md` note under `docs/` is listed but never converted|Move it to `internal/`, then `npm run docs:build`|
|The docs config is not loaded|It was renamed to `.ts`|Rename it back to `.mjs`|
|Playwright finds no tests|It was run from the app root|Run it from `e2e/`|
|A frontend change is not visible|Assets are built, not served from source|`bench build --app benchpress`, then restart|
|`--destroy` lost the database|It removes volumes as well as containers|It says so. Use `--stop`|

## Reference

|Fact|Value|
|--|--|
|Bench subcommands this app adds|0|
|Shell scripts|`setup.sh`, `upgrade.sh`|
|Python scripts|4|
|Documentation commands|5|
|Passing pipeline result|`exit=0`|
|Lint|`uvx pre-commit@4.3.0 run --all-files`|

## Related

* [Install](/docs/operator/install) — the first `entry.py` run.
* [Upgrading](/docs/operator/upgrading) — what `upgrade.sh` automates.
* [Configuration](/docs/reference/configuration) — which change needs a rebuild.
* [Golden images](/docs/operator/golden-images) — what the golden drill measures.
