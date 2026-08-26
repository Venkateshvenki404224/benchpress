---
name: issue-to-phases
description: >-
  Decompose a planning document (plan.md, a spec, or a GitHub issue) into incremental,
  independently-shippable "tracer bullet" phases, write them as phase specs under specs/, and
  optionally generate a Ralph loop (ralph.sh + prompt.md) that implements them unattended. Use
  this whenever the user hands you a plan and wants it broken into phases, mentions "tracer
  bullets", "phase 0/1/2", "build this in phases", "thin end-to-end slice first", "ralph loop",
  or wants phased specs in the specs/ folder — even if they never say the word "phase". Also use
  it when the user asks to "implement / work on phase N" of an existing spec folder, so the
  branch, the PR and the spec's status all move the way every earlier phase did.
---

# issue-to-phases

Three jobs. Work out which one the request is, then do that one.

| Job | Trigger | Output |
|---|---|---|
| **1. Decompose** | the user hands you a plan | a spec folder under `specs/` |
| **2. Implement a phase** | "work on phase N" | a commit on the one branch, the one PR retitled, the spec's status moved |
| **3. Build a Ralph loop** | "make a ralph script", or the work is long and unattended | `ralph.sh` + `prompt.md` in the spec folder |

Job 1 usually leads into Job 3. Do not start Job 2 straight after Job 1 unless
asked — decomposition is its own step, and the user may want to read it first.

## The idea: tracer bullets

> Tracer bullets come from *The Pragmatic Programmer*. When building systems you
> want feedback as quickly as possible. A tracer bullet is a small slice of
> functionality that goes through **all layers** of the system, letting you test
> and validate the approach early — before investing significant time.

Everything below is mechanics. The point is real feedback: each phase is a slice
you can run and verify, not a horizontal layer (all the backend, then all the
frontend) that proves nothing until the end.

## Job 1 — Decompose a plan into phases

**Read `references/spec-templates.md` before writing anything.** It carries the
README and phase templates, and the code-snippet style contract that keeps
generated implementations from drowning in comments.

1. **Read the plan in full**, then list every layer the finished feature touches
   — infra, a backend manager module, the deploy pipeline, a DocType, the
   whitelisted API, the SPA. You are looking for the seam that runs top to bottom
   through all of them.

2. **Find phase 1 — the thinnest end-to-end slice.** Everything optional
   stripped: no auth, no toggles, no polish. Its only job is to prove the
   architecture and produce feedback. If phase 1 touches one layer it is not a
   tracer bullet; widen it until a single user-visible action travels the whole
   pipe.

   Two halves that are individually unverifiable are **one** phase, not two. If
   shipping half of it breaks production or changes nothing observable, it was
   never a phase boundary.

3. **Slice the rest.** Each later phase adds one coherent capability, is
   independently shippable, and is independently verifiable. A phase is the wrong
   size when you cannot write a concrete "Done when". Order so nothing depends on
   a later phase. Most plans land at 3–5 phases; let the plan decide.

4. **Write the folder**, using the templates:

   ```
   specs/not-completed/<feature-slug>/
   ├── README.md
   ├── phase-1-<slug>.md … phase-N-<slug>.md
   └── ralph.sh + prompt.md   (Job 3, optional)
   ```

5. **Create the tree and register it — with the script, never by hand:**

   ```bash
   python3 .claude/skills/issue-to-phases/scripts/promote_spec.py --init
   python3 .claude/skills/issue-to-phases/scripts/promote_spec.py <slug> \
     --to not-completed --note "freshly authored — no branch yet"
   ```

   `--init` creates `specs/`, all four buckets and `STATUS.md` if any are
   missing, so a repo that has never used `specs/` needs no setup. Run it first
   whenever you are not certain the tree exists.

6. **Tell the user the folder path, the phase list, and the branch name**, then
   stop unless they ask you to build or implement.

## Job 2 — Implement a phase

One branch for the whole feature; every phase commits to it; **one** PR that
walks forward phase by phase. The reviewer watches the feature grow as a single
story, and GitHub allows only one open PR per head→base pair anyway.

Branch name comes from the spec README. Base is the integration branch it names,
else the repo default.

**Phase 1**
1. `promote_spec.py <slug> --to in-progress --detail "P1 started"`
2. `git switch -c <branch> <base>`
3. Implement from the phase spec. Follow the repo conventions, run the lint hook.
4. Commit, `git push -u origin <branch>`
5. `gh pr create --base <base> --head <branch> --title "Implemented phase one" --body "<what it does + how to verify>"`
6. `gh pr checks <branch> --watch` — fix whatever is red before calling the phase done.

**Phase N ≥ 2**
1. `git switch <branch>` — do **not** branch off it.
2. Implement, lint, commit, push.
3. `gh pr checks <branch> --watch`, and fix what it reports.
4. `gh pr edit <branch> --title "Implemented phase <ordinal>"` and
   `gh pr comment <branch> --body "Phase <ordinal>: <what it added + how to verify>"`
5. `promote_spec.py <slug> --to in-progress --detail "P<n> done"`
6. **If it was the final phase, CI is green and it merged:**
   `promote_spec.py <slug> --to completed --detail "all phases in <base> (PR #<n>)"`

**CI is a gate, not a report.** A phase whose tests pass locally and fail on the
runner is unfinished, and a check that was already red before the branch is still
the branch's problem — nothing merges past it. Fix it in its own commit.

Ordinals are spelled out: one, two, three, four, five.

