`<reasoning_effort>40</reasoning_effort>`

# verification_gates

This repo has 1450 Python tests, 153 SPA unit tests and a Playwright suite, and it runs six CI
jobs across two workflows — but `version-16` carries no branch protection and no rulesets, so
every one of those checks is advisory and a red run can still merge. That makes the local gate the
real gate. Claude runs the checks before pushing rather than after, because nothing downstream
will stop a mistake.

The test before pushing: **which of these six jobs would this change turn red, and has Claude
actually run that one?**

## the_suites

- Python tests run under Frappe's own runner — `bench --site <site> run-tests --app benchpress` —
  which is unittest, not pytest, so a pytest-only fixture or a bare `assert` idiom will not run.
- Claude never names `frontend` as the test site. That site carries no `allow_tests`, and an
  interrupted run leaves its scheduler disabled from a value the runner held in memory — a site
  with the scheduler off composes mail and never sends it, silently.
- The site to use is `bp_test_site` locally and `test_site` in CI, where `ci.yml` sets
  `allow_tests true` before the run.
- 72 test files hold the 1450 tests, and they mirror the module under test —
  `benchpress/tests/test_docker_manager.py` for `benchpress/docker_manager.py`. Claude adds a test
  to the mirror file rather than starting a new one.
- The SPA suite is `cd frontend && yarn test:run` — vitest over `src/**/*.spec.js`, 13 files.
  `yarn build` only proves the bundle compiles, which is why `ci.yml` runs both.
- Playwright lives in `e2e/` with its own config; `cd e2e && npx playwright test` is the only
  invocation that resolves, since running from the app root finds nothing.
- A test cleans up what it created — labs, bench instances, ledger entries, waitlist entries,
  users — in the same run, because test users have been found alive on a live site holding
  `System Manager`.

## lint_and_format

- One command runs the Python and JavaScript gates together: `uvx pre-commit@4.3.0 run
  --all-files`, which is exactly what the `Frappe Linter` job runs.
- Claude never runs `yarn lint`. That script is biome, a style this repo has never used, and it
  rewrites every file under `frontend/`.
- ruff is configured at `pyproject.toml:26-27` with `line-length = 110` and
  `target-version = "py314"`, and it runs three times in pre-commit — import sorter, linter,
  formatter.
- `E501` sits in the ignore list, so ruff does **not** enforce that 110-character limit; it is a
  formatter target and a convention, and Claude honours it by hand.
- The formatter uses tabs and double quotes (`[tool.ruff.format]`), which is why the Python in
  this tree is tab-indented — Claude matches it rather than reformatting a file it touched.
- Nothing in this repo typechecks. There is no tracked `tsconfig.json`, the SPA is plain
  JavaScript, and the 23 `.ts` files are Playwright specs that only the ungated e2e run compiles.
- Docstrings are capped at two lines by a `PostToolUse` hook,
  `.claude/hooks/docstring_limit.py`, which flags only docstrings the current edit touched.

## the_ci_jobs

| Job (workflow) | Runs on | Gates | Blocking |
|---|---|---|---|
| `Detect Changes` (`ci.yml`) | pull requests | Path filter feeding the two jobs below | Advisory |
| `Server` (`ci.yml`) | backend paths; 60-min cap | 1450 tests + a page-load check on `test_site` | Advisory |
| `Frontend` (`ci.yml`) | `frontend/**` | `yarn test:run` then `yarn build` | Advisory |
| `Docs` (`ci.yml`) | every push and PR, ungated | build, lint, score, dead links, drift | Advisory |
| `Frappe Linter` (`linter.yml`) | pull requests only | pre-commit + semgrep diff scan | Advisory |
| `Vulnerable Dependency Check` (`linter.yml`) | every push and PR | `pip-audit` over the manifest | Advisory |

- Every row reads "Advisory" because `version-16` has no protection rule and no ruleset. The
  comment at `ci.yml:24-26` still describes `Server` and `Frontend` as required checks; the
  branch-protection API answers "Branch not protected", and the ruleset list is empty.
- The path filter excludes `docs/`, `docs-site/`, `docs-bundle/`, `internal/` and every `.md` and
  `.mdx`, so a docs-only change never wakes the 60-minute `Server` job — Claude does not add a
  code path to those exclusions.
- Semgrep runs on pull requests only, deliberately: `semgrep ci` full-scans on push and would fail
  on findings no pull request has seen.
- The Docs job fails on any diff under `docs-site/` or `docs-bundle/` it did not produce, so a
  docs change means `npm run docs:build` and committing the regenerated trees in the same commit.

## commits_and_branches

- `version-16` is the only trunk. Claude branches from it and targets it — `main` and `develop`
  were abandoned at the 0.1.0 release, as `CONTRIBUTING.md:70-72` records, whatever
  `CLAUDE.md:232` still says.
- A branch takes its commit type as a prefix: `feat/<name>`, `fix/<name>`, `docs/<name>`,
  `refactor/<name>`, `test/<name>`, `chore/<name>`.
- Conventional Commits are the rule and nothing enforces them — 51 of the last 200 non-merge
  commits carry headers such as `Implemented phase two (#228)`, because no CI job reads a message.
- The header is `type(scope): summary`, lowercase after the colon, and both the header and every
  body line stay within 100 characters.
- The body says what changed, why, what it corrects and what it deliberately leaves out, since the
  diff already says how.

## what_not_to_do

- Do not run any `run-tests` command against the `frontend` site.
- Do not run `yarn lint`, and do not add biome to a hook or a workflow.
- Do not assume a green PR page means the checks passed — read each job, because none of them
  blocks a merge today.
- Do not edit `docs-site/` or `docs-bundle/` by hand, and do not commit a docs change without
  regenerating them.
- Do not add a pytest-only construct to the Python suite; the runner is unittest.
- Do not push a commit whose header is not `type(scope): summary` just because CI would let it
  through.
- Do not leave a new Playwright spec as the only coverage for a change — nothing runs `e2e/` in CI.
