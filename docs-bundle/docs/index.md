---
title: BenchPress documentation
description: Start here. Three tracks — use a bench, run the server that hosts
  one, or read the data model and the API.
lastModified: "2026-08-30T17:48:34+05:30"
lastAuthor: Venkatesh
---
# BenchPress documentation

BenchPress deploys a Frappe bench from a template. An operator describes the
bench once. Anybody with access deploys it, works in it, and destroys it when
the task is done.

**Who this is for.** Three readers, three tracks. Read the track that matches
your job. You do not need the other two.

## Tracks

|Track|Read it when|Start at|
|--|--|--|
|User|Somebody gave you a login and you need a bench|[Quick tour](/docs/user/quick-tour)|
|Operator|You run the server that hosts the benches|[Operator track](/docs/operator)|
|Reference|You call the API or change the code|[Reference track](/docs/reference)|

All three tracks are published. Forty pages in total: 12 for a user, 16 for an
operator, 11 for reference, and this one.

## What BenchPress does

An operator describes a **lab** once: a Frappe version and a list of apps. A
deploy turns that lab into a running **bench instance**. The deploy restores a
cached image, creates a site, and puts the container on a WireGuard network.

You get a site address, an SSH login and a browser VS Code session. When the
work is done, you destroy the environment. Spin up, use, tear down.

A bench answers on up to four addresses at once: two public HTTPS addresses
served by Traefik, which anyone on the internet can reach once `base_domain` is
set, and two tunnel addresses that only a device on the VPN can reach.
`base_domain` is a required setting, so a bench is not VPN-only on the
documented install. [Networking](/docs/reference/networking) states the address
plan in full.

## Reference

One MDX source builds three surfaces. The `leadtype` pipeline writes all three.

|Surface|Path|Read by|
|--|--|--|
|Rendered pages|`docs-site/docs/**`|a person|
|Offline index|`docs-bundle/AGENTS.md`|a coding agent with a clone|
|Routing hints|`docs-site/llms.txt`|an agent over HTTP|

Rebuild every surface with one command:

```bash
npm run docs:build && npm run docs:lint && npm run docs:score
```

Every page states in prose whatever its screenshots show. Strip the images and
the page is still complete.

## Related

* [Quick tour](/docs/user/quick-tour) — the five screens, and what the dashboard reports.
* [Networking](/docs/reference/networking) — the four addresses a bench answers on, and who can reach each one.
