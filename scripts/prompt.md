Implement the work described by the user in the spec or tickets.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

Commit your work to the current branch.

## The tickets

The tickets are GitHub issues: the sub-issues of parent spec **#288**, numbered #289 to #300. The
current state of every one of them is at the top of this prompt, with its state and how many of its
blockers are still open.

Pick the FIRST issue, in ascending number order, that is `[open]` **and** has `blocked_by=0`. That
one issue is the whole of this iteration.

Only one issue. Do not start the next one — the next loop iteration picks it up with a fresh
context window.

Read it with `gh issue view <n>`. Read the parent with `gh issue view 288` when you need the wider
context.

Your context is new every iteration. Nothing from a previous iteration is in it. Before you change
anything, read the issue, read the code it names, and read `git log` on this branch. Do not assume
a thing is unimplemented because you cannot remember implementing it — search first.

An issue's blockers are recorded as GitHub dependencies, and `blocked_by=0` means every one of them
is closed. Trust that number over your own reading of the issue body.

## The pre-agreed seams

`/tdd` needs seams. These three were agreed on the parent spec. Do not introduce a fourth. A good
test asserts what a visitor or an operator can observe, never how it is produced.

1. **Rendering a route as a guest.** Render a public route through the framework's website-serving
   helper and assert against the returned HTML. The highest seam available, and it carries most of
   this series: shipped copy with no rows behind it, identical chrome across routes, the absence of
   the framework bundle, the link-preview tags, and every route's behaviour with the public-site
   flag off. Prior art: `benchpress/tests/test_landing.py` and
   `benchpress/benchpress/tests/test_site_content.py`.
2. **Calling the whitelisted public functions directly.** Carries endpoint behaviour: storage,
   acknowledgement, topic routing, per-endpoint rate limits, the created user's type, the seeded
   mail templates, and refusal when the flag is off. Prior art: `benchpress/tests/test_contact.py`,
   `test_signup.py`, `test_waitlist.py`. `test_api_authorization.py` already walks every module for
   guest-reachable endpoints.
3. **The browser.** The Playwright `public` project in `e2e/` runs signed out against all six
   routes at nine widths. Use it for chrome regressions the HTML cannot show.

Assert on a distinctive phrase from the shipped constants, so a test fails when copy is lost rather
than when it is reworded elsewhere. Never assert that a function was called, or on an internal
context key name. Asset file sizes are deliberately not tested; assert the absence of the framework
bundle at seam one instead.

## The repository

- Bench commands run inside the parent compose stack, not a standalone bench. From
  `/home/ubuntu/benchpress_devops` use `docker compose exec -T backend bench ...`.
- One module while working:
  `bench --site frontend run-tests --app benchpress --module <module.path>`.
  Whole app suite once before you commit: `... run-tests --app benchpress`.
- Frontend changes need `bench build --app benchpress`, then restart backend and frontend.
  Schema changes need `bench --site frontend migrate`.
- The local site has this branch migrated and seeded, so the schema is real and every seam runs
  locally.
- Query with `frappe.qb`, never raw SQL. Every whitelisted method checks permissions itself.
- Behaviour lives in doctype controllers and `hooks.py` as often as in the obvious module. Read
  `hooks.py` before assuming a save does the plain thing.

## Testing in a browser

A rendering test cannot see a broken layout, a header that overflows on a phone, or a form that
stopped submitting. Any issue that changes what a page looks like or how it behaves must be checked
in a real browser before you commit. Use the `agent-browser` skill.

1. **The local stack, `http://localhost:8080`** — the port is `PORT` in
   `/home/ubuntu/benchpress_devops/.env`. It runs this branch against real, migrated schema. Sign
   in as `Administrator` with `ADMIN_PASSWORD` from that same file. **Use this for anything that
   writes**: submitting a form, signing in or out, creating a user, editing in Desk.
2. **The deployed branch instance, `$BP_TEST_URL`**, defaulting to
   `https://b3873df7.benchpress.cloud`, signing in as `Administrator` with `$BP_TEST_PASSWORD`,
   defaulting to `admin`. Use it to see a change against deployed data.
3. **Production, `https://benchpress.cloud`** — **read-only, always**. Never submit a form there,
   never sign in, never create or edit a record.

Check every page you changed: it renders with no console error; the header and footer match the
other public routes; nothing overflows horizontally at 320, 390 and 768 pixels and at desktop
width; both light and dark mode; every form on it submits and shows its result.

## Style

- Match the Frappe framework's own sparse comment style. Few comments, short or no docstrings. Do
  not write a block comment above a function or a rule explaining why the decision was made — that
  belongs in the commit message.
- A `PostToolUse` hook caps docstrings at two lines. The hook is a ceiling, not a target.
- Every colour comes from `benchpress/public/css/bp-brand.bundle.css`. Never a raw hex value.
- Load the `code-style` skill for any code change, and `frappe-app-dev` for any Frappe work.

## Before you commit

1. `uvx pre-commit@4.3.0 run --all-files` must pass. Never run `yarn lint`.
2. The full app test suite must pass.
3. Use `/code-review` on your own work and act on what it finds.
4. Write the message with the `technical-writing` skill: plain and short, Conventional Commits
   header (`type(scope): summary`).
5. Commit to the branch you are already on. Do not create a branch, do not push, do not open or
   merge a pull request.

## Finishing the ticket

When, and only when, every acceptance checkbox in that issue is genuinely satisfied by committed
work:

1. Tick each checkbox in the issue body with `gh issue edit <n> --body-file <file>`.
2. Close it: `gh issue close <n> --comment "<one line naming the commit sha>"`.

The issue's state is the loop's only progress signal. Never close an issue to end the session. If
you cannot finish it, leave it open and `gh issue comment <n>` with what blocked you, so the next
iteration starts from what you learned.

Do not close, edit or comment on any other issue, and never touch the parent #288.

Leave the working tree clean. A half-finished edit left behind poisons the next iteration, which
starts from this same checkout.

## Phases

- #289 close the three guest endpoints to GET
- #290 emit one correct set of link-preview tags
- #291 give each public form its own rate-limit counter
- #292 gate the public site behind a site-config flag
- #293 serve Frappe's login when the public site is off
- #294 render every page from the shipped constants
- #295 delete the thirty page-content doctypes
- #296 use one header and footer on every public route
- #297 replace the placeholder testimonials with the forum thread
- #298 drop Frappe's website assets from the marketing pages
- #299 serve our stylesheets and scripts from the bundler
- #300 cut the comments and retire the superseded design docs

#293 is the one to stop on rather than solve cleverly. The branded login shadows Frappe's by
filename, and filename shadowing has no off position. If no clean mechanism presents itself,
comment what you found and leave it open. A wrong answer there breaks the login page on every
self-hosted install.

## Ending the loop

When every issue from #289 to #300 is closed, and only then, end your final message with exactly:

<promise>COMPLETE</promise>

Never write that line while any ticket is unfinished — the loop stops on it. Finishing one ticket
is not the end of the loop, it is the end of your session.
