---
name: issue-to-phases
description: >-
  Decompose a single planning document (plan.md, a spec, or a GitHub issue) into incremental,
  independently-shippable "tracer bullet" phases, write them as phase specs in a dedicated
  subfolder under specs/, then drive a one-branch / per-phase-PR implementation workflow. Use this
  whenever the user hands you a plan and wants it broken into phases, mentions "tracer bullets",
  "phase 0/1/2", "build this in phases", "thin end-to-end slice first", or wants phased specs in the
  specs/ folder — even if they don't say the word "phase". Also use it when the user asks an agent to
  "implement / work on phase N" of an existing spec folder, so the branch and PR are handled the way
  every other phase did it.
---

# issue-to-phases — plan.md → tracer-bullet phases → one-branch, per-phase PRs

This skill does two jobs. Figure out which one the request is and do that one:

- **Decompose** — the user has a `plan.md` (or a spec / GitHub issue) and wants it sliced into phases.
  Produce a phase-spec folder under `specs/`. This is the default when a plan is provided.
- **Implement a phase** — the user (or an agent) is starting "phase N" of an already-decomposed
  feature. Reuse the one feature branch and the one PR, the same way the earlier phases did.

Both jobs are built around one idea, so internalize it first.

## The idea: tracer bullets

> Tracer bullets for new features. Tracer bullets comes from the Pragmatic Programmer. When building
> systems, you want to write code that gets you feedback as quickly as possible. Tracer bullets are
> small slices of functionality that go through all layers of the system, allowing you to test and
> validate your approach early. This helps in identifying potential issues and ensures that the
> overall architecture is sound before investing significant time in development.
> TL;DR - build a tiny, end-to-end slice of the feature first, then expand it out.

Everything below is just the mechanics of applying that idea to a plan and to the git workflow that
ships it. The whole point is fast, real feedback: each phase is a slice you can actually run and
verify, not a horizontal layer (all the backend, then all the frontend) that proves nothing until
the end.

---

## Job 1 — Decompose a plan into phases

### Step 1: Read the plan and map the layers

Read the plan.md in full. Then list every layer the finished feature has to touch in this codebase —
for example: infra / docker-compose, a backend `*_manager.py`, the deploy pipeline, a DocType, the
`api.py` whitelisted endpoint, the SPA in `frontend/src/`. You are looking for the seam that runs
top-to-bottom through all of them.

### Step 2: Find phase 1 — the thinnest end-to-end slice

Phase 1 is the tracer bullet: the smallest thing that exercises **every** layer end-to-end with
everything optional stripped away (no auth, no TLS, no toggles, no error handling beyond not
crashing, no polish). Its only job is to prove the architecture is sound and give real feedback. If
phase 1 touches only one layer, it isn't a tracer bullet — widen it until a single user-visible
action travels the whole pipe.

### Step 3: Slice the rest

Each later phase adds **one** coherent capability on top of the working slice, and each one must be
independently shippable and independently verifiable. A phase is the wrong size if you can't write a
concrete "Done when" for it, or if it can't be demoed without the next phase. Order them so nothing
depends on a phase that comes later. Most plans land at 3–5 phases; let the plan decide, don't pad.

### Step 4: Write the spec folder

`specs/` is organized into **status buckets** — `not-completed/`, `in-progress/`, `completed/`,
`superseded/` — indexed by `specs/STATUS.md`. A feature moves through the buckets as it is built
(Job 2 handles the moves). A **freshly decomposed spec has no implementation yet, so it is born in
`not-completed/`.** Always create a dedicated subfolder for the feature and put every file inside it:

```
specs/not-completed/<feature-slug>/
├── README.md            # overview + the phase table — read this first
├── phase-1-<slug>.md
├── phase-2-<slug>.md
└── phase-N-<slug>.md
```

Then register it in the index: add a row for the feature under the **Not started** table in
`specs/STATUS.md` (`| <feature-slug> | freshly authored — no branch yet |`) and bump that section's
count + the totals line. (`specs/` is gitignored, so these are plain filesystem writes — nothing to
commit.)

