# Spec templates and the code-snippet style contract

Read this when writing or revising a spec folder (Job 1).

## Contents

- [The folder](#the-folder)
- [README.md template](#readmemd-template)
- [phase-N.md template](#phase-nmd-template)
- [The `## Host steps` section](#the--host-steps-section) — every spec writes it, even an empty one
- [The code-snippet style contract](#the-code-snippet-style-contract) — read this one even if you skim the rest
- [Verification sections that are worth writing](#verification-sections-that-are-worth-writing)

## The folder

```
specs/not-completed/<feature-slug>/
├── README.md            # overview, verified facts, decisions, the phase table
├── phase-1-<slug>.md
├── phase-N-<slug>.md
└── ralph.sh             # optional; see references/ralph-loop.md
```

A freshly decomposed spec is born in `not-completed/`, because nothing is built
yet. Register it in `specs/STATUS.md` with the script — never by hand:

```bash
python3 .claude/skills/issue-to-phases/scripts/promote_spec.py <slug> --to not-completed \
  --note "freshly authored — no branch yet"
```

## README.md template

The first line is the status banner. `promote_spec.py` owns it after creation —
do not hand-edit it later, or the three trackers drift.

```markdown
> **Status:** ⬜ Not started — spec authored, no implementation yet

# Spec: <feature title>

<One or two paragraphs: the problem today, and the outcome we want. Lead with what
is broken or missing, not with the solution.>

Branch: `<branch>` · Base: `<integration or default branch>`

## What was verified before this spec was written

<A table of facts MEASURED against the real system, with the evidence. This is the
most valuable section in the file: it is what stops a phase being planned against
an assumption. If you did not check it, do not list it.>

| Fact | Evidence |
|---|---|
| <fact> | <the command run and what it returned> |

## Build strategy — tracer bullets

<Thinnest end-to-end slice first, prove it, then widen. Each phase independently
shippable and verified before the next.>

| Phase | Tracer-bullet capability | Proves |
|------|---------------------------|--------|
| **[1](phase-1-<slug>.md)** | <the thinnest end-to-end thing that works> | <what running it proves> |
| **[N](phase-N-<slug>.md)** | <one capability added on top> | <what it proves> |

## Confirmed decisions (apply to all phases)

- <decisions from the plan that constrain every phase, each with its reason>

## Shared architecture facts (verified — referenced by every phase)

- <concrete files, functions, fields each phase touches, so a phase doc can point
  here instead of repeating it>

## Host steps

<Three labelled lists — Precondition, Leftover, Never — all three written even
when one is empty. See [The `## Host steps` section](#the--host-steps-section).>

## Conventions (from CLAUDE.md — apply to all phases)

- <the repo conventions the implementer must follow>
- **No hardcoded config.** Values an admin could change (accounts, rates,
  thresholds, recipients, toggles) are read from an admin-editable Settings
  DocType / config record — never hardcoded. <Name the specific values this
  feature needs and where each is configured.>
```

If the feature has a trap — two things that look independent but collide — give
it its own `## The trap that decides the slicing` section. That section is
usually the reason the phases are ordered the way they are, and the next reader
needs it more than they need the phase table.

## phase-N.md template

```markdown
# Phase N — <short title>

> Read [README.md](README.md) first for shared architecture facts and conventions.

## Goal (the thinnest end-to-end slice)

<What works when this phase ships. For phase 1, name the layers the slice travels
through. Then, explicitly:>

**Not in scope for phase N:** <what a reader will expect and not find, and which
later phase owns it. Naming these is what stops a reviewer reading a deliberate
boundary as an oversight.>

## Changes by file

### <path>
- <the specific change, with a code snippet where the shape is not obvious>

## Verification

1. <concrete, runnable steps — commands, and what the output must say>

<Where a step depends on human-only host work, link it rather than restating it:>

> **Host step (precondition):** <what must be true>. See
> [Host steps](README.md#host-steps). The loop refuses to start otherwise.

<Where the phase touches a test module fenced for live-site coupling, say so:>

> **Fenced test module:** `benchpress.tests.<module>` cannot pass on a developer
> site. This phase gates on CI for it. See
> [Tests](ralph-loop.md#tests-scoped-fenced-exit-code) for the reason.

<Where the phase moves a function that a scheduler entry or an `enqueue` call
names by string, spell the closing order out — it is the step a phase drops:>

> **String-named move:** this phase ends with rewrite every string → `migrate` →
> restart the workers, in that order. Migrating after the restart leaves a
> `Scheduled Job Type` row pointing at nothing, and that failure is silent. See
> [Moving code that a string names](ralph-loop.md#moving-code-that-a-string-names).

**Rollback**, if step <n> fails: <the exact command. Restore first, diagnose after.>

## Done when

<One paragraph: the observable end state, including the graceful-degradation case
(still works / no-ops cleanly when unconfigured), and a sentence naming the known
gaps this phase deliberately leaves for later phases.>
```

## The `## Host steps` section

Every spec README carries this section, and it is the single source for the
human-only work around the loop. Phase specs link to it. They never restate a
step, because two copies drift and the loop reads neither.

Three kinds of step, and they are not interchangeable:

| | **Precondition** | **Leftover** | **Never** |
|---|---|---|---|
| When | before phase 1 is attempted | after the last phase lands | at any time |
| Who runs it | a human, before the loop starts | a human, after the loop finishes | nobody |
| What the loop does | `preflight` refuses to start | finishes, then reports it | `smoke_check` stops the loop |
| Example | `sudo scripts/enable-sysbox.sh` | `sudo scripts/tune-host.sh` | write to `/etc/sysctl.d` |

A Leftover and a Never are one action seen from two sides. "A human runs
`tune-host.sh`" and "the loop must never run `tune-host.sh`" are the same entry,
so every Leftover generates a Never. The Never list is never written on its own.

**Write all three lists, even when one is empty.** An omitted list reads as "not
considered". Write `— none` and the reason it is none.

```markdown
## Host steps

### Precondition — true before phase 1 is attempted

| Step | Verify (read-only, no root) | Why |
|---|---|---|
| <the command a human runs> | <a command that exits non-zero while the step is undone> | <what breaks without it> |

### Leftover — a human runs this after the last phase

| Step | Verify (read-only, no root) | Why |
|---|---|---|
| <the command a human runs> | <a command that exits non-zero while the step is undone> | <why no loop may run it> |

### Never — the loop is gated on these

| Never | Why |
|---|---|
| <the action> | <the damage, stated concretely> |
```

An empty list keeps its heading and gets a reason:

```markdown
### Leftover — a human runs this after the last phase

— none. Nothing in this spec writes outside the checkout, so it adds no host
debt and needs no new checker.
```

### The verify command is the load-bearing part

Prose cannot gate a loop. Every Precondition and every Leftover names a command
that is **read-only, needs no root, and exits non-zero while the step is undone**.
Writing that checker is part of the work, not a note for later.

**Scope the check to this spec, never to the whole host.** A whole-host readiness
gate refuses to start every later loop until unrelated debt is paid. On this repo
`entry.py --check-host` exits 1 today, because item 5's leftover has never been
run. A spec about Docker events that gated on it would never start.

### A leftover outlives the spec, so its record is tracked code

`specs/` is gitignored in full, and a completed spec is deleted once its code
lands. Nothing durable may be recorded only inside one.

A leftover is per-host state, not a repo TODO. A second host owes every leftover,
not the ones this host happened to skip. So the record is two tracked halves, and
the phase that creates the debt ships both:

| Half | Job |
|---|---|
| A read-only, non-root **checker** in tracked code | the host answers for itself, with no document to keep in step |
| A line in the **operations runbook** | a human provisioning a fresh host reads it |

Item 5 is the worked instance: `entry.py --check-host` and
`benchpress_devops/PRODUCTION.md` §5.18. A spec whose leftover no tracked command
can detect is not finished.

`specs/STATUS.md` keeps a `⚠ by hand:` prefix in its Notes cell while the spec
exists, so `grep '⚠ by hand:' specs/STATUS.md` lists what is outstanding on this
host. That is a working-tree convenience, not the record of truth.

### What the loop does with the section

`ralph.sh` builds two gates from these lists, and `prompt.md` restates the Never
list in its Safety section. See
[references/ralph-loop.md](ralph-loop.md#the-two-host-gates) for both gates.

A spec with no host steps at all deletes the section, the way a repo with no CI
deletes the `ci_status` gate.

## The code-snippet style contract

**This is the section that matters most, because of how the snippets get used.**

A phase spec's code snippets are not illustrations. The implementing agent pastes
them. Whatever density of comment you write into the spec is the density that
lands in the merged file — a thirteen-line docstring in a spec becomes a
thirteen-line docstring in production, and the reviewer sees a file where the
prose outweighs the code.

So the snippets in a spec obey the same limit the code does:

- **Default to no comment.** Code that reads clearly gets none.
- **A comment earns its place** only when something is surprising, constrained
  from elsewhere in the system, or would otherwise be "fixed" by the next reader.
  When it earns it: **one to three lines, never more.**
- **One-line docstrings for almost everything.** Reserve a multi-line docstring
  for a real contract — a non-obvious parameter, a sentinel return, a raised
  exception.
- **Never restate the code.** Never explain a well-named constant. Never narrate
  a sequence of obvious statements.
- **Match the file being edited.** If the surrounding code is bare, the new code
  is bare.

The design reasoning still has to live somewhere — it is the most valuable thing
in the spec. Put it in the **prose around the snippet**, where a reader who wants
the argument will find it and a reader of the source will not have to wade
through it.

**Before** — this shipped, and it is the failure mode:

```python
# One file, one router, one identity set — the only place in this app that names a
# certificate resolver. Fixed name so it is idempotently overwritten and can never
# collide with an instance file, which is always a 32-character hex id.
WILDCARD_ANCHOR_FILE = "wildcard-anchor.yml"

def _ensure_wildcard_anchor(base_domain: str | None) -> bool:
	"""Put the bench-zone wildcard in Traefik's certificate store, once.

	Returns True when the file was written. Rewrites only on a real change: Traefik
	reloads on mtime, and a deploy has no business making it reload to say nothing.

	Never deleted at teardown — it has to outlive every bench, because it is what keeps
	the certificate renewing.
	"""
```

**After** — same design, same information available, comment budget spent where
it buys something:

```python
WILDCARD_ANCHOR_FILE = "wildcard-anchor.yml"

def _ensure_wildcard_anchor(base_domain: str | None) -> bool:
	"""Write the wildcard anchor if it is missing or stale; True when written."""
	# Rewriting unchanged content would touch mtime, and Traefik reloads on mtime.
```

The "never deleted at teardown" fact did not disappear — it belongs in the
teardown function, next to the code that would otherwise delete it, and in the
spec's prose. Facts go where someone would act on them, not where they were
discovered.

Write the surrounding prose with the `technical-writing` skill and the code with
`code-style`. This section is the concrete limit for `code-style`'s "do not
narrate obvious code".

## Verification sections that are worth writing

A phase whose Verification is "run the tests" is not sliced yet — it has no
observable end state, which means it is a horizontal layer rather than a tracer
bullet.

Good verification steps share three properties:

1. **They observe the real thing through the real path.** An exit code, a 200,
   or a log line saying "done" is not evidence. Name the discriminator: the
   header, the field, the certificate subject, the row count.
2. **They can fail.** Write a step whose expected output you could not produce
   today, before the phase is built.
3. **They say what to do when the step fails**, when the step touches something
   live. Restore first, diagnose after — a rolled-back attempt that leaves the
   system working beats a forward-debugged outage.

**Tests are not the phase's verification, and they are never the loop's gate.** A
phase runs the scoped test modules it touches — see
[Tests](ralph-loop.md#tests-scoped-fenced-exit-code) — but `smoke_check` invokes
none of them. The agent edits the suite, so the suite cannot be the independent
word on the agent's work. Verification observes the running system, and CI runs
the suite against a site the agent never touched.

**A phase that moves code verifies the strings, not just the imports.** Frappe
resolves scheduled and enqueued jobs from dotted strings at run time, so a green
import proves nothing about them. The three gates that do — a `git grep` for the
old path, two static tests that resolve every scheduler and `enqueue` target, and
one runtime pass over `Scheduled Job Type.method` — are in
[Moving code that a string names](ralph-loop.md#moving-code-that-a-string-names).

Include a negative control wherever one is cheap: a name that should *not*
resolve, a user who should *not* have access, a file that should *not* be
deleted. A gate that only ever sees passing input is not a gate.
