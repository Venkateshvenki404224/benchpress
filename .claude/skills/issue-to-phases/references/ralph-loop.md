# Authoring the Ralph loop

Read this when writing a spec's `ralph.sh` (Job 3). Start from
`assets/ralph.sh.template` and replace every `{{PLACEHOLDER}}` and every `ADAPT:`
block.

## Contents

- [What a Ralph loop is](#what-a-ralph-loop-is)
- [The one idea that makes it work](#the-one-idea-that-makes-it-work)
- [Designing smoke_check](#designing-smoke_check)
- [Tests: scoped, fenced, exit code](#tests-scoped-fenced-exit-code)
- [Moving code that a string names](#moving-code-that-a-string-names)
- [Proving the UI](#proving-the-ui)
- [Why a loop stalls](#why-a-loop-stalls)
- [Preflight and rollback](#preflight-and-rollback)
- [The two host gates](#the-two-host-gates)
- [The phase prompt](#the-phase-prompt)
- [Filling in the template](#filling-in-the-template)
- [Before you hand it over](#before-you-hand-it-over)

## What a Ralph loop is

A bash loop that runs one **fresh** headless `claude -p` session per iteration.
Nothing carries between iterations except the file system: the spec, a notes file
per phase, and marker files. Phases run strictly in order; phase N+1 starts only
once phase N is genuinely finished.

Fresh sessions are the point. An agent that has been arguing with a problem for
two hours has a context full of failed approaches; an agent that starts from the
spec plus a notes file has the conclusions without the wreckage.

Not every spec wants one. A loop pays for itself when the work is long, has
verifiable per-phase end states, and touches something you would rather not
babysit. A two-file refactor does not need one.

## The one idea that makes it work

**The agent does not get to be the only judge of its own work.**

Every phase ends with the agent writing a `.done` marker. The loop then runs
`smoke_check` — its own verification, in bash, against the real system — and if
that disagrees it **deletes the marker** and the phase continues. The agent
cannot declare success past a broken system, and phase N+1 can never start on a
bad base.

This is worth the effort because "reported success while doing nothing" is the
single most common failure in this kind of automation. An exit code is not
evidence.

## Designing smoke_check

The gates are the hard part and the part worth thinking about. Rules:

**Write gates that fail today.** Before the feature exists, `smoke_check <phase>`
should fail. If it passes on an unmodified tree it is testing nothing. Run it and
confirm, then keep the output — it is proof the gate has teeth.

**The baseline must pass.** `smoke_check 0` runs before the first iteration. It
must pass on the current system, or the loop refuses to start — deliberately, so
the loop can tell its own damage apart from what it inherited. If the baseline
fails, either the system is genuinely broken or the gate is wrong; both need a
human.

**Gate the incumbent, not just the new thing.** Name whatever is serving users
today and check it every single time, at every phase including phase 0. Most
damage from this kind of work is collateral.

**Gate on the property, not the symptom.** If the feature exists to stop
certificates being issued, gate on "no new certificate appeared" — not on the
site loading. A system can look perfect while quietly doing the thing you built
the feature to prevent.

**Find a real discriminator.** Two different services can both return 200 with a
page titled "Login". Status codes and titles usually prove nothing. Find the
field that actually differs — a header, a site name in a payload, a certificate
subject — and verify it by hand before trusting it.

> A worked example: an earlier loop discriminated the control plane from a tenant
> site by reading `"sitename"` out of the boot payload. A later release replaced
> that page with an SPA that never emits it, so the check returned empty for a
> perfectly healthy system and the loop aborted at baseline every run. The `server`
> header — nginx versus Werkzeug — was the durable discriminator. Test every helper
> against the live system before shipping the loop.

**Every helper returns 0 even when it finds nothing.** Under `set -euo pipefail`
an unguarded `grep` miss aborts the whole loop instead of reporting the failure
the gate exists to catch. End helpers with `|| true` and an explicit `return 0`.

**Redirect stdin on every `docker compose exec`, or the loop hangs forever.**
GNU `timeout` calls `setpgid()` to put its child in its own process group so it
can kill the group. That group is *background* relative to the terminal, so the
Compose CLI touching the controlling terminal takes SIGTTIN and stops — and
because `timeout` is stopped alongside it, the timeout never fires. A
one-second query then sits frozen for hours, reading to the operator as a hung
phase. `-T` is not enough: it disables TTY allocation for the exec'd process,
not the CLI's own terminal access.

```bash
( cd "$DEVOPS_DIR" && </dev/null timeout 120 docker compose exec -T db sh -c '...' )
```

Leave off only where stdin is already a pipe (`printf ... | timeout ...`), where
the redirect would override the pipe and break the query. The signature when it
happens: `ps -o pid,pgid,tpgid,stat` shows `T`/`Tl` with `PGID != TPGID`.
SIGCONT does not help — the kernel re-stops it.

**smoke_check invokes no tests.** The gate is worth having because the agent is
not the only judge of its own work, and the suite is a thing the agent edits. A
phase that adds a passing test to a suite it also changed proves nothing. Tests
belong in `{{TEST_CMD}}`, where the agent runs them. The independent run comes
from `ci_green`, against a site the agent never touched.

**Gate on CI, and let the gate wait.** The template ships `ci_status` and
`ci_green`: a phase is not done while the PR's checks are pending, and not done at
all while any is failing. Two things make this worth its own helper rather than an
instruction in the prompt. `gh pr checks` exits non-zero for *pending* as well as
*failing*, so the exit code cannot tell "still running" from "broken" — read the
buckets. And an agent that pushes at the end of its turn never sees the run
finish, so the loop is the only thing still present when the answer arrives.

Size `CI_WAIT_SECONDS` to the slowest workflow in the repo. A gate that gives up
after two minutes on a fifteen-minute test suite fails every good phase.

On a repo with **no** workflows, delete the gate and both helpers. `gh pr checks`
reports nothing there, so the gate would wait out its entire budget and fail every
phase for the absence of a thing that does not exist.

**A phase that moves code gets a grep gate.** A moved function that a dotted
string names is broken in a way no import error and no test catches, so
`smoke_check` greps for the old path. See
[Moving code that a string names](#moving-code-that-a-string-names).

**Include the status-lockstep gate.** The template ships it: phases before the
last must leave the spec in `in-progress/`, the final phase in `completed/`, and
`promote_spec.py --check` must pass. Keep it. Spec bookkeeping is what an agent
drops first when it is concentrating on code, and a shipped feature filed under
"not started" is how a tracker stops being worth reading.

## Tests: scoped, fenced, exit code

`{{TEST_CMD}}` names the test modules the phase touches, one line each:

```bash
docker compose exec backend bench --site frontend run-tests --module benchpress.tests.test_deploy_manager
```

Three rules, and each one has cost a real run.

**Never `--app benchpress`.** The whole suite is CI's job. It takes 60 seconds
against the live site, and eight of its tests fail on any developer site with
real rows, for a reason no phase can fix — the fence list below.

**Never name a fenced module.** `test_credit_sweep`, `test_demo_data`,
`test_lease` and `test_signup` call a production function that scans the whole
site, then assert on the whole result. `enforce_limits()["stopped"] == [my bench]`
is true on an empty site and false as soon as one real bench exists. Cardinality
is the property under test, so the assertions are correct and only unrunnable
here. CI stays green because `ci.yml` builds a fresh `test_site` first. A phase
that must touch one of these gates on CI alone, and its phase spec says so.
Tracked as [#196](https://github.com/Venkateshvenki404224/benchpress/issues/196):
delete a module from this list when that issue fixes it, not before.

**Read the exit code, never the output.** `run-tests` prints one summary per test
category, so any target holding both integration and unit tests prints two. The
last line is the second summary, and it says `OK` on a run that exits 1:

```
Ran 786 tests in 60.320s
FAILED (failures=7, errors=1)

Ran 153 tests in 0.282s
OK
```

A scoped command splits the same way — `--module benchpress.tests.test_deploy_manager`
is 86 tests then 30 — so the rule holds everywhere. No `tail`, no `grep -q OK`.
Only `$?` is honest.

**A phase that moves a string-named function names one more module.** The static
job-path tests are the gate that outlives the refactor, so every later phase of
the move runs them too. See
[Moving code that a string names](#moving-code-that-a-string-names).

## Moving code that a string names

A refactor phase that moves a function is not finished when the imports are
right. Frappe resolves a scheduled job and an enqueued job from a **dotted
string** at run time, through `frappe.get_attr`, so a name that moved leaves those
strings pointing at nothing. The two carriers fail in opposite ways, and the
persisted one is the silent one:

| Carrier | What a stale string does | The only trace |
|---|---|---|
| a `Scheduled Job Type` row, from `hooks.scheduler_events` | the job stops running, indefinitely | one `INFO` line in `logs/scheduler.log` |
| a `frappe.enqueue("…")` call site | the job fails once, at the moment it is queued | `ModuleNotFoundError` in `FailedJobRegistry` |

The scheduler row is the dangerous one because it goes on looking healthy.
`ScheduledJobType.execute()` catches the exception and `run_scheduled_job` catches
again, so nothing raises. No `Scheduled Job Log` row is written when the row has
`create_log = 0`, and no `Error Log` row appears either. `last_execution` still
advances, because `log_status("Start")` stamps it before the call — so the desk
list shows a job that ran a moment ago while a `*/5` reconcile has quietly
stopped.

### End the phase in this order

1. **Move the code and rewrite every string in the same commit** — call sites,
   `hooks.py`, docstrings, tracked `.md`, and the test assertions that name the
   path. A forgotten test assertion fails loudly, which is the cheapest gate here.
2. **`docker compose exec backend bench --site frontend migrate`.**
3. **`docker compose restart backend queue-long queue-short scheduler websocket`.**

Step 2 before step 3 is a rule, not a preference. `migrate` calls `sync_jobs()`
(`frappe/migrate.py:162`), which inserts the new `Scheduled Job Type` row and then
deletes the one whose method is no longer in `scheduler_events`. So the stale row
never outlives the commit, and a scheduler string never needs a `patches.txt`
entry. `migrate` runs inside `backend`, a fresh process reading the bind-mounted
new code, so it sees the new hooks while the un-restarted workers resolve the new
path straight from disk. Between steps 2 and 3 both paths work. **Migrating after
the restart is the order that opens the silent window.**

Before step 3, wait for `queue-long` — **bounded, and not a gate.** Poll for at
most 120 seconds, then go ahead anyway and log the depth it gave up at. A restart
already kills an in-flight deploy, so blocking until the queue is empty buys
nothing and can hang the loop behind a two-minute deploy.

### Never add a re-export shim

The reflex fix for a moved name is to re-export it from the old module. Do not.
A move that leaves any back-reference into the old module — and a partial extract
usually leaves one — makes the re-export a cycle, and the cycle breaks on the path
the workers take:

| Where the shim goes | Entered via the old module | Entered via the new module |
|---|---|---|
| top of the old module | `ImportError` | `ImportError` |
| bottom of the old module | works | **`ImportError`** |
| lazy import inside the new module | works | works |

The middle row is the trap. It is the form a reviewer asks for, it passes every
test that imports the old module first, and it fails on
`frappe.get_attr("<new module>.<name>")` — which is exactly what an RQ worker
calls. A shim that is green in CI and broken in every worker is worse than no
shim. Rewriting the strings costs one `git grep` and needs none of this.

### Job ids are frozen

An RQ `job_id` is a dedup key, not an import path, so moving the function cannot
break it. Renaming it during the move is what breaks: a job queued under the old
id is invisible to `is_job_enqueued` on the new one
(`frappe/utils/background_jobs.py:664`), so two runs of a job that exists to be
unique can overlap. `bench_instance.py:174`'s `deploy_bench:{self.name}` is the
live example — one id shared by deploy and redeploy on purpose, so that "a deploy
is already in progress" is true for both. Leave every job id exactly as it is,
across every phase of the move.

### The three gates

Two are static and one is a runtime check, and none needs a human.

**a. A repo-wide grep, in `smoke_check`.** After the phase, no moved name may
survive as `<old dotted module>.<name>` anywhere. Use `git grep`, not a
Python-only search: a docstring, a `.md` file or a JSON fixture holds these too.
Write the pattern with the module prefix and the trailing dot so it cannot match a
bare job id like `deploy_bench:`.

**b. Two static tests, added once in the first phase that moves anything.** They
generalize `benchpress/tests/test_scheduler_entries.py`, which already AST-walks
`scheduler_events` and proves the shape works:

- every string in `hooks.scheduler_events` resolves under `frappe.get_attr`;
- every `enqueue` target resolves — AST-walk each non-test `.py` under the app,
  take the first positional or `method=` `Constant` of each `enqueue` call, and
  resolve it.

This is the gate that outlives the refactor. Any later move of a job target then
fails a test instead of going quiet.

**c. One runtime assertion, after step 2.** Resolve every
`Scheduled Job Type.method` on the live site with `frappe.get_attr` and fail on
any that raises. Gate **b** proves the source is right. This one proves the
**database** is, which is the half no static check can see.

## Proving the UI

A green smoke check says the code is right. It says nothing about whether anyone
can see it. If the spec touches a page, the loop needs a browser, and
`agent-browser` is the one to use — check it launches **before** handing the loop
over, because an agent discovering a missing browser mid-phase spends an
iteration on setup instead of the feature.

Set `APP_URL` in the config block. The template's `preflight` refuses to start
when `APP_URL` is set and `agent-browser` is missing, which is the right moment
to find out.

Three things hide a correct, merged UI change. None of them fails a test, and all
three have cost real iterations:

| What | Why it hides the change | How the loop catches it |
|---|---|---|
| **Built assets older than the source** | the server ships compiled bundles, so the browser gets the previous build | `assets_stale` in `smoke_check` — a gate, not a habit |
| **A feature flag is off** | money-touching and half-built features hang off a settings toggle, and the whole surface renders exactly as it did before | read the flag in a helper and gate on it |
| **No row exercises it** | a feature keyed on a new column shows nothing while every row predating the migration has it `NULL` | the phase's verification has to create a row that carries the data |

The first is worth a gate rather than a note because it is invisible from inside
the code: every test passes, the component is correct, the diff is merged, and the
user sees the old page. Only a timestamp comparison catches it.

One more that wastes a whole debugging session: **check the page the feature
actually lives on**. A dashboard or overview that was never in the spec's scope
looks untouched no matter how right the work is.

## Why a loop stalls

Three causes, all observed, all silent — a stalled loop and a working loop look
identical from the terminal.

**The agent ends its turn waiting.** A headless `claude -p` session has no next
turn, so "I've started the drill in the background and will report when it
finishes" ends the iteration with the work half-done and the switches unrestored.
Say this in the prompt explicitly; it does not occur to an agent that has spent
its whole existence in interactive sessions. The template's *How an iteration
ends* section carries the wording.

**A `docker compose exec` under `timeout` takes SIGTTIN.** Covered in
[Designing smoke_check](#designing-smoke_check) — the fix is `</dev/null`. The
diagnosis is `ps -o pid,pgid,tpgid,stat`: `T`/`Tl` with `PGID != TPGID`, and
Ctrl-C cannot clear it because the stuck process is not in the terminal's
foreground group.

**A process outlives the session that started it.** A load harness or watcher an
agent backgrounded keeps mutating the system after its session dies, so the next
iteration's smoke check reads state nobody is maintaining. Tell the agent to stop
what it starts, and when a phase ends badly, check for orphans before re-running:
`ps -eo pid,ppid,etime,args | grep <your harness>`.

## Preflight and rollback

`preflight()` snapshots, once, everything that:

1. rollback needs — so recovering is a file copy rather than an act of memory, and
2. `smoke_check` compares against — counts, identity sets, the list of things that
   existed before.

Then write the rollback command into the phase prompt verbatim. Not "restore the
config" — the actual command, with paths. An agent mid-incident should not be
composing it.

State the order plainly: **restore first, diagnose after.** A rolled-back
iteration that leaves the system working is a good iteration.

## The two host gates

A spec's `## Host steps` section names three lists — Precondition, Leftover,
Never. See
[references/spec-templates.md](spec-templates.md#the--host-steps-section) for how
to write them. The loop turns two of those lists into gates. Prose alone was the
old convention, and prose does not stop a loop.

### Gate 1 — the precondition gate

In `preflight`, before anything changes. The command is read-only, needs no root,
and is **scoped to this spec**, never to the whole host.

```bash
# Exits non-zero when this spec's host precondition is unmet. Read-only, no root.
PRECONDITION_CMD='...'
PRECONDITION_FIX='sudo benchpress_devops/scripts/<script>.sh'

preflight() {
  if ! eval "$PRECONDITION_CMD"; then
    echo "[ralph] host precondition unmet. Run this, then re-run me:"
    echo "[ralph]   $PRECONDITION_FIX"
    exit 1
  fi
  ...
}
```

The scoping rule has teeth. `entry.py --check-host` exits 1 on this host right
now: six of twelve knobs are low and `/etc/sysctl.d` holds no
`99-benchpress-density.conf`, because item 5's leftover has never been run. A
whole-host gate would refuse to start every later loop until unrelated debt was
paid.

A spec with no precondition leaves `PRECONDITION_CMD` empty and deletes the
refusal.

### Gate 2 — the host-diff gate

In `smoke_check`, at every phase, and **fatal**. It snapshots exactly the surfaces
the Never list names, and nothing else.

```bash
# Exactly the surfaces the Never list names, and nothing else.
host_snapshot() {
  cat /etc/docker/daemon.json 2>/dev/null || true
  ls /etc/sysctl.d 2>/dev/null || true
  systemctl show docker --property=ActiveEnterTimestamp 2>/dev/null || true
  return 0
}

# inside smoke_check, before every other gate:
host_snapshot > "$SNAP_DIR/host.now"
if ! diff -q "$SNAP_DIR/host.before" "$SNAP_DIR/host.now" >/dev/null; then
  echo "[ralph] the host changed under the loop — STOPPING:"
  diff "$SNAP_DIR/host.before" "$SNAP_DIR/host.now" || true
  echo "[ralph] review the diff, undo it by hand, then re-run."
  exit 2
fi
```

**Fatal, not retract-and-retry.** Every other gate deletes the done marker and
lets the next iteration try again. This one exits 2, the blocked-marker path. A
host change is not something the next iteration can undo, so retracting would burn
every remaining iteration against an unfixable condition — and would keep an
unattended agent working on a host it has already changed.

`preflight` writes the `host.before` baseline. A human's legitimate run of a
precondition script **before** the loop starts is therefore inside the baseline,
so it never fires falsely.

### Why the named-artifact gate rots

The obvious gate is to check for the artifact the host step produces. It is wrong,
and the density loop is the worked example:

```bash
host_sysctl_applied() { [ -f /etc/sysctl.d/99-benchpress-density.conf ]; }
```

That fails when the file **exists**, which conflates "the loop did this" with
"this is done". The same spec tells a human to run `sudo tune-host.sh`, and that
script creates the file. From the moment the human obeys the spec, the loop fails
its smoke check at every phase on a correctly tuned host. The gate also catches
only the one step its author thought of.

A snapshot diff has neither fault. It has no opinion about who made a change or
which change it was, and an unforeseen host change is caught along with the
foreseen one.

The snapshots are close to free. The density loop's `preflight` already writes
eight `.before` files — `networks`, `legacy-members`, `containers`, `links`,
`sysctl`, `sysctl.d`, `daemon.json` and `head` — and no `.before` file is read
anywhere in that script. They are a human's rollback aid. This gate turns them
into a gate.

### Gate 3 is prose, and it is still needed

`prompt.md` restates the Never list in its Safety section, each entry with its
reason, because that is the text the agent actually reads. A rule without a reason
invites a clever exception.

### A leftover's durable home is tracked code, never a spec folder

`specs/` is gitignored in full and a completed spec is deleted, so a spec is
disposable scaffolding. A leftover is per-host state that outlives it: a second
host owes every leftover, not the ones this host happened to skip.

So the phase that creates the debt also ships a **read-only, non-root checker in
tracked code** and a line in the **operations runbook**. Item 5 shipped both —
`entry.py --check-host` and `benchpress_devops/PRODUCTION.md` §5.18. A spec whose
leftover no tracked command can detect is not finished, and no `promote_spec.py`
change is involved: `specs/STATUS.md`'s `⚠ by hand:` prefix is a working-tree
convenience, not the record.

## The phase prompt

**The prompt is not in ralph.sh.** It lives in `prompt.md` beside it, copied from
`assets/prompt.md.template`. `ralph.sh` reads that file, substitutes
`{{PLACEHOLDERS}}`, and passes the result to `claude -p`.

This split exists because the prompt is the part you actually tune. Buried in a
200-line bash heredoc it is unreadable and every edit risks the script; as
markdown it can be revised between runs with no change to ralph.sh, and the next
iteration picks it up.

How the file is laid out:

- Everything **above** the first `<!-- PHASE n -->` marker is sent for every phase.
- Below the markers, only the block matching the current phase is appended — this
  replaces the old `phase_extra()` bash function.
- Block comments are stripped before sending, so notes to whoever edits the file
  cost no tokens. A block comment is delimited by lines that are **only** `<!--`
  and `-->`; keep it that way, because prose mentioning `-->` inline on a
  delimiter line would end the comment early.
- Substitution is bash parameter expansion, never `eval` or `sed` — the prompt is
  markdown full of backticks, quotes and `$`, and both of those would execute or
  mangle it. An unrecognised `{{PLACEHOLDER}}` is left in place, so a typo shows
  up in the log instead of silently becoming an empty string.

The shared half already carries the parts that generalise: read order, branch/PR
flow, spec-status commands, comment discipline, notes contract, completion
contract, escape hatch. What you write per spec:

- **`{{FEATURE_SUMMARY}}`** — two or three sentences on what is broken and what
  the outcome is. The agent has no memory; this is its orientation.
- **`{{SAFETY_RULES}}`** — the irreversible things, stated as prohibitions with
  reasons. "Never X" alone invites a clever exception; "Never X, because Y" does
  not. Cover: what must never be deleted, what must never be restarted, which
  commands are out of bounds and why, and anything with a rate limit or a cost.
- **`{{HOST_NEVER_RULES}}`** — the README's Never list, verbatim, each with its
  reason. This is the prose half of the host-diff gate. The two must name the same
  surfaces, or the loop stops on something the prompt never warned about.
- **`{{EXTRA_RULES}}`** — repo-specific traps. Which lint command is wrong to run.
  Which services hold a stale module until restarted. Anything that has bitten
  someone.
- **the `<!-- PHASE n -->` blocks** — per-phase warnings. Put the destructive
  phase's order of operations here, phrased as "do not reorder them". A phase that
  moves a function named by a string is exactly this case: write out
  rewrite → `migrate` → restart, with the reason, because the wrong order fails
  silently. See
  [Moving code that a string names](#moving-code-that-a-string-names).

Write prohibitions where the agent will be when it needs them, and give the
reason. An agent that understands why a rule exists will not route around it.

## Filling in the template

Copy both files into the spec folder, then fill them in:

```bash
cp .claude/skills/issue-to-phases/assets/ralph.sh.template   specs/not-completed/<slug>/ralph.sh
cp .claude/skills/issue-to-phases/assets/prompt.md.template  specs/not-completed/<slug>/prompt.md
chmod +x specs/not-completed/<slug>/ralph.sh
```

In **`ralph.sh`** — the wiring:

| Placeholder | What goes in |
|---|---|
| `{{SPEC_SLUG}}` | folder name, e.g. `wildcard-cert-routing` |
| `{{RALPH_NS}}` | short namespace for markers/logs, e.g. `wildcard-cert` |
| `{{NOTES_PREFIX}}` | short prefix for notes files, e.g. `wc` |
| `{{APP_DIR}}` / `{{DEVOPS_DIR}}` / `{{WORKDIR}}` | absolute paths |
| `{{BRANCH}}` / `{{BASE_BRANCH}}` | from the spec README |
| `{{PHASE_FILES}}` | one quoted filename per line, in order |
| `{{ITER_TIMEOUT}}` | seconds per session; size it to the slowest phase |
| `{{APP_URL}}` | the running UI, for the browser checks — empty on a spec with no UI |
| `{{SRC_GLOB}}` / `{{BUILT_MARKER}}` | frontend source tree and one built asset, for `assets_stale` |
| `{{RISK_LINE}}` | one line telling the user what this loop will change |
| `PRECONDITION_CMD` / `PRECONDITION_FIX` | the spec's host precondition and the command that fixes it — empty on a spec with none |
| `host_snapshot` | the surfaces the Never list names, and nothing else |
| `{{HELPERS}}`, `{{PREFLIGHT}}`, `{{SMOKE_CHECKS}}` | bash, per above |

In **`prompt.md`** — the words:

| Placeholder | What goes in |
|---|---|
| `{{FEATURE_SUMMARY}}` | two or three sentences of orientation |
| `{{CONTEXT_DOCS}}` | the CLAUDE.md / design docs worth reading |
| `{{TEST_CMD}}` | one scoped `--module` line per test file the phase touches — see [Tests](#tests-scoped-fenced-exit-code) |
| `<!-- PHASE n -->` order of operations | any sequence the phase must not reorder, including a [string-named move](#moving-code-that-a-string-names) |
| `{{LINT_CMD}}` | the repo's real lint command |
| `{{EXTRA_RULES}}` | repo-specific traps |
| `{{SAFETY_RULES}}` | the irreversible things, each with its reason |
| `{{HOST_NEVER_RULES}}` | the README's Never list, each with its reason |
| `{{ROLLBACK}}` | the exact restore command, with paths |
| `<!-- PHASE n -->` blocks | per-phase warnings |

Everything else in `prompt.md` — phase number, ordinal, paths, markers, branch —
is substituted by `ralph.sh` at run time. Leave those alone.

Leave `{{APP_URL}}` empty on a backend-only spec and delete the `assets_stale`
helper with its gate — an empty `find` glob matches the whole tree and the gate
then fails on every run.

`RALPH_NS` and `NOTES_PREFIX` must be unique per spec. Two loops sharing a
namespace makes the second one skip every phase as "already done" and overwrite
the first one's notes.

## Before you hand it over

Six checks, all cheap, and each has caught a real bug:

```bash
bash -n ralph.sh                      # 1. syntax
```

2. **Run every helper by hand** against the live system and confirm each returns
   what you assumed. This is where a stale discriminator shows up. If the spec has
   a UI, launch the browser once too — `agent-browser open "$APP_URL"` — so a
   missing binary or a sandbox flag surfaces now rather than mid-phase.

3. **Execute `smoke_check` in a sandbox**, without starting the loop. Extract the
   config and function block into a scratch file, point `WORKDIR` at a temp
   directory, and call `preflight` then `smoke_check 0` and `smoke_check 1`:

```bash
sed -n '/^set -euo pipefail/,/^# ─── Prompt/p' ralph.sh | sed '$d' > /tmp/harness.sh
cat >> /tmp/harness.sh <<'EOS'
preflight
smoke_check 0 && echo "BASELINE PASS" || echo "BASELINE FAIL"
smoke_check 1 && echo "PHASE-1 GATE PASS" || echo "PHASE-1 GATE FAIL"
EOS
sed -i 's|^WORKDIR=.*|WORKDIR="/tmp/ralphtest"|' /tmp/harness.sh
bash /tmp/harness.sh
```

   Baseline must pass and the phase-1 gate must **fail** — on today's unmodified
   tree, naming the specific things the phase will fix. That pair is the
   calibration. Paste the output when you hand the loop over.

4. **Run `host_snapshot` by hand** and confirm every source reads without root.
   A source that needs root turns the gate into a permission error at every phase.
   Run `PRECONDITION_CMD` too, and confirm its exit code matches reality.

5. **`chmod +x ralph.sh`.**

Then tell the user how to watch it and how to stop it, and say plainly what it
will change.
