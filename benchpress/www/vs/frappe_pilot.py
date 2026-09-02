# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress.benchpress.site_content import (
	DOCS_INSTALL_ROUTE,
	SELF_HOST_ROUTE,
	VS_FRAPPE_DOCKER_ROUTE,
)
from benchpress.www.vs import render

ROUTE = "/vs/frappe-pilot"

FRAPPE_PILOT_URL = "https://github.com/frappe/pilot"

no_cache = 1
sitemap = 1

# Pilot is Frappe's own and has the web UI this product is usually described by, so the frame is
# a server against the people on it. Both projects are pre-1.0 and the page says so on both
# sides. Every claim is checked against the repository, not remembered.
COMPARISON_SEED = {
	"eyebrow": "Comparison",
	"title": "BenchPress and Frappe Pilot.",
	"lede": (
		"<p>Pilot looks after a server. BenchPress looks after the people asking it for "
		"environments. Both are early, both are open source, and they are not competing for the "
		"same job.</p>"
	),
	"cta_label": "See what self-hosting takes",
	"cta_url": SELF_HOST_ROUTE,
	"cta2_label": "Pilot on GitHub",
	"cta2_url": FRAPPE_PILOT_URL,
	"related_label": "Also comparing? BenchPress and frappe_docker",
	"related_url": VS_FRAPPE_DOCKER_ROUTE,
	"credit_title": "What Pilot is",
	"credit_body": (
		"<p><b>A server manager for Frappe</b>, in the framework's own organisation under "
		"AGPL-3.0 and installed with a <code>curl</code> script. It raises an admin UI on port "
		"8002 and manages the whole life of a bench and its sites — create, update, rename, back "
		"up, restore and drop — with an app marketplace built in.</p>"
		"<p>One <code>bench.toml</code> is the source of truth for all of it: the apps and their "
		"branches, MariaDB, Redis, the worker queues, nginx, gunicorn, Let's Encrypt, S3, the "
		"firewall and the WAF. It describes itself as experimental. BenchPress calls itself "
		"alpha. Neither is a safe place to put something you cannot afford to lose.</p>"
	),
	"table_title": "The two, side by side",
	"table_lede": ("<p>Read the first four rows as the case for Pilot. It wins them, and it should.</p>"),
	"table_head": ["", "Frappe Pilot", "BenchPress"],
	"table_rows": [
		{
			"label": "Maintained by",
			"theirs": "Frappe Technologies, in the framework's own organisation",
			"ours": "One author, outside it",
			"wins": "theirs",
		},
		{
			"label": "Production",
			"theirs": "Yes. nginx, gunicorn, systemd or supervisor, Let's Encrypt, a WAF",
			"ours": "No. Development and demo environments only",
			"wins": "theirs",
		},
		{
			"label": "Looking after the server",
			"theirs": "Backups to S3, a firewall, monitoring, site restore and rename",
			"ours": "None of it. BenchPress is not a server manager",
			"wins": "theirs",
		},
		{
			"label": "Installing apps",
			"theirs": "A marketplace in the admin UI, and `bench.toml` behind it",
			"ours": "The app list on a lab template. There is nothing to browse",
			"wins": "theirs",
		},
		{
			"label": "Maturity",
			"theirs": "Experimental, by its own description",
			"ours": "Alpha, by its own README",
			"wins": "",
		},
		{
			"label": "What it manages",
			"theirs": "One bench and its sites, on one server",
			"ours": "Many isolated benches, one per person who asked",
			"wins": "ours",
		},
		{
			"label": "Whose environment it is",
			"theirs": "The server's. One `bench.toml` describes it",
			"ours": "The requester's. One template, deployed once per person",
			"wins": "ours",
		},
		{
			"label": "Who has access",
			"theirs": "One admin password for the admin UI",
			"ours": "Roles and ownership: users see their own, admins see everything",
			"wins": "ours",
		},
		{
			"label": "Reaching a site",
			"theirs": "A public domain with Let's Encrypt, or the admin port",
			"ours": "A WireGuard address per environment, one revocable key per device",
			"wins": "ours",
		},
		{
			"label": "Editing the code",
			"theirs": "Not its job. You bring an editor to the server yourself",
			"ours": "Browser VS Code inside the container that serves the site, shareable",
			"wins": "ours",
		},
		{
			"label": "Throwing one away",
			"theirs": "Dropping a site from a bench you are keeping",
			"ours": "Destroying the environment — the container and the databases with it",
			"wins": "ours",
		},
		{
			"label": "Cost when idle",
			"theirs": "The bench and its sites stay up, because that is the point",
			"ours": "Leases and metering. An unused environment can be reclaimed",
			"wins": "ours",
		},
	],
	"stay_title": "Stay with Pilot if",
	"stay_points": [
		"You are running one bench with real sites on it, and it has to stay up.",
		"You want backups, TLS, a firewall and monitoring looked after for you.",
		"You would rather trust something inside Frappe's own organisation. That is a fair instinct.",
		"Nobody is asking you for an environment of their own.",
	],
	"switch_title": "BenchPress earns its place when",
	"switch_points": [
		"Each person needs a bench of their own, not another site on the one you already run.",
		"Four clients means four app stacks, on four different Frappe versions.",
		"The environments are disposable — made for a task, destroyed when it is done.",
		"A beta has to be reachable by the team and by nobody else.",
		"You want a browser editor you can hand to somebody, not a server you have to trust them on.",
	],
	"under_title": "A server, or the people on it",
	"under_body": (
		"<p>Pilot manages a server. It knows about one bench, its sites, its nginx, its "
		"certificates and its backups, and <code>bench.toml</code> is the single file that "
		"describes all of them. That is the right shape for something you intend to keep.</p>"
		"<p>BenchPress manages requests. Its unit is not a server but a person: somebody needs the "
		"client's stack, they get a container of their own with a private address and a VS Code "
		"window, and it goes away when the task does. The two barely overlap, and the overlap "
		"they do have — creating a bench, installing apps — is the part Pilot does better.</p>"
	),
	"faq_title": "Questions people actually ask",
	"faq_items": [
		{
			"question": "Is BenchPress a replacement for Pilot?",
			"answer": (
				"No. Pilot manages a server and the sites you keep on it; BenchPress makes "
				"disposable environments for people. If the problem is “this bench must stay "
				"up and be backed up”, Pilot is the tool. If it is “four people each need "
				"a different client's stack by Monday”, BenchPress is."
			),
			"default_open": 1,
		},
		{
			"question": "Pilot comes from Frappe and BenchPress does not. Why use BenchPress?",
			"answer": (
				"Because they answer different questions, and only one of them is about handing an "
				"environment to another person. Where the two overlap — creating a bench, "
				"installing apps — Pilot is the safer choice, and the table above says so."
			),
			"default_open": 0,
		},
		{
			"question": "Can I run both on one host?",
			"answer": (
				"In principle yes: Pilot manages the bench you keep, and BenchPress installs into "
				"a Frappe bench and drives Docker beside it. Nobody has tested the combination, so "
				"treat it as untried rather than supported."
			),
			"default_open": 0,
		},
		{
			"question": "Does BenchPress do backups, TLS and monitoring?",
			"answer": (
				"No. Those belong to an environment you mean to keep, and BenchPress builds "
				"environments you mean to throw away. The host itself is yours to look after, and "
				"the self-host page lists what that involves."
			),
			"default_open": 0,
		},
		{
			"question": "Both are early. Which is the safer bet?",
			"answer": (
				"Pilot, for anything you would be sorry to lose: it is experimental, but it sits "
				"in Frappe's own organisation. BenchPress is alpha, and a lab user holds root "
				"inside their own bench — which without a user-namespace boundary is root on the "
				"host. The install page says so before anything runs."
			),
			"default_open": 0,
		},
	],
	"closing_title": "See what running it takes.",
	"closing_body": (
		"The preconditions, the real commands and the six things that break on a first install "
		"are on one page. If what you actually need is one bench kept alive and backed up, Pilot "
		"is the better place to spend the afternoon."
	),
	"closing_cta_label": "Read the self-host page",
	"closing_cta_url": SELF_HOST_ROUTE,
	"closing_cta2_label": "Read the install guide",
	"closing_cta2_url": DOCS_INSTALL_ROUTE,
	"meta_title": "BenchPress vs Frappe Pilot — a server manager, or environments for people",
	"meta_description": (
		"Frappe Pilot manages one server's benches and sites. BenchPress hands a disposable "
		"environment to each person who needs one. An honest comparison of two early tools."
	),
	"og_image": "",
}


def get_context(context):
	return render(context, ROUTE, COMPARISON_SEED)