## Job 3 — Build a Ralph loop

**Read `references/ralph-loop.md` before writing the script.** Copy both
templates into the spec folder and fill them in:

```bash
cp .claude/skills/issue-to-phases/assets/ralph.sh.template   specs/<bucket>/<slug>/ralph.sh
cp .claude/skills/issue-to-phases/assets/prompt.md.template  specs/<bucket>/<slug>/prompt.md
chmod +x specs/<bucket>/<slug>/ralph.sh
```

**A phase that touches the UI needs a browser, so make sure there is one.** Before
writing the loop, check that `agent-browser` is installed and can launch:

```bash
agent-browser --version || npm i -g agent-browser && agent-browser install
agent-browser skills get core     # the workflow guide; the CLI serves its own docs
```

If it cannot launch, fix that before the loop runs, not during it — an agent
discovering a missing browser mid-phase burns an iteration on setup. On a
container host Chrome usually needs `--args "--no-sandbox"`; record the working
invocation in the spec README so every iteration inherits it instead of
rediscovering it.

A Ralph loop runs one **fresh** headless `claude -p` session per iteration, with
the file system as its only memory, and runs phases strictly in order. The prompt
lives in `prompt.md` so it can be tuned between runs without touching bash.

The thing that makes it trustworthy: **the agent is not the only judge of its own
work.** After the agent writes a `.done` marker the loop runs its own
`smoke_check` against the real system, and deletes the marker if reality
disagrees. Write gates that would fail today, before the feature exists — a gate
that passes on an unmodified tree is testing nothing. `references/ralph-loop.md`
covers gate design, preflight/rollback, and the sandbox check to run before
handing the loop over.

Not every spec needs one. A loop pays for itself when the work is long, has
verifiable per-phase end states, and touches something you would rather not
babysit.

## Spec status: one script, three trackers

A spec's status lives in three places that must agree — the **bucket folder**,
the README **banner**, and its **row plus counts** in `STATUS.md`. By hand that
is three edits and two counters, and it is reliably the step that gets skipped
while you are concentrating on code. A shipped feature filed under "not started"
is how a tracker stops being worth reading.

So it is a script, not a ritual:

```bash
P=.claude/skills/issue-to-phases/scripts/promote_spec.py
python3 $P --init                                          # create the tree
python3 $P <slug> --to in-progress --detail "P1 started"
python3 $P <slug> --to completed --detail "all phases in main (PR #12)" --note "<index line>"
python3 $P <slug> --check                                  # verify; changes nothing
```

It is idempotent, recomputes every count, refuses a backwards move without
`--force`, and `--check` exits non-zero on drift so a loop can gate on it — which
the ralph template does.

Buckets walk forward only: `not-completed/` → `in-progress/` → `completed/`.
`superseded/` is a manual sideways move for an abandoned spec. Keep a spec in
`in-progress/` until the final phase actually merges; half-shipped is not
completed.

## Guardrails

- **Never hardcode configurable values.** Anything a business admin could
  reasonably change — accounts, cost centers, rates, thresholds, default parties,
  recipients, toggles — belongs in an admin-editable config surface (a Settings
  DocType, a Custom Field, a config record read at runtime), never baked into
  source. When a phase needs such a value, adding the config surface is part of
  that phase. Flag every one of them while decomposing and give it a home in the
  spec.
- **A UI change is not done until it has been seen in a browser.** Tests passing
  and a green smoke check say the code is right; they say nothing about whether a
  user can see it. Any phase touching a page, component or form ends with
  `agent-browser` driving the real deployment and a screenshot in the notes. Three
  things make a correct, merged UI change invisible, and none of them fails a
  test: **the built assets are older than the source**, **a feature flag hides
  it**, and **no row exercises it** (the feature reads a column every existing row
  has as `NULL`). Check those three before concluding the code is wrong.
- **A move that changes a dotted path ends with `migrate`, then the restart.**
  Frappe resolves scheduled and enqueued jobs from strings at run time, so moving
  a function they name breaks them while every import still works. Rewrite every
  string in the same commit, run
  `docker compose exec backend bench --site frontend migrate`, and restart the
  workers **after** — the other order leaves a `Scheduled Job Type` row pointing
  at nothing, and that fails in complete silence. Job ids never change during a
  move, and a re-export shim is not a fallback: see
  [Moving code that a string names](references/ralph-loop.md#moving-code-that-a-string-names).
- One subfolder per feature, always inside a status bucket — never loose in
  `specs/` or in a bucket root.
- One branch and one PR per feature. Never a second PR for a later phase.
- **A spec reaches `completed/` only with a green CI run behind it.** The bucket
  is a claim about shippability; a red PR filed under "completed" is the same lie
  as a shipped feature filed under "not started".
- Phase numbers and PR ordinals stay in lockstep: phase 1 is "Implemented phase
  one".
- A phase with no concrete "Done when" is too big or too vague. Reslice it.
- Keep the bucket, the banner and `STATUS.md` in agreement. When they disagree,
  the bucket the folder physically sits in wins.

## Files in this skill

| Path | Read it when |
|---|---|
| `references/spec-templates.md` | writing or revising a spec folder (Job 1) |
| `references/ralph-loop.md` | writing a `ralph.sh` (Job 3) |
| `assets/ralph.sh.template` | the loop skeleton to copy |
| `assets/prompt.md.template` | the phase prompt to copy |
| `scripts/promote_spec.py` | any time spec status or the tree changes |
