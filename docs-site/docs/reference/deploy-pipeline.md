---
title: Deploy pipeline
description: The eleven steps of a BenchPress deploy, in the order the code runs
  them, with the function behind each step and the log line it writes.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Deploy pipeline

What happens between a click on **Deploy** and a site that answers.

**Who this is for.** Somebody reading a deploy log, or changing what a deploy
does.

**Before you start.** A deploy takes minutes and runs in one background job on
`queue-long`. Nothing below happens in the web request. The request queues the
job and returns `{"status": "Deploying"}`.

## The eleven steps

`benchpress/deploy_pipeline.py` defines the steps. `lifecycle._deploy_bench`
runs ten of them, and `deploy_manager` runs the fifth.

|#|Key|Label|Runs in|
|--|--|--|--|
|1|`infrastructure`|Checking shared infrastructure|`lifecycle._deploy_bench`|
|2|`image`|Preparing the lab image|`lifecycle._prepare_lab_image`|
|3|`container`|Creating the container|`docker_manager.create_bench_container`|
|4|`container_ip`|Waiting for the container IP|`docker_manager.wait_for_container_running`|
|5|`vpn_peer`|Configuring the WireGuard peer|`deploy_manager._setup_container_vpn`|
|6|`site_config`|Writing common\_site\_config.json|`docker_manager.write_file_to_container`|
|7|`site`|Creating the site|`docker_manager.create_site_in_container`|
|8|`assets`|Preparing assets|`lifecycle._deploy_bench`|
|9|`ssh_user`|Provisioning the SSH user|`linkuser.sh`, in the container|
|10|`code_server`|Starting the lab's services|`serve.sh`, then `_start_code_server`|
|11|`complete`|Deploy complete|`lifecycle._deploy_bench`|

**The order is the order the code runs, not the order the design brief lists.**
The brief puts the WireGuard peer at position 10. `_setup_container_vpn` runs it
at 5, right after the container reports an address. The stepper reports the run,
so do not correct this to the brief.

## How a step reports itself

Each boundary writes one marker line into the Deploy Log.

```text
=== Step 4/11: Waiting for the container IP [container_ip @14.2s] ===
```

The `=== … ===` wrapper is load bearing. `LogViewer.vue` and
`lab_detail._parse_failure` both parse it, and every log written before the
stepper existed carries only that. Step metadata goes inside the marker, never
in place of it, so an old run still renders.

A failure writes its own marker:

```text
=== Deploy failed: <reason> ===
```

Each line is committed as it is written. A deploy holds one transaction for
minutes, so without the commit nobody could watch a run in progress or reload
after a dropped socket.

## Step 1. Checking shared infrastructure

Makes sure the shared MariaDB exists and answers, with a 60 second timeout.
Records which `Database Server` this run used, and commits that before anything
depends on it.

This step also writes the Traefik wildcard anchor when `base_domain` is set.
It runs first on purpose. A fresh install needs DNS-01 to finish issuing the
certificate before a bench route goes live, and that takes minutes.

Then it checks the runtime is registered. That check sits ahead of the image
step because the build is where the minutes go, and a bench the host cannot
isolate should not pay for one.

## Step 2. Preparing the lab image

One step whichever way it goes. The run either builds the lab image or adopts a
cached one, and the detail line says which.

A cached image is the normal path and costs seconds. A build costs an hour and
most of the disk. See [The image cache](/docs/operator/image-cache).

## Step 3. Creating the container

Before the container is made, the run removes the previous container and drops
the site database. Both halves of the last deploy go together, and they go
before the new container exists. Dropping a few hundred tables is teardown, not
part of creating the site that follows.

The instance size is resolved here and written onto the bench. It is never
copied onto the Lab, so a size edited in Desk reaches the next deploy and
billing keeps pricing what Docker was actually given.

The container id is committed as soon as it exists. A crash after this point
leaves something to clean up rather than an orphan nothing points at.

## Step 4. Waiting for the container IP

Waits up to 60 seconds for the container to report an address on its bridge.
The address is committed, because the route file is written from it.

## Step 5. Configuring the WireGuard peer

`deploy_manager._setup_container_vpn` generates the container keypair locally
and registers only the public key as a `VPN Peer`. The insert claims the tunnel
address atomically from the server pool.

The private key is written into the container and stored nowhere else.

