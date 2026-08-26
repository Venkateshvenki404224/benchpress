# 1. Dial-out control bus with signed commands

- **Status:** Accepted. Not built.
- **Date:** 2026-08-26
- **Decides:** `todo.md` item 11
- **Ticket:** [ADR: dial-out control bus with signed commands (item 11)](https://github.com/Venkateshvenki404224/benchpress/issues/176)
- **Map:** [Map: scaling BenchPress for the agent-runtime load profile](https://github.com/Venkateshvenki404224/benchpress/issues/166)

## Context

BenchPress deploys to one host. `docker_manager` talks to a local Docker
socket, and no record anywhere names a host. A second host is not planned for
any current release.

The reason to decide now is cost asymmetry. Code that assumes it can open a
connection **to** a node is free to write today and expensive to unpick later.
Every deploy path, every sweep loop, and every job that touches a container
would need to change. This ADR fixes the constraint before that code exists.

Three facts about the current codebase shape the decision.

**A partial control path already exists.** `benchpress/credits/lease.py`
carries `local_node()`, `stop_queue_for()`, and `assert_local()`.
`local_node()` reads `benchpress_node` from the site config.
`stop_queue_for()` sends a stop to the RQ queue `bench_stop_<node>` when the
bench belongs to another host. `assert_local()` refuses a stop for a container
that this Docker daemon does not hold. The comment on `assert_local` states the
reason. `docker_manager.stop_container` treats `NotFound` as success, so a stop
that reaches the wrong host marks the row `Stopped` while the container keeps
running somewhere else.

**Those queues carry pickle, not data.** Frappe builds every queue through
`Queue(generate_qname(qtype), connection=get_redis_conn(), is_async=is_async)`
in `frappe/utils/background_jobs.py:544`. The call passes no `serializer`, so
RQ 2.6.1 applies its default. A measurement on this host returned
`b'\x80\x05\x95...'` from `resolve_serializer(None).dumps(...)`. That is pickle
protocol 5. A worker on a customer host that reads an RQ queue from a shared
broker runs any Python object the broker holds. This is why the per-node RQ
queues are a local mechanism and must not become the bus.

**WireGuard already removes the need for a public inbound port.**
`vpn_adapter.py` puts every bench container on a WireGuard mesh, and
`vpn_management` owns the `Wireguard Server` record. A host added as a peer is
reachable over the tunnel with no port open to the internet.

## Decision

Nodes dial **out** to a Redis or Valkey Streams broker. A node never listens
for a control connection. Commands are JSON. Every command carries an Ed25519
signature that the node verifies before dispatch.

### What a node is

A `Node` doctype record. Its `name` is the string that
`site_config.benchpress_node` already holds, so existing `Bench Instance.node`
values migrate without a rewrite. The record holds the node public key, the
last heartbeat time, the consumer name, and the status.

`Bench Instance.node` changes from `Data` to `Link(Node)`. Item 12 hangs its
capacity figures on the same record.

### Transport

The control plane appends a command with `XADD`. Each node reads its own
stream with `XREADGROUP` under a consumer group. The node acknowledges a
finished command with `XACK`.

A stream keeps a command while a node is down, and the node collects it on the
next read. This is the property that a direct call over the WireGuard tunnel
does not have, and it is the reason to run a broker next to a mesh that already
works.

The broker needs a password and TLS. The current `redis-queue` service has
neither. `CONFIG GET requirepass` returned an empty value, and the service is
reachable only on the internal bridge. The bus broker is a separate service
from `redis-queue`, and it is not the queue that Frappe uses.

### Signing

The control plane holds an Ed25519 private key. Every node holds the matching
public key.

- The plane signs the canonical JSON body of each command.
- The node verifies the signature against the public key before it dispatches
  anything.
- The private key lives in a Frappe `Password` field, the same way
  `Database Server.mariadb_root_password` does.
- The public key lives on the `Node` record and in the node agent config.

The pair is asymmetric on purpose. A stolen node key forges nothing, because
the node holds only the verifying half. Rotation ships a new public key and
accepts both keys for one overlap window.

No signing primitive exists in the app today. Any choice here is new code.

### A command that fails verification

The node does three things, in this order.

1. Acknowledge the command with `XACK`, so the broker never redelivers it.
2. Copy the body, the reason, and the node name to a dead-letter stream.
3. Raise an alert.

A forged command is a security event, not a transient fault. An unacknowledged
bad command returns on every reclaim pass, which retries the forgery on the
attacker's behalf.

### Heartbeat

Each node writes a Redis key with a TTL on a fixed interval. A missing key
means the node is gone. The `Node` record records the last heartbeat time for
the desk view. The TTL key, not the record, is the liveness source, because the
key expires without anyone running a sweep.

### Reclaim and the age ceiling

A crashed node leaves commands in the pending entries list of its consumer
group. `XAUTOCLAIM` moves them to a live consumer after a minimum idle time.
Redis 6.2 supports `XAUTOCLAIM`, and the running `redis-queue` reports
`6.2.23`.

A command older than the age ceiling is discarded, not reclaimed. The reason is
the failure that item 11 records: a broker replayed stale delete commands the
moment reclaim started working.

**The age ceiling measures against the broker clock only.** Node wall clocks
never enter the calculation. Two broker-supplied values give the age.

- The stream entry ID starts with the broker millisecond timestamp. A
  measurement on this host returned entry ID `1787739456450-0` against a broker
  `TIME` of `1787739456000` ms.
- `XPENDING` reports idle time that the broker measures. The same measurement
  returned `2004` ms after a two second wait.

Clock skew between a node and the broker is therefore not a risk to manage. It
is a value that no part of this calculation reads.

### Per-bench locks and preempting verbs

A lock is per bench. A verb holds it, and a higher-ranked verb takes it.

| Rank | Verb | Job today |
|---|---|---|
| 4 | `bench.destroy` | `credits.reaper.reap_bench` |
| 3 | `bench.stop` | `deploy_manager.stop_bench` |
| 2 | `bench.redeploy` | `deploy_manager.redeploy_bench` |
| 1 | `bench.deploy` | `deploy_manager.deploy_bench` |
| 0 | `bench.route_sync` | `deploy_manager.sync_instance_route` |

A higher rank cancels the current holder. The agent then runs the same cleanup
that `deploy_manager._cleanup_failed_deploy` runs today, so no container
survives a cancelled deploy.

This costs a wasted build. It buys a lease that always expires on time. Without
preemption, a wedged deploy holds the bench lock past the lease deadline, and
the platform bills for compute that never became usable. The lease sweep in
`lease.claim_due` already assumes a stop it enqueues will run.

## Alternatives considered

**WireGuard tunnel and a node HTTP API.** The node joins the existing mesh and
listens on its tunnel address only. This adds no broker and no second set of
keys, because the WireGuard keypair is already the identity.

Rejected on durability. A command sent to a node that is down is a failed
request. The control plane then owns retry state, delivery order, and crash
recovery, and rebuilds by hand what a consumer group provides. The tunnel stays
the right path for synchronous work such as logs, exec, and a stats scrape.

**Per-node RQ queues, extended across hosts.** The mechanism exists in
`lease.stop_queue_for`, so this looks like the smallest change.

Rejected on the pickle measurement above. It also needs a MariaDB connection
from every customer host to the control plane database, because an RQ worker in
Frappe is a full Frappe process.

**Transport identity only, with no per-message signature.** Trust that a
command arrived over the tunnel from the control plane address.

Rejected. A compromised broker then injects commands with nothing left to stop
it. Item 11 records an unsigned bus as the finding that blocks real customers.

**Reject the item and stay single node.** Keep only the constraint that nothing
may assume inbound access.

Rejected. The constraint alone does not tell a reader what shape to build
toward, and the questions settled above are cheaper to answer now than under
delivery pressure.

## Constraints on work built before the bus

This section is what other work consumes. Each line is checkable in review.

1. **No component opens a connection to a node.** Control flows out from the
   node. Today every path is local, so this costs nothing.
2. **A cross-node work item is JSON.** Nothing crosses a node boundary as a
   pickled RQ payload. The per-node queues in `lease.stop_queue_for` stay a
   local mechanism against the local broker.
3. **Name a host through `lease.local_node()` and `Bench Instance.node`.** New
   code does not read a hostname from the environment and does not invent a
   second host identifier.
4. **A node-bound operation is idempotent.** Stream delivery is at least once,
   so every operation runs twice without harm.
5. **A node-bound operation declares a verb from the rank table.** An operation
   with no verb cannot take part in preemption.
6. **No operation depends on node clocks agreeing.** Read time from the broker
   or the database, never from a node wall clock.
7. **Keep `lease.assert_local`.** The guard that refuses work for a daemon this
   process does not hold stays in place after the bus lands.

## Measurements

All values come from this host on 2026-08-26.

| What | Value | How |
|---|---|---|
| RQ version | 2.6.1 | `rq.__version__` in the bench env |
| RQ default serializer output | `b'\x80\x05\x95...'` | `resolve_serializer(None).dumps({'a': 1})` |
| Broker version | 6.2.23 | `redis-cli INFO server` on `redis-queue` |
| `requirepass` on `redis-queue` | empty | `redis-cli CONFIG GET requirepass` |
| `XAUTOCLAIM` present | yes | `redis-cli COMMAND INFO XAUTOCLAIM` |
| Stream entry ID against broker `TIME` | `1787739456450-0` against `1787739456000` ms | `XADD` then `TIME` |
| `XPENDING` idle after a two second wait | `2004` ms | `XPENDING <stream> <group> - + 10` |
| Node-bound job targets today | 6 of 9 | `deploy_bench`, `redeploy_bench`, `stop_bench`, `reap_bench`, `sync_instance_route`, `reconcile_instance_routes` |

## Consequences

- Item 12 inherits the `Node` record and reports its figures against it.
- The bus broker is a new service to run, secure, and monitor. It is not
  `redis-queue`.
- Signature verification and canonical JSON are new code with no precedent in
  the app.
- A cancelled deploy wastes a build. The lease deadline holds in exchange.
