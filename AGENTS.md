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
