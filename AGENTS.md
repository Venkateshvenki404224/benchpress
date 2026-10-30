# BenchPress — for coding agents

> Self-hosted Frappe dev environments, deployed from a template.

**Read [`docs-bundle/AGENTS.md`](docs-bundle/AGENTS.md) first.** It lists all 40
documentation pages as relative links, each with a one-line description, and
every page is flattened Markdown you can read without a browser. It is generated
from this checkout, so it matches the code beside it.

Route by the task:

| Task | Start at |
|---|---|
| Use a bench somebody deployed for you | [`docs-bundle/docs/user/quick-tour.md`](docs-bundle/docs/user/quick-tour.md) |
| Install or run BenchPress on a host | [`docs-bundle/docs/operator/index.md`](docs-bundle/docs/operator/index.md) |
| Call the HTTP API | [`docs-bundle/docs/reference/api.md`](docs-bundle/docs/reference/api.md) |
| Change the code | [`docs-bundle/docs/reference/architecture.md`](docs-bundle/docs/reference/architecture.md) |
| Look up a DocType or a field | [`docs-bundle/docs/reference/data-model.md`](docs-bundle/docs/reference/data-model.md) |
| Find what a word means here | [`docs-bundle/docs/reference/glossary.md`](docs-bundle/docs/reference/glossary.md) |

## Rules for editing this repository

- **Documentation source is `docs/**/*.mdx`.** Everything under `docs-site/` and
  `docs-bundle/` is generated. Never edit a generated file. Edit the `.mdx`, then
  run `npm run docs:build`.
- **Nothing but page source lives under `docs/`.** leadtype lists every `.md` it
  finds there in `llms.txt` but converts only `.mdx`, so a working note dropped
  in `docs/` becomes a dead link an agent follows. Internal notes go in
  `internal/`.
- **Lint the source folder positionally: `npm run docs:lint`.** It runs
  `leadtype lint docs`. Passing `--src .` makes leadtype lint its own output and
  report errors on generated files that are not pages.
- **Every page needs `title` and `description` in its frontmatter.** A missing
  `description` costs 5 score points and leaves the page out of the routing hints
  in `llms.txt`.
- **Query with `frappe.qb`, never `frappe.db.sql`.** A raw string query is a lint
  failure.
- **Every `@frappe.whitelist()` function checks permissions itself.** The
  decorator publishes the function. It grants nothing.
- **Check `benchpress/hooks.py`** before assuming a save or a submit does the
  plain thing. Behavior lives there as well as in the controller.
- **Run `uvx pre-commit@4.3.0 run --all-files` before you push**, and `git add`
  first. pre-commit skips untracked files.
- **Never run `yarn lint`.** That is biome, a style this repository has never
  used, and it rewrites every frontend file.

`CLAUDE.md` carries the same conventions with more detail on the compose
topology. [`CONTRIBUTING.md`](CONTRIBUTING.md) is the full contributor guide.

## Fresh checkout, dev server and checks

- **Setup.** A fresh checkout or worktree needs no `.env`. Install the SPA's
  dependencies with `cd frontend && npx yarn@1.22.22 install --frozen-lockfile`,
  and the docs toolchain with `npm ci --ignore-scripts` from the root.
- **Dev server.** `cd frontend && npx yarn@1.22.22 dev --port <port>` serves the
  SPA. It proxies API calls to a Frappe backend on `127.0.0.1:8000`; without
  one, pages that load data show their error or empty state.
- **Validation.** `bash factory/checks.sh` runs what CI's lint, frontend and docs
  jobs run: `uvx pre-commit@4.3.0 run --all-files`, the frontend unit tests
  (`yarn test:run`) and build (`yarn build`), and, when a branch touches docs,
  `npm run docs:build`, `docs:lint` and `docs:score` plus a check that the
  generated files are committed.
- **Server tests** need a bench and a site. Locally that is
  `docker compose exec backend bench --site frontend run-tests --module <module>`,
  which runs the code in `apps/benchpress`, not in a worktree. CI's Server job
  runs the whole suite on every pull request.

## Software factory

`/factory run` builds every open GitHub issue labeled `factory` through
intake → spec → build → gate → review → approve, one PR per issue into
`develop`. State is in `factory/jobs/` (gitignored); `factory/bin/job` is its
only writer. Checks: `factory/checks.sh`. A job merges only after its PR's
GitHub checks pass. Dashboard: `cd factory && python3 -m http.server`, then open
http://localhost:8000/dashboard.html.
