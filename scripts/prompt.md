# Ralph implementation rules

You are running unattended in a fresh session. Nobody will answer a question, so do
not ask one. If you are genuinely blocked, stop, say why in your final message, and
do not print the completion sentinel.

## What to do

Implement the single GitHub issue named in the prompt, and nothing else. The issue is
one vertical slice of the parent spec. Do not start work described by a different
issue, even if it looks trivial and adjacent. Scope creep across issues is what makes
an overnight run unreviewable.

## The repository

- Bench commands run inside the parent compose stack, not a standalone bench. From
  `/home/ubuntu/benchpress_devops` use `docker compose exec -T backend bench ...`.
- Run the app's tests with
  `bench --site frontend run-tests --app benchpress --module <module.path>` while
  working, and the whole app suite once before you commit.
- Frontend changes need `bench build --app benchpress`, then restart backend and
  frontend.
- Schema changes need `bench --site frontend migrate`.
- Query with `frappe.qb`, never raw SQL. Every whitelisted method checks permissions
  itself.
- Behaviour lives in doctype controllers and `hooks.py` as often as in the obvious
  module. Read `hooks.py` before assuming a save does the plain thing.

## Style

- Match the Frappe framework's own sparse comment style. Few comments, short or no
  docstrings. Do not write a block comment above a function or a rule explaining why
  the decision was made — that belongs in the commit message.
- A `PostToolUse` hook caps docstrings at two lines. The hook is a ceiling, not a
  target.
- Every token comes from the brand stylesheet. Never a raw hex value.
- Load the `code-style` skill for any code change, and `frappe-app-dev` for any
  Frappe work.

## Before you commit

1. `uvx pre-commit@4.3.0 run --all-files` must pass. Never run `yarn lint`.
2. The full app test suite must pass.
3. Use `/code-review` on your own work and act on what it finds.
4. Write the message with the `technical-writing` skill: plain and short, with a
   Conventional Commits header (`type(scope): summary`).
5. Commit to the branch you are already on. Do not create a branch, do not push, do
   not open or merge a pull request, and do not touch any other issue.

## When you are done

Print, as the last line of your final message, exactly:

<promise>COMPLETE</promise>

Print it only if the code is committed, pre-commit passed and the tests passed. If
any of those is untrue, explain what stopped you and print nothing.
