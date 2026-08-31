# Ralph implementation rules

You are running unattended in a fresh session. Nobody will answer a question, so do
not ask one. If you are genuinely blocked, stop, say why in your final message, and
do not print the completion sentinel.

## The implement instructions

These are the `/implement` skill's own instructions. They govern this session:

> Implement the work described by the user in the spec or tickets.
>
> Use `/tdd` where possible, at pre-agreed seams.
>
> Run typechecking regularly, single test files regularly, and the full test suite
> once at the end.
>
> Once done, use `/code-review` to review the work.
>
> Commit your work to the current branch.

## Scope

Implement the single GitHub issue named in the prompt, and nothing else. The issue is
one vertical slice of parent spec #288. Do not start work described by a different
issue, even if it looks trivial and adjacent. Scope creep across issues is what makes
an overnight run unreviewable.

## The pre-agreed seams

`/implement` says to use `/tdd` at pre-agreed seams. These are those seams, agreed on
the parent spec. Do not introduce a new one. A good test asserts what a visitor or an
operator can observe, never how it is produced.

1. **Rendering a route as a guest.** Render a public route through the framework's
   website-serving helper and assert against the returned HTML. This is the highest
   seam available and carries most of the work: shipped copy with no rows behind it,
   identical chrome across routes, the absence of the framework bundle, the link
   preview tags, and every route's behaviour with the public-site flag off. Prior
   art: the landing tests and the site-content tests.
2. **Calling the whitelisted public functions directly.** Carries endpoint behaviour:
   storage, acknowledgement, topic routing, per-endpoint rate limits, the created
   user's type, the seeded mail templates, and refusal when the flag is off. Prior
   art: the contact, signup and waitlist tests. The authorization test already walks
   every module for guest-reachable endpoints.
3. **The browser.** The existing Playwright public project runs signed out against
   all six routes at nine widths. Use it for chrome regressions the HTML cannot show.

Assert on a distinctive phrase from the shipped constants, so a test fails when copy
is lost rather than when it is reworded elsewhere. Do not assert that a function was
called, or on an internal context key name.

Asset file sizes are deliberately not tested. Assert the absence of the framework
bundle at seam one instead.

## Testing in a browser

Rendering tests cannot see a broken layout, a header that overflows on a phone, or a
form that fails after the framework bundle was removed. Any issue that changes what a
page looks like or how it behaves must be checked in a real browser before you commit.
Use the `agent-browser` skill.

**Where to test, in order of preference:**

1. **The local stack, `http://localhost:8080`** — the port comes from `PORT` in
   `/home/ubuntu/benchpress_devops/.env`. It runs this branch against real, migrated
   schema. Sign in as `Administrator` with the `ADMIN_PASSWORD` value from that same
   file. **Use this for anything that writes**: submitting a form, signing in, signing
   out, creating a user, editing in Desk.
2. **The deployed branch instance, `$BP_TEST_URL`**, defaulting to
   `https://b3873df7.benchpress.cloud`. Disposable, runs the branch, signs in as
   `Administrator` with `$BP_TEST_PASSWORD`, defaulting to `admin`. Use it when you
   need to see a change against deployed data.
3. **Production, `https://benchpress.cloud`** — **read-only, always**. Look at it to
   compare a layout against what is live. Never submit a form there, never attempt to
   sign in, never create or edit a record.

**A non-administrator user:** passwords are stored hashed, so there is no way to read
an existing user's password. Create one with a password you choose instead, on the
local stack, from `/home/ubuntu/benchpress_devops`:

    docker compose exec -T backend bench --site frontend add-system-manager \
      tester@example.com --password <chosen>

For a website user rather than a desk user, create the user and set its type in
`bench --site frontend console`. Delete any user you created before you finish.

**What to check, every time a page changes:**

- The route renders with no console error.
- The header and the footer are identical to the other public routes.
- Nothing overflows horizontally at 320, 390 and 768 pixels wide, and at desktop
  width. 320 is the floor the existing browser test uses.
- Both light and dark mode.
- Any form on the page submits successfully and shows its result.

Never report a front-end change as finished on the strength of a passing test alone.

## The repository

- Bench commands run inside the parent compose stack, not a standalone bench. From
  `/home/ubuntu/benchpress_devops` use `docker compose exec -T backend bench ...`.
- Single module while working:
  `bench --site frontend run-tests --app benchpress --module <module.path>`.
  Whole app suite once before you commit: `... run-tests --app benchpress`.
- Frontend changes need `bench build --app benchpress`, then restart backend and
  frontend. Schema changes need `bench --site frontend migrate`.
- The local site has this branch migrated and seeded, so the schema is real and every
  seam above runs locally.
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
