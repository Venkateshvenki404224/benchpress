---
title: Configuration
description: Where each BenchPress setting lives — build arguments that need a
  rebuild, runtime environment that needs a restart, and DocType fields that
  apply on save.
lastModified: "2026-08-28T22:10:21+05:30"
lastAuthor: Venkatesh
---
# Configuration

Which knob lives where, and what changing it costs.

**Who this is for.** Somebody who changed a value and is waiting for it to take
effect.

**Before you start.** BenchPress is configured in three layers, and they behave
differently. A value in the wrong layer looks ignored. Read
[The three layers](#the-three-layers) before you change anything.

## The three layers

|Layer|Lives in|A change costs|Owns|
|--|--|--|--|
|Build arguments|`Dockerfile`, passed by `entry.py`|a rebuild|what is inside the control plane image|
|Runtime environment|`.env`, read by Docker Compose|a restart|ports, passwords, hostnames, the image tag|
|DocType settings|`BenchPress Settings`, `Credit Settings`|a save, and a cache clear|how benches are built, placed and priced|

Most of what a reader wants is the third layer, and it is documented field by
field in the [Settings reference](/docs/operator/settings-reference). This page
covers the first two, and the rule for telling them apart.

## Build arguments

Anything that changes what is inside the image is a build argument. Changing one
needs `--build`. A restart does nothing.

|Argument|Decides|
|--|--|
|`FRAPPE_BRANCH`|the Frappe version both image stages are built from|
|`FRAPPE_PATH`|where Frappe is cloned from|
|`APPS_JSON_BASE64`|the app list baked into the bench|

`entry.py` base64-encodes the preset and passes it as `APPS_JSON_BASE64`. The
preset is a JSON array of `{url, branch}` under `presets/`.

Rebuild after changing any of the three:

```bash
./entry.py --build --preset benchpress --frappe-version version-16
```

## Runtime environment

Everything else in `.env` is read when a container starts. A `down` and `up -d`
is enough. No rebuild.

|Variable|Decides|
|--|--|
|`PORT`|the port the dev checkout publishes|
|`SITE_NAME`|the control plane site name, always `frontend`|
|`PRESET`|which preset the checkout was built from|
|`INSTALL_APPS`|the apps `create-site` installs|
|`IMAGE_NAME`|the tag `--push` and `--pull` use|
|`ADMIN_PASSWORD`, `DB_ROOT_PASSWORD`|generated at setup|
|`PUBLIC_HOSTNAME`|the only switch between a dev checkout and a public deployment|
|`ACME_EMAIL`, `CF_DNS_API_TOKEN`|the DNS-01 certificate challenge|
|`DOCKER_GID`|the host's docker group, detected and never defaulted|
|`VPN_ENDPOINT_HOST`|the address devices dial to reach the tunnel|

**`PUBLIC_HOSTNAME` is the only switch.** Setting it appends the production
overlay to `COMPOSE_FILE` and turns a dev checkout into a public deployment. No
file in the repository names a hostname. A new domain is a flag, never an edit.

**`DOCKER_GID` must be detected.** The compose default is a Fedora value, and
Ubuntu hosts differ. `entry.py` writes the real value at setup and on every
`--build`.

## The site name invariant

The control plane site is `frontend` everywhere: in `.env`, in the Compose
defaults and in the nginx `FRAPPE_SITE_NAME_HEADER`. Do not change it without
auditing all three.

This is the control plane's site. It has nothing to do with the site inside a
bench, which is named from the instance id and the base domain.

## DocType settings

The third layer is two Singles. Both are documented in full in the
[Settings reference](/docs/operator/settings-reference), which reads its values
off a live host rather than out of a JSON file.

|Document|Fields|Edited in|
|--|--|--|
|`BenchPress Settings`|26|the app's Settings dialog for 10 of them, Desk for all|
|`Credit Settings`|16|Desk only|

Three rules apply to both.

1. **A Single is cached in each process.** After a save, run
   `bench --site <site> clear-cache` and restart the workers, or a worker keeps
   the old value.
2. **`0` often means the built-in default, not zero.** A field cleared to `0`
   behaves as though it was never set. `max_concurrent_uncredited` is the
   sharpest case: `0` there means unlimited.
3. **A size applies at the next deploy.** Editing an `Instance Size` does not
   resize a running container. The size is resolved during the deploy and
   written onto the bench.

`enable_credits` is the one field that changes what the whole product does. It
ships as `0`. Nothing in `Credit Settings` has any effect while it is `0`.

## Which change needs what

|You changed|It takes effect after|
|--|--|
|A preset, or `FRAPPE_BRANCH`|`./entry.py --build`|
|`PORT`, `IMAGE_NAME`, a password|`./entry.py --restart`|
|`PUBLIC_HOSTNAME`|`./entry.py --domain <fqdn>`, which regenerates `COMPOSE_FILE`|
|Python in the app|`docker compose restart backend`, and the workers if they import it|
|A Vue file or a bundle|`bench build --app benchpress`, then restart `backend frontend`|
|A hook, a fixture or a DocType schema|`bench --site frontend migrate`|
|A `BenchPress Settings` field|save, clear the cache, restart the workers|
|An `Instance Size`|the next deploy|
|A `Lab` app list|rebuilding the lab image|

## Verify

Read a settings value as a worker sees it, not as the JSON declares it:

```bash
bench --site <site> execute frappe.client.get_value \
  --kwargs "{'doctype':'BenchPress Settings','fieldname':['base_domain','enable_credits','default_bench_runtime']}"
```

Confirm which Compose files are in play:

```bash
grep COMPOSE_FILE .env
```

## Troubleshooting

|Symptom|Cause|Fix|
|--|--|--|
|A saved setting has no effect|The Single is cached in another process|Clear the cache, then restart the workers|
|A preset change did nothing|The app list is baked into the image|Rebuild with `--build`|
|A cleared field behaves as before|`0` falls back to the built-in|Set the number you want|
|The site is served in plaintext on a public host|The dev port mapping survived|The production overlay uses `ports: !override`|
|Docker calls fail with a permission error|`DOCKER_GID` is the default, not this host's|Re-run `--build`, which detects it|
|Every deploy is refused|`enable_credits` is `1` and nobody can pay|Set it back to `0`|
|A container resize did nothing|Sizes apply at deploy time|Redeploy the bench|

## Reference

|Fact|Value|
|--|--|
|Build arguments|3|
|`BenchPress Settings` fields|26|
|`Credit Settings` fields|16|
|Control plane site|`frontend`|
|Public switch|`PUBLIC_HOSTNAME`|
|Credits switch|`BenchPress Settings.enable_credits`, ships `0`|

`enable_credits` is a field on a Single, not a site config key.
`bench set-config -g enable_credits 0` writes an unrelated value and leaves the
flag on.

## Related

* [Settings reference](/docs/operator/settings-reference) — every field, measured on a live host.
* [Install](/docs/operator/install) — where `.env` comes from.
* [Data model](/docs/reference/data-model#benchpress-settings) — the two Singles as DocTypes.
* [CLI and scripts](/docs/reference/cli-and-scripts) — the commands named above.
