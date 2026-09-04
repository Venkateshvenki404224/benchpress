`<reasoning_effort>40</reasoning_effort>`

# data_access_and_cost

Every screen in this app reads rows that grow without bound — deploy logs, bench events, ledger
entries, containers on a host. 56 of the 88 `frappe.get_all(` / `frappe.get_list(` call sites
declare no `limit`, and nine `for` loops issue a per-row `get_doc` or `get_value` inside them.
Each one is cheap on a demo host and expensive on the host that matters, which is why the cost of
a read is decided when it is written and not when it is reported.

The test before writing a query, a loop or a component: **what is the largest number of rows this
touches on a busy host, and what bounds it?**

## bounding_a_read

- Benchpress passes an explicit `limit` to every `get_all` / `get_list`, because a list that is
  short in development is the same list that has 40 000 deploy log rows in production.
- The limit is a named constant at module scope, not a literal in the call —
  `overview.py:22-24` declares `ENVIRONMENT_LIMIT = 6`, `ACTIVITY_LIMIT = 6` and
  `DEPLOY_SAMPLE_LIMIT = 50`, so a screen's cost is legible without reading its queries.
- An intentionally unbounded read says so in a comment beside it. `api.py:485-487` is the model:
  a teardown must be exhaustive, and the comment names the bug the bound would cause.
- A statistic never claims a window longer than the data retained for it —
  `overview.py:26-28` derives `LOG_RETENTION_DAYS` from `default_log_clearing_doctypes` rather
  than hard-coding a number that log clearing will quietly invalidate.
- Benchpress requests only the fields it renders. A `fields=[...]` list is cheaper than a `get_doc`
  and it documents what the caller actually depends on.
- A count is a count, not `len()` over fetched rows, since fetching a thousand documents to
  measure how many there are pays the whole transfer cost for one integer.
- An index is declared in `benchpress/indexes.py` rather than assumed — a filter added to a hot
  list query without one turns a bounded read into a full scan.

## avoiding_per_row_work

- One query per collection, then join in Python — `overview.py:4-11` states the rule in its own
  docstring and the module keeps it across five collections in a single request.
- Benchpress does not call `frappe.get_doc`, `frappe.get_cached_doc` or `frappe.db.get_value` inside
  a loop over rows; nine sites in the tree still do, including `docker_events.py:171` and
  `lab_templates.py:522`, and they are debt rather than precedent.
- A lookup reused across a request is memoised with `request_cache.local_cache`, as
  `docker_manager.host_runtimes` does — built once per job, torn down with the request, never a
  module-level dict, since forked workers outlive one.
- A Docker call inside a loop is the expensive case: `hooks.py:255` records that the stats sweep
  spends about two seconds per container on the socket, which is why no decision job shares its
  cron slot.
- Benchpress batches a scheduled sweep onto the worker that already holds what it needs —
  `queue-short` has neither the Docker socket nor the route mount, and a job placed there fails
  with nothing useful in the log.

## frontend_render_cost

- Derived values are `computed` (143 uses), never recomputed in a template expression, because a
  template expression re-evaluates on every render and a `computed` caches on its dependencies.
- `watchEffect` has zero uses and stays there; `watch` (17 uses) names its source, which is what
  makes a re-render traceable in review.
- Anything periodic subscribes to `frontend/src/utils/clock.js` rather than starting its own
  timer — one `setTimeout` serves every subscriber, aligned to the server's corrected second, and
  the subscribe call returns its own unsubscribe.
- The SPA has zero `setInterval` uses and pairs all three `setTimeout` calls with a `clearTimeout`;
  Benchpress keeps that pairing, since a timer surviving unmount fires against a dead component.
- There is no `AbortController` anywhere in `frontend/src`, so a request from an abandoned screen
  still completes. Benchpress does not add a new long-running fetch without cancelling it, and the
  team must decide whether to retrofit the existing ones.
- The largest component is `pages/LabDetail.vue` at 424 lines. A screen approaching that size gets
  a child component under `components/<area>/`, which is how the existing 47 components arose.

## bundle_and_build

- Build target is `es2015` and `chunkSizeWarningLimit` is 1500 (`frontend/vite.config.js:25-28`);
  Benchpress does not raise the limit to silence a warning — the warning is the signal.
- Sourcemaps are off deliberately: `vite.config.js:17-20` records that a 3.2 MB `.js.map` once
  shipped to every browser, and `buildConfig` is the only place that setting is declared.
- `optimizeDeps.include` at `vite.config.js:36` pre-bundles `feather-icons` and
  `highlight.js/lib/core`, neither of which `frontend/src` imports — Benchpress removes an entry
  there when removing its last import rather than leaving the pre-bundle behind.
- Nothing generated is committed: `benchpress/public/frontend/` has zero tracked files, and the
  SPA is rebuilt with `yarn build` or `bench build --app benchpress`.
- A stylesheet's content hash changes on every build even when the file did not, because Frappe's
  postcss step copies the source through a randomly named temp directory that lands in the
  sourcemap. Benchpress does not chase that diff; scripts are content-stable and stylesheets are
  not.

## what_not_to_do

- Do not write a `get_all` or `get_list` without a `limit`, or with a bare integer where a named
  constant belongs.
- Do not put `get_doc`, `get_cached_doc` or `get_value` inside a loop over rows.
- Do not open a Docker socket call inside a loop, or add work to the one-minute stats cron.
- Do not start a bare `setInterval` or an unpaired `setTimeout` in a component.
- Do not raise `chunkSizeWarningLimit`, re-enable sourcemaps, or commit build output.
- Do not cache anything in a module-level global in Python — forked workers keep it alive.
- Do not report a statistic over a window longer than the retention that feeds it.