This runs synchronously, which is possible because deploys run on `queue-long`,
and that worker mounts the WireGuard agent socket.

## Step 6. Writing common\_site\_config.json

Writes the bench's site configuration into the container, naming the database
host, the web server port and the default site.

## Step 7. Creating the site

Runs `bench new-site` inside the container against the shared MariaDB, and
installs the lab's apps. Frappe is dropped from the app list, because a site
always has it.

This step decides between two paths, and the log line says which one it took.

|Path|When|Costs|
|--|--|--|
|Restore from the golden dump|The lab has a golden image and the server matches|seconds|
|Create the site from scratch|No golden dump, or the server does not match|minutes|

A refusal to use the golden dump is logged with its reason rather than passed
over. See [Golden images](/docs/operator/golden-images).

A non-zero exit fails the run and the whole deploy.

## Step 8. Preparing assets

Nothing is built. Assets ship in the image, bundled at build time, and the step
logs exactly that.

Rebuilding the lab image is how a stale bundle is refreshed. A deploy never
builds assets, and a deploy will not fix a stale one.

## Step 9. Provisioning the SSH user

Runs `linkuser.sh` in the container to create the Linux account, using a
username derived from the owner's email address. The part before the `@` is
lowercased, stripped of invalid characters and capped at 32 characters.

The app's copy of `linkuser.sh` wins over the copy baked into the image.

The SSH password is generated for this run and stored on the bench as a
`Password` field. Read it with
[`get_bench_credentials`](/docs/reference/api#credentials).

## Step 10. Starting the lab's services

Runs `serve.sh` to serve the site on port 8000, then starts code-server if this
lab and this instance size include it.

The step is emitted even when code-server is off. A step the run decided to skip
is information, and a stepper missing its tenth row is not. The log says the IDE
was skipped and why.

The check uses the same resolver the route file was written from, so the router
and the process cannot disagree about whether this bench has an IDE.

## Step 11. Deploy complete

Moves the bench to `Running`, marks the Deploy Log `success`, commits, and
notifies the owner.

The eleventh step and the success line are one line. It carries the total
elapsed time, and the words "Deploy complete" are still in its text for
everything that reads the marker rather than the metadata.

Everything above this line is free however long it took. A deploy that never
gets here never reaches `Running`.

## Verify

Read the steps out of a finished run rather than trusting this page:

```bash
bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'Deploy Log','fields':['name','bench','log_type'],'limit_page_length':5}"
```

A successful run shows eleven ticked steps on the Lab detail screen. See
[Watch a deploy](/docs/user/deploy-from-template).

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|The run stops at step 1|The shared MariaDB is not answering|[The shared database server](/docs/operator/database-server)|
|Step 2 takes an hour|The lab has no cached image, so it built one|[The image cache](/docs/operator/image-cache)|
|The run stops at step 3|The bridge address pool is full, or the runtime is missing|[Prerequisites](/docs/operator/prerequisites)|
|The run stops at step 5|The worker has no WireGuard agent socket|Run the deploy on `queue-long`|
|Step 7 takes minutes every time|The lab has no golden dump|[Golden images](/docs/operator/golden-images)|
|Step 7 logs a refusal|The golden dump does not match the database server|Rebuild the golden dump|
|An old asset is still served|Assets ship in the image|Rebuild the lab image|
|Step 10 says the IDE was skipped|The lab or its size has code-server off|Expected. Turn it on in the Lab|
|The deploy log stops with no failure marker|The worker died mid-run|The `*/5` reconcile pass corrects the row|
|A second Deploy click does nothing|The job id deduplicates|Expected. Watch the running deploy|

## Reference

|Fact|Value|
|--|--|
|Steps|11|
|Queue|`queue-long`|
|Job id|`deploy_bench:<bench name>`|
|Deduplicated|yes|
|Infrastructure timeout|60 seconds|
|Container IP timeout|60 seconds|
|Site HTTP port|8000|
|IDE HTTP port|8080|
|Marker format|`=== Step N/11: <label> [<key> @<seconds>s] ===`|

## Related

* [Lifecycle and events](/docs/reference/lifecycle-and-events) — what happens after step 11.
* [Networking](/docs/reference/networking) — the addresses steps 4, 5 and 10 produce.
* [API](/docs/reference/api#benches) — the endpoint that queues this job.
* [Logs and monitoring](/docs/user/logs-and-monitoring) — reading a run as it happens.
