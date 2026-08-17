# BenchPress CPU sizing

This baseline was measured on 2026-07-02 on a two-vCPU KVM guest with an AMD EPYC 9355P host
CPU and 7.8 GiB RAM. The BenchPress backend ran Frappe 16.25.0. Docker's `--cpus` limit was
applied to `benchpress_backend`, the service that runs migrations, tests, authentication, and API
requests. Database, Redis, nginx, websocket, scheduler, and worker containers were not capped, so
these results describe the backend allocation rather than a whole-host CPU limit.

## Acceptance criteria

- Boot/lifecycle: migration and Administrator login complete without a timeout, and `/frontend`
  returns HTTP 200 with the `#app` mount.
- Test suite: `run-tests --app benchpress` passes, including every endpoint timing budget.
- Concurrent reads: 30 authenticated requests per endpoint at 10-way concurrency complete with no
  errors and p95 latency at or below 1,000 ms.

The candidate backend caps were 0.5, 1, 1.5, and 2 CPUs. Testing began at the lowest candidate; a
tier's minimum is the first cap that meets its criterion.

## Results

| Tier | Minimum CPU | Evidence at the minimum |
| --- | ---: | --- |
| Boot/lifecycle | 0.5 | Migration 13.22 s; login HTTP 200 in 192 ms; `/frontend` HTTP 200 in 27 ms |
| Test suite | 0.5 | The 124-test phase 1–3 suite passed in 11.59 s; endpoint timing budgets passed |
| Concurrent reads | 0.5 | `get_labs` p95 127 ms; `get_benches` p95 48 ms; 0/60 errors |

Concurrent-read comparison:

| CPU cap | `get_labs` p95 | `get_benches` p95 | Errors |
| ---: | ---: | ---: | ---: |
| 0.5 | 127 ms | 48 ms | 0 |
| 1 | 108 ms | 60 ms | 0 |
| 1.5 | 104 ms | 57 ms | 0 |
| 2 | 51 ms | 71 ms | 0 |

## Enforced baseline

The measured tier maximum is 0.5 CPU. `Lab.cpu_cores` is an integer DocType field, so fractional
allocations cannot be represented. The enforced baseline is therefore **1 CPU core**, the smallest
representable allocation at or above the measured minimum. One core is sufficient for all tested
tiers and provides headroom over the observed minimum.

The 0.5-CPU candidate did not visibly degrade this light workload, so the measurements do not
support claiming that one core is a performance minimum. The one-core floor is a schema-compatible
operational default. Re-run this benchmark after material application growth or when changing the
host class. Host compose resource limits remain a deployment option but are intentionally not set
by BenchPress.
