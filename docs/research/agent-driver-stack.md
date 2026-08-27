# Agent Driver: loop framework, model gateway, and what Frappe ships

Research for [issue #237](https://github.com/Venkateshvenki404224/benchpress/issues/237), a
ticket on map [#236](https://github.com/Venkateshvenki404224/benchpress/issues/236)
(Autonomous Coding Agent Harness, PRD v1.0). Verified against primary sources on
2026-08-27. Version numbers and provider claims move fast; re-check before the
PRD is signed.

## Verdict

The charting position holds, and holds for a better reason than charting knew:
**PydanticAI plus `pydantic-ai-harness` already ships most of the harness the
PRD specifies**, so the first driver is a wiring job, not a build. LangGraph is
rejected. **OpenHands is not rejected** — it is the designed-for second driver,
and its integration shape is known.

Recommended first driver: **PydanticAI + `pydantic-ai-harness`, pointed at any
provider through an OpenAI-compatible `base_url`, with LiteLLM as the gateway
when a repository's provider needs one.**

## Package facts

Versions from the PyPI JSON API; licenses from the GitHub API on the owning
repository. Both checked 2026-08-27.

| Package | Version | License | Requires Python |
| --- | --- | --- | --- |
| `pydantic-ai` | 2.35.1 | MIT | >= 3.10 |
| `pydantic-ai-harness` | 0.26.0 | MIT | >= 3.10 |
| `openhands-sdk` | 1.44.0 | MIT | >= 3.12 |
| `litellm` | 1.98.0 | MIT, plus an enterprise-licensed subtree | >= 3.10, < 3.15 |

The bench container runs **Python 3.14.2** (`docker compose exec backend python
--version`). Every candidate installs. BenchPress is AGPL-3.0-only
(`pyproject.toml`), so an MIT dependency is inbound-compatible.

**LiteLLM is the one to read before shipping.** GitHub reports its license as
`NOASSERTION` rather than MIT, because the repository is MIT with a carve-out
subtree under an enterprise licence. That is survivable — the proxy is a
separate process we run, not code we link — but it is a reason to keep LiteLLM
out of the Frappe app's own dependency set, which §3 argues for on packaging
grounds anyway. Legal should read the LICENSE file before v1.0 names LiteLLM as
a shipped component.

## 1. Does the loop framework hold up?

Yes. PydanticAI is OpenTelemetry-native — "the Instrumentation capability emits
standard OTel spans for every model call and tool call, and any OTLP backend
works" — and supports "virtually every model and provider (OpenAI, Anthropic,
Google, Bedrock, Azure AI Foundry, Groq, Mistral, xAI, Ollama, and dozens
more)" ([overview](https://pydantic.dev/docs/ai/overview/)).

What charting did not know is that `pydantic-ai-harness` exists and covers four
requirements the PRD treats as ours to build:

- **Coder** — FileSystem (read/write/edit/search), Shell with an allowlist,
  RepoContext, Planning, SubAgents (read-only explorer by default), and context
  management (ClearToolResults, WarnNearLimits, ToolOutputLimits). Both
  FileSystem and Shell are rooted at the workspace with path-traversal and
  symlink protection ([coder](https://pydantic.dev/docs/ai/harness/coder/)).
  This is FR-06's tool surface.
- **Step Persistence** — a `StepEvent` is appended at "every interesting
  boundary (run start/end, model request, tool call, failure)", with snapshots
  at settled tool boundaries, over InMemory / File / SQLite / Mongo stores, and
  `continue_run` / `fork_run` to resume or branch a prior run
  ([step-persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)).
  This is FR-09's resume-after-restart and most of §9's state machine.
- **Spend** — `SpendLimits` with USD and token ceilings over `run` / `day` /
  `month` windows, per-tenant `scope` callables, and `SpendLimitExceeded` raised
  before the next request starts. `RedisSpendStore` shares the counter across
  worker processes using Lua scripts
  ([spend](https://pydantic.dev/docs/ai/harness/spend/index.md)). This is
  FR-07, **and it lands on Redis, which BenchPress already runs** — no new
  datastore.
- **Guardrails** — guards at input, tool call, tool result, and output; a guard
  returning `block` skips execution and its refusal message becomes the tool
  result; `redact_secrets` and `redact_personal_data` rewrite text in place
  ([guardrails](https://pydantic.dev/docs/ai/harness/guardrails/)). This is the
  map's "redact secrets at write time" preference, implemented.

The library is on 0.x and says so: "these capabilities are tested end-to-end and
meant for production use", but APIs may shift between minor releases with
deprecation warnings. Pin it.

### Two limits to write into the PRD, not paper over

**The Coder shell allowlist is not a security boundary, and its own docs say
so.** Defaults are `git, rg, grep, find, ls, cat, sed, head, tail, python, uv,
pytest, ruff, make`; validation "only checks the first token", and permitted
commands like `python` and `git` "can spawn arbitrary processes, so deliberate
circumvention is possible" — it is "a guardrail against accidents, not a
security boundary" ([coder](https://pydantic.dev/docs/ai/harness/coder/)). The
docs' own advice is to "run the agent inside an OS-level sandbox such as
ModalSandbox or a container".

**This is fine, and it is precisely BenchPress's shape.** The container is the
security boundary; the allowlist is defence in depth. The PRD must say that in
those words, because a reader who assumes the allowlist enforces FR-06 will
under-build the container side.

**Guardrails do not stop prompt injection, and the docs are honest about it:**
pattern matching "does not find a prompt injection, which is ordinary
language", and it false-positives on log excerpts
([guardrails](https://pydantic.dev/docs/ai/harness/guardrails/)). No library on
this list solves §11. Hand that to
[#243](https://github.com/Venkateshvenki404224/benchpress/issues/243) with the
negative result attached.

### LangGraph: rejected

LangGraph's checkpointing was the stated reason to consider it, and Step
Persistence covers the same ground. LangGraph's own persistence docs list
InMemorySaver, SqliteSaver and PostgresSaver, and state that in-memory
checkpoints are lost on restart, so durability means Postgres or SQLite
([persistence](https://docs.langchain.com/oss/python/langgraph/persistence)) —
the same trade, plus a datastore BenchPress does not run. LangGraph ships **no
coding tool surface**, so adopting it means building FileSystem, Shell, git and
context management ourselves. It costs more and delivers less here.

## 2. Adopt a model-agnostic coding agent instead?

**OpenHands is stronger than charting credited, and the sandbox collision is
solvable.** It should be the second driver, not a rejected option.

- **Provider-agnostic through LiteLLM.** "OpenHands can connect to any LLM
  supported by LiteLLM", with Ollama, vLLM, LM Studio and SGLang named
  explicitly ([llms](https://docs.openhands.dev/usage/llms/llms)).
- **The SDK is MIT and separable from the product.** `openhands-sdk` 1.44.0
  ships "ready-to-use tools for executing Bash commands, editing files,
  browsing the web, integrating with MCP" ([sdk](https://docs.openhands.dev/sdk.md)).
- **Its policy enforcement is better than PydanticAI's on FR-06.** Confirmation
  policies (`AlwaysConfirm` / `ConfirmRisky` / `NeverConfirm`) plus deterministic
  analyzers (`PatternSecurityAnalyzer`, `PolicyRailSecurityAnalyzer`,
  `EnsembleSecurityAnalyzer`) run "at the action boundary — before the tool
  runs" with "no network calls, no model inference", and the host application
  can inspect pending actions and call `conversation.reject_pending_actions()`
  ([security](https://docs.openhands.dev/sdk/guides/security.md)). Risk levels
  are LOW / MEDIUM / HIGH / UNKNOWN.

**The sandbox collision, and its resolution.** The default runtime "creates a
new Docker container per session", building an OH runtime image from a base
image and mounting the workspace
([runtime](https://docs.openhands.dev/usage/architecture/runtime)). Inside a
BenchPress job container that would need `/var/run/docker.sock`, which is host
root — not acceptable. But OpenHands ships a **Process sandbox** that "runs the
agent server directly on your machine as a regular process", requires no
Docker, and provides "no sandbox isolation"
([process](https://docs.openhands.dev/openhands/usage/sandboxes/process.md)).
Its documented warning — the agent can do anything the user account can — is
the *correct* mode when BenchPress already owns the container and the container
is the boundary. That is the integration shape: **BenchPress provisions the
container; OpenHands runs as a process inside it in Process-sandbox mode.**

**Why it is still the second driver.** Adopting it first would put FR-06, FR-07,
FR-09 and FR-14 behind another project's abstractions on day one, and the PRD
has to commit to those four. PydanticAI's harness maps onto them component by
component and leaves the seam ours. Shipping the seam with one driver and a
credible second is what makes provider independence a design property rather
than a claim.

**Model quality is not a seam problem.** OpenHands warns that "open-weight and
local models still vary widely in tool-use reliability" and advises switching to
a stronger model on malformed-JSON errors
([llms](https://docs.openhands.dev/usage/llms/llms)). The seam guarantees a
model can be *connected*, never that it will succeed. §16's risk section should
say that outright.

## 3. What is Frappe shipping?

**Frappe Flow** — `frappe/flow_client`, first-party, AGPL-3.0-or-later, 59
stars and 357 commits on `develop`, actively developed with CI.

Its README: "AI agents for Frappe … puts an AI assistant inside your Frappe
site. It knows your DocTypes, respects your permissions, and can operate your
site in plain English" ([repo](https://github.com/frappe/flow_client)).

- **Doctypes**: agents with instructions plus model config, `Flow Trigger` (run
  on DocType events or a schedule), `Flow Knowledge Source` (RAG over files,
  URLs, DocTypes), `Flow Session` and `Flow Run` (conversation history and
  execution records).
- **Tools**: `read`, `create`, `update`, `delete`, `describe`, `run_action` —
  DocType operations, permission-respecting.
- **Providers**: model IDs like `anthropic/claude-sonnet-4-6`; Ollama and LM
  Studio via a Base URL.

**It does not duplicate this harness.** Flow is a business-automation assistant
operating a live site in natural language. It does not read issues, write code,
run tests, or open pull requests. Different actor, different tools, different
outcome. The PRD should state this in one line so no reviewer has to ask.

Two things do fall out of it, and both are useful:

**A real dependency collision.** `flow_client/pyproject.toml` pins
`litellm>=1.83.0,<1.83.8`; current LiteLLM is **1.98.0**. If the harness
declares LiteLLM as a Frappe-app dependency and a customer installs BenchPress
and Frappe Flow on one bench, pip conflicts. **Keep the driver's model calls out
of the Frappe app's dependency set** — inside the job container, or behind a
gateway process. This is an argument for the gateway, not just a packaging note.

**First-party precedent for the persistence shape.** Flow's `Flow Session` plus
`Flow Run` pair is Frappe's own answer to the question
[#242](https://github.com/Venkateshvenki404224/benchpress/issues/242) has to
settle. Worth copying the shape rather than inventing one.

Also first-party and worth a PRD line: **`frappe/skills`**, "agent skills for
Frappe App development" — structured Frappe knowledge for a coding agent. A
cheap quality win for the Coding Agent's context, and it is Frappe's own.

Community projects, for completeness, none first-party and none a coding agent
for this purpose: `lubusIN/frappe-skills`, `Dkm0315/frappe-agent`,
`KorucuTech/kai` (CrewAI as doctypes), `buildswithpaul/Frappe_Assistant_Core`
(MCP over ERPNext), `ERPGulf/changAI`.

## 4. Traces and killability

**Traces: yes, structured enough for FR-14.** OTel spans for every model call
and tool call, plus Step Persistence's `StepEvent` stream at run start/end,
model request, tool call and failure boundaries, plus snapshots. Persist the
step store as the trace of record and export OTel for §12's dashboards.

**Killability: solved by architecture, not by the framework.** Run the driver as
a **process inside the job container**, not in a Frappe worker. Cancellation is
then a signal to that process or a stop of the container; tool access dies with
the container and the short-lived push token is revoked. This sidesteps the
constraint map #236 already recorded from #210 — Python cannot kill a wedged
thread, which is why RQ forks a child.

**One finding to carry into FR-15.** A killed run is not simply "gone". Step
Persistence marks a snapshot `complete` "when every `ToolCallPart` has a
matching result, `interrupted` when the capture holds unsettled tool work", only
`complete` snapshots resume by default, and a tool with a `started` record and
no terminal update "should be treated as `unknown_after_crash`: the side effect
may or may not have happened"
([step-persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)).
So **cancelled must be a real terminal state with a dedup rule for
already-started tool effects**, not an absence. That belongs in §9's state
machine and in the cancellation fog.

## 5. The gateway

LiteLLM is confirmed as the gateway, with one caveat that changes the shape.

- The proxy is self-hostable and OpenAI-compatible, "calling 100+ LLMs", with
  virtual keys, per-key/user/team budgets, TPM/RPM limits and persisted spend
  ([quick start](https://docs.litellm.ai/docs/proxy/quick_start),
  [budgets](https://docs.litellm.ai/docs/proxy/users)).
- **Budgets require a database.** "Every budget on this page is enforced against
  spend read from the database, so none of them cap anything on a DB-less
  deployment" ([budgets](https://docs.litellm.ai/docs/proxy/users)). Per-model
  budgets, budget tiers and temporary increases are marked enterprise.
- PydanticAI reaches it as an OpenAI-compatible endpoint —
  `OpenAIChatModel(..., provider=OpenAIProvider(base_url=..., api_key=...))`,
  with LiteLLM, Ollama and vLLM all named
  ([openai](https://pydantic.dev/docs/ai/models/openai/)).

**Therefore the proxy is optional, not foundational.** Per-job budgets come from
`pydantic-ai-harness` spend limits on Redis we already run; a Postgres-backed
proxy on a single box to duplicate that is not worth it. What the proxy *does*
uniquely buy is **keeping the provider credential out of the job container**:
with default-deny egress, the container's only allowed model route is the
gateway, and the key never lands next to untrusted repository content. That is a
security argument, and it should be the PRD's stated reason for the gateway —
not budgets.

Recommended shape: BYO key per repository, stored BenchPress-side; the driver
inside the container talks to a gateway endpoint on an allowlisted host; LiteLLM
fills that role when a repository's provider needs translation, and a direct
`base_url` when it does not.

## Sources

- <https://pydantic.dev/docs/ai/overview/>
- <https://pydantic.dev/docs/ai/harness/>
- <https://pydantic.dev/docs/ai/harness/coder/>
- <https://pydantic.dev/docs/ai/harness/step-persistence/>
- <https://pydantic.dev/docs/ai/harness/guardrails/>
- <https://pydantic.dev/docs/ai/harness/spend/index.md>
- <https://pydantic.dev/docs/ai/models/openai/>
- <https://docs.litellm.ai/docs/proxy/quick_start>
- <https://docs.litellm.ai/docs/proxy/users>
- <https://docs.openhands.dev/sdk.md>
- <https://docs.openhands.dev/sdk/guides/security.md>
- <https://docs.openhands.dev/usage/architecture/runtime>
- <https://docs.openhands.dev/openhands/usage/sandboxes/process.md>
- <https://docs.openhands.dev/usage/llms/llms>
- <https://docs.langchain.com/oss/python/langgraph/persistence>
- <https://github.com/frappe/flow_client>
- <https://github.com/frappe/skills>
- <https://code.claude.com/docs/en/agent-sdk/overview>
- PyPI JSON API for the version and license table

## Appendix: the Claude Agent SDK, and why it is not the seam

Worth naming because it will be asked about. The Claude Agent SDK is "Claude
Code as a library": the same agent loop, built-in Read/Write/Edit/Bash/Glob/Grep
tools, hooks, subagents, permissions that "control which tools run
automatically, which need approval", and sessions that "resume or fork later"
([overview](https://code.claude.com/docs/en/agent-sdk/overview)). On capability
it is a strong driver.

It cannot be *the* driver. Use is "governed by Anthropic's Commercial Terms of
Service", and it is a route to Claude, not to any model — which fails the hard
requirement that "I have a local model, I connect it" be the same operation.
It is a good **third driver** for teams bringing Claude, behind the same seam,
and it is a useful proof that the seam is drawn in the right place: three
drivers with three different loops, one harness contract.
