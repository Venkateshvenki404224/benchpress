# Spec templates and the code-snippet style contract

Read this when writing or revising a spec folder (Job 1).

## Contents

- [The folder](#the-folder)
- [README.md template](#readmemd-template)
- [phase-N.md template](#phase-nmd-template)
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

**Rollback**, if step <n> fails: <the exact command. Restore first, diagnose after.>

## Done when

<One paragraph: the observable end state, including the graceful-degradation case
(still works / no-ops cleanly when unconfigured), and a sentence naming the known
gaps this phase deliberately leaves for later phases.>
```

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

Include a negative control wherever one is cheap: a name that should *not*
resolve, a user who should *not* have access, a file that should *not* be
deleted. A gate that only ever sees passing input is not a gate.