`<feature-slug>` is a short kebab-case name for the feature (e.g. `public-browser-access`). Phases
are numbered from **1** (phase 1 = the tracer bullet) so the numbers line up with the PR titles in
Job 2. Use the existing files in `specs/` as the format reference — match their structure, depth, and
tone rather than inventing a new layout. The two templates below capture that structure.

**`README.md` template:** (the first line is the status banner — it moves in lockstep with the
folder's bucket: `⬜ Not started` → `🟡 In progress` → `✅ Completed`)

```markdown
> **Status:** ⬜ Not started — spec authored, no implementation yet

# Spec: <feature title>

<One-paragraph what + why: the problem today and the outcome we want.>
Branch: `feature/<feature-slug>` · Base: `<integration or default branch>`

## Build strategy — tracer bullets

<Restate the tracer-bullet idea in one or two sentences for this feature: thinnest end-to-end slice
first, prove it, then widen. Each phase is independently shippable and verified before the next.>

| Phase | Tracer-bullet capability | Proves |
|------|---------------------------|--------|
| **[1](phase-1-<slug>.md)** | <the thinnest end-to-end thing that works> | <what running it proves> |
| **[2](phase-2-<slug>.md)** | <one capability added on top> | <what it proves> |
| **[N](phase-N-<slug>.md)** | ... | ... |

## Confirmed decisions (apply to all phases)

- <decisions taken from the plan that constrain every phase>

## Shared architecture facts (verified — referenced by every phase)

- <the concrete files / functions / fields each phase will touch, so a phase doc can point here
  instead of repeating it>

## Conventions (from CLAUDE.md — apply to all phases)

- <the repo conventions the implementer must follow>
- **No hardcoded config.** Values an admin could change (accounts, cost centers, rates, thresholds,
  default parties, recipients, toggles) are read from an admin-editable Settings DocType / Custom
  Field / config record — never hardcoded in frontend or backend source. <List the specific values
  this feature needs and where each is configured.>
```

**`phase-N-<slug>.md` template:**

```markdown
# Phase N — <short title>

> Read [README.md](README.md) first for shared architecture facts and conventions.

## Goal (the thinnest end-to-end slice)

<What works when this phase ships, and explicitly what is NOT in scope yet (deferred to later
phases). For phase 1, name the layers the single slice travels through.>

## Changes by file

### <Layer, e.g. Infra / Backend / API / DocType / Frontend>
- **New/Modify `<path>`** — <the specific change>.

## Verification

1. <concrete, runnable steps to prove the slice works — commands, what to look for>

## Done when

<One paragraph: the observable end state. Include the graceful-degradation case where relevant
(e.g. still works / no-ops cleanly when the feature is unconfigured).>
```

After writing the files, tell the user the folder path and the phase list, and confirm the branch
name you'll use in Job 2. Don't start implementing unless they ask — decomposition is its own step.

---

## Job 2 — Implement a phase (one branch, one rolling PR)

The whole feature lives on **one branch**; every phase commits to that same branch, and there is
**one PR** that walks forward phase by phase. This is deliberate: the reviewer watches the feature
grow as a single coherent story instead of juggling a PR per phase. (GitHub also only allows one open
PR per head→base pair, so "raise a PR" on phases after the first means *update the existing one*.)

Derive the branch name from the spec README — `feature/<feature-slug>`. Base branch = the integration
branch named in the plan/README, else the repo's default branch (`develop` here).

### Phase 1

1. **Promote the spec to `in-progress/`** (starting phase 1 = work has begun):
   `mv specs/not-completed/<feature-slug> specs/in-progress/<feature-slug>`. Then flip its README
   banner to `> **Status:** 🟡 In progress — P1 started` and move its row from the **Not started**
   table to the **In progress** table in `specs/STATUS.md` (adjust both counts). Plain `mv` — `specs/`
   is gitignored.
2. Branch off the base: `git switch -c feature/<feature-slug> <base>`.
3. Implement phase 1 from `specs/in-progress/<feature-slug>/phase-1-<slug>.md`. Follow the repo
   conventions and run `pre-commit run --all-files` before committing.
4. Commit and push: `git push -u origin feature/<feature-slug>`.
5. Open the PR:
   ```bash
   gh pr create --base <base> --head feature/<feature-slug> \
     --title "Implemented phase one" \
     --body "<what phase one does + how to verify it, drawn from the phase spec>"
   ```

### Phase N (N ≥ 2)

1. Reuse the branch: `git switch feature/<feature-slug>` (don't branch off it). The spec folder is in
   `specs/in-progress/<feature-slug>/` for the whole implementation run.
2. Implement phase N from its spec; `pre-commit run --all-files`; commit; `git push`.
3. The PR already exists for this branch, so update it instead of creating a new one:
   ```bash
   gh pr edit feature/<feature-slug> --title "Implemented phase <ordinal>"
   gh pr comment feature/<feature-slug> \
     --body "Phase <ordinal>: <what this phase added + how to verify it>"
   ```
4. **If this is the final phase** (the last row of the phase table just shipped and merged): promote
   the spec to `completed/`. `mv specs/in-progress/<feature-slug> specs/completed/<feature-slug>`,
   flip its README banner to `> **Status:** ✅ Completed — all phases in <base> (PR #<n>)`, and move
   its row to the **Completed** table in `specs/STATUS.md` (adjust both counts). Keep the folder in
   `in-progress/` until the final phase is actually merged — a half-shipped feature is not completed.

Each phase therefore (a) commits to the same branch, (b) sets the PR title to **"Implemented phase
&lt;ordinal&gt;"**, and (c) leaves a comment describing what that phase did. Title ordinals are
spelled-out words: phase 1 → "one", 2 → "two", 3 → "three", 4 → "four", 5 → "five" (continue the
pattern beyond that).

**Example — titles across a 3-phase feature:**

Input: implementing phase 2 of `public-browser-access`
Output:
- branch stays `feature/public-browser-access`
- PR title becomes `Implemented phase two`
- new PR comment: `Phase two: HTTPS via Let's Encrypt on the same routed host. Verify: curl -I https://<bench>.<domain>/ returns 200 with a valid cert.`

## Guardrails

- **Never hardcode configurable values — make them admin-configurable.** Anything a business admin
  could reasonably change over time — GL / expense / income accounts, cost centers, tax or fee rates,
  thresholds, default parties, email recipients, feature toggles — must live in an admin-editable
  config surface (a single-DocType Settings record, a Custom Field, or a config record read at
  runtime), **never baked into frontend or backend source**. When a phase needs such a value, adding
  the config surface is part of that phase's scope, and the code reads from it. This is the lesson
  from the Partner fee-invoices feature, where the Expense account was hardcoded in the codebase — it
  should have been an admin setting, because accounts change. When decomposing, flag every value like
  this and give it a home in the spec.
- One subfolder per feature, always filed inside a **status bucket** — never write phase files into
  the flat `specs/` root or loose in a bucket root. New specs are born in `not-completed/`.
- The folder lives in exactly one bucket at a time and walks forward only:
  `not-completed/` → `in-progress/` (phase 1 starts) → `completed/` (final phase merged). Never skip
  `in-progress/`. `superseded/` is a manual sideways move for abandoned specs.
- Keep the three trackers in lockstep on every move: the folder's **bucket**, its README **status
  banner** (first line), and its row + counts in **`specs/STATUS.md`**. If they disagree, the bucket
  the folder physically sits in wins.
- One branch and one PR per feature; never open a second PR for a later phase of the same feature.
- Keep phase numbers and PR ordinals in lockstep — phase 1 is "Implemented phase one".
- A phase that can't state a concrete "Done when" / "Verification" is too big or too vague — reslice it.
