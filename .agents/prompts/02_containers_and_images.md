`<reasoning_effort>40</reasoning_effort>`

# containers_and_images

This app is a Docker client with a web interface: it builds images, creates containers, and
removes them again on a host it shares with the operator's own work. A container it creates
carries a lab user who holds root inside it, so every option passed to `containers.create` is a
security decision before it is an ergonomic one. The label on a container is the whole authority
for whether this app may delete it.

The test before creating, tagging or removing anything on the daemon: **if this ran on the
operator's own machine, what could it reach that it does not own?**

## container_creation

- Every container this app creates carries all three labels — `benchpress.managed`,
  `benchpress.bench_name`, `benchpress.lab` — defined once at `docker_manager.py:50-52`, because
  `list_benches` (`docker_manager.py:619`) and the event stream (`docker_events.py:23`) both
  filter on `benchpress.managed=true` and an unlabelled container becomes invisible and immortal.
- Claude never passes `privileged=True`. The tree contains zero uses, and
  `docker_manager.py:342-350` records the chain it would open: in-container root → host root →
  `docker exec benchpress-mariadb` → every tenant's database.
- Capabilities are added one at a time and named: `cap_add=["NET_ADMIN"]` at
  `docker_manager.py:357` exists so `wg-quick up wg0` works, and nothing else has earned an entry.
- Device access is explicit — `devices=["/dev/net/tun:/dev/net/tun:rwm"]` — not a bind of `/dev`,
  since the tunnel needs one node and a wildcard would hand over the rest.
- Every create sets `mem_limit`, `nano_cpus` and `pids_limit` (`DEFAULT_PIDS_LIMIT = 500`,
  `docker_manager.py:24`) plus per-device IOPS and bandwidth caps, because an unlimited container
  on a shared host is a denial of service against every other bench.
- A limit the host cannot enforce is reported, not silently dropped — `_storage_opt` returns a
  `disk_skipped` reason and `CreatedContainer.skipped` carries it to the operator.
- Claude does not mount a named volume over `/home/frappe`; the comment at
  `docker_manager.py:359-360` measured the cost — a full bench copy on every create.

## healthchecks_and_runtime

- Healthcheck durations are converted with `NANOSECONDS` (`docker_manager.py:38`) because Docker's
  API takes nanoseconds, and passing seconds yields an interval the daemon clamps while `inspect`
  reports the wrong value back as if it were right.
- The probe targets `localhost` inside the container (`BENCH_HEALTH_PROBE`), not the bridge, so it
  tests the server rather than the network path.
- `starting` is neither healthy nor unhealthy — `HEALTH_LABELS` maps it to `Unknown`, and Claude
  keeps that third state rather than collapsing it into a failure.
- A runtime is proven, not assumed: `preflight_runtime` runs a throwaway `alpine` container,
  because a broken runtime stays listed in `docker info` with its unit active.
- Claude reads back what the daemon actually did — `container_runtime` and `container_network`
  inspect `HostConfig` rather than trusting the value that was requested.

## images_and_the_build

- An image tag is the content hash of its build spec (`image_cache.cache_tag`), never the lab id,
  so two labs with the same recipe share one image instead of each holding a private copy.
- The Dockerfile's six layers are ordered cheapest-changing-last on purpose
  (`benchpress/lab-templates/Dockerfile:10-64`); Claude adds a new step at the layer its inputs
  belong to, since a `COPY` moved upward invalidates `bench init` and the app clone beneath it.
- Every `apt-get install` uses `--no-install-recommends` and ends with
  `rm -rf /var/lib/apt/lists/*` in the same `RUN`, because a cleanup in a later layer removes
  nothing from the image.
- The build context is `benchpress/lab-templates/`, which holds only `Dockerfile` and `scripts/`.
  There is no `.dockerignore`, so a file dropped into that directory ships to the daemon — Claude
  adds one before adding anything else to that folder.
- `api_client.build(..., network_mode="host")` at `docker_manager.py:193-201` is an undocumented
  deviation from the default bridge; Claude does not copy it elsewhere, and the team must confirm
  whether the app clone still needs it.
- Image tags across the tree float rather than pin: `frappe/build:${FRAPPE_BRANCH}`,
  `mariadb:${MARIADB_VERSION:-10.6}`, `valkey/valkey:8-alpine` and a default of
  `benchpress:latest` in `benchpress/config/docker-compose.yml:55`. A new service pins a version;
  `:latest` is never an acceptable default.
- The image ends on `USER root` (`Dockerfile:58`) because sshd and code-server need it — that is a
  deliberate alpha trade recorded in the repository README (`README.md:51-64`), not a pattern
  Claude extends to a new image.

## removal_and_reconciliation

- Claude removes a container only after confirming the `benchpress.managed` label, because the
  reconciler runs unattended and a filter mistake deletes an operator's own workload.
- `list_benches` includes stopped containers deliberately — an exited orphan still holds its
  writable layer, and a sweep that only saw running ones would never reclaim the disk.
- Image pruning goes through `image_cache.sweep_cached_images`, which subtracts `referenced_tags`
  and `in_flight_tags` first, since a tag being built right now has no container pointing at it.
- A retry is bounded and says why: `start_bench_container` rolls to the next bridge exactly once,
  never in a loop, because a second refusal means the recorded count disagrees with the daemon.
- `restart:` keys belong in the compose file, not `deploy.restart_policy` — the latter is a Swarm
  field and `docker compose up` ignores it, as the comment at `docker-compose.yml:58` records.

## what_not_to_do

- Do not create a container without the three `benchpress.*` labels — the reconciler cannot see
  it, and nothing will ever clean it up.
- Do not pass `privileged=True`, add a capability without naming its reason, or bind `/dev`.
- Do not tag an image `:latest` or reference an unpinned upstream tag in a new service.
- Do not put a healthcheck interval in seconds where the API wants nanoseconds.
- Do not shell out to the `docker` CLI when the SDK models the call; the tree has one such site
  and it exists only because compose has no SDK.
- Do not widen the build context or add files beside the `Dockerfile` while there is no
  `.dockerignore` to hold the line.
- Do not delete an image tag without subtracting the in-flight builds first.
