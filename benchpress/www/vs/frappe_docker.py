# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress.benchpress.site_content import (
	DOCS_INSTALL_ROUTE,
	SELF_HOST_ROUTE,
	VS_FRAPPE_MANAGER_ROUTE,
)
from benchpress.www.vs import render

ROUTE = "/vs/frappe-docker"

FRAPPE_DOCKER_URL = "https://github.com/frappe/frappe_docker"

no_cache = 1
sitemap = 1

# The positioning rule for every comparison page: different layer, never "better". BenchPress
# runs on frappe_docker's ideas, and a reader who feels the official repo being attacked stops
# reading. Every claim about it is checked against the repository, not remembered.
COMPARISON_SEED = {
	"eyebrow": "Comparison",
	"title": "BenchPress and frappe_docker.",
	"lede": (
		"<p>frappe_docker builds a bench. BenchPress hands one out. They are not rivals — "
		"BenchPress runs on the same ideas, and if you are happy writing a compose file you do "
		"not need it.</p>"
	),
	"cta_label": "See what self-hosting takes",
	"cta_url": SELF_HOST_ROUTE,
	"cta2_label": "frappe_docker on GitHub",
	"cta2_url": FRAPPE_DOCKER_URL,
	"related_label": "Also comparing? BenchPress and Frappe Manager",
	"related_url": VS_FRAPPE_MANAGER_ROUTE,
	"credit_title": "What frappe_docker is",
	"credit_body": (
		"<p><b>The official container setup for Frappe</b>, maintained in the framework's own "
		"organisation under MIT. It ships production images and a <code>compose.yaml</code>, a "
		"<code>pwd.yml</code> for a disposable demo, and a VS Code devcontainer for working on "
		"Frappe apps locally. It is the correct starting point, and it is where most teams "
		"start.</p>"
		"<p>It is also, by its own description, an <b>environment</b> — a configuration you "
		"take and adapt. The repository has around 2,500 stars and around 2,700 forks. More "
		"forks than stars is unusual, and it says something plain: teams copy it and edit it "
		"rather than run it as it comes. Each of those edited copies is a compose file somebody "
		"now maintains by hand.</p>"
	),
	"table_title": "The two, side by side",
	"table_lede": (
		"<p>Read the first four rows as the case for frappe_docker. It wins them, and it should.</p>"
	),
	"table_head": ["", "frappe_docker", "BenchPress"],
	"table_rows": [
		{
			"label": "Maintained by",
			"theirs": "Frappe Technologies, the framework's own team",
			"ours": "One author. Alpha, and the README says so first",
			"wins": "theirs",
		},
		{
			"label": "Production",
			"theirs": "Yes — that is half of what it is for",
			"ours": "No. Development and demo environments only",
			"wins": "theirs",
		},
		{
			"label": "Needs a server",
			"theirs": "No. A laptop with Docker is enough",
			"ours": "Yes. One Linux host, plus an existing Frappe v16 bench",
			"wins": "theirs",
		},
		{
			"label": "Community",
			"theirs": "Thousands of users, and every search result",
			"ours": "New, and small",
			"wins": "theirs",
		},
		{
			"label": "Getting an environment",
			"theirs": "Edit a compose file, build, create the site, install the apps",
			"ours": "Pick a template, press deploy",
			"wins": "ours",
		},
		{
			"label": "Who can do it",
			"theirs": "Someone who knows Docker and bench",
			"ours": "Anyone with a login. The bench commands stay in the log",
			"wins": "ours",
		},
		{
			"label": "Four clients, four app stacks",
			"theirs": "Four configurations, maintained by hand, free to drift",
			"ours": "Four lab templates, each pinned to a version and an app list",
			"wins": "ours",
		},
		{
			"label": "Reaching the site",
			"theirs": "Publish a port, or set up a proxy yourself",
			"ours": "A WireGuard address per environment, one revocable key per device",
			"wins": "ours",
		},
		{
			"label": "Editing the code",
			"theirs": "A local devcontainer, on the developer's own machine",
			"ours": "Browser VS Code inside the container that serves the site, shareable",
			"wins": "ours",
		},
		{
			"label": "When a build fails",
			"theirs": "Terminal scrollback",
			"ours": "The failing step named, in a deploy log kept per run",
			"wins": "ours",
		},
		{
			"label": "Tearing it down",
			"theirs": "`docker compose down -v`, and remember the volumes",
			"ours": "A confirmation that names the container, the site and the databases",
			"wins": "ours",
		},
		{
			"label": "Who has access",
			"theirs": "Whoever has the shell",
			"ours": "Roles and ownership: users see their own, admins see everything",
			"wins": "ours",
		},
	],
	"stay_title": "Stay with frappe_docker if",
	"stay_points": [
		"You are one developer, on one project, with one Frappe version.",
		"You are deploying production. BenchPress is not for that, and says so.",
		"You have no server to dedicate, and no appetite for alpha software.",
		"Writing a compose file does not cost you anything you mind spending.",
	],
	"switch_title": "BenchPress earns its place when",
	"switch_points": [
		"You maintain more than one client's app stack at a time.",
		"People who do not know Docker need working environments — a joiner, an intern, a "
		"designer, a client reviewing a build.",
		"You are the person environments always land on, and you would rather not be.",
		"Betas and client instances have to be reachable by the team and by nobody else.",
		"An environment should cost nothing when nobody is using it.",
	],
	"under_title": "It is the same machinery underneath",
	"under_body": (
		"<p>BenchPress is a control plane, not a runtime. It talks to a Docker daemon and runs "
		"the bench commands you would have typed — resolve the app list into an apps.json, "
		"build or restore the image, create the site, install the apps, migrate, build the "
		"assets, join the network, health-check, hand over the credentials. Eleven steps, each "
		"one visible in the log.</p>"
		"<p>Nothing about that is secret, and none of it is a replacement for frappe_docker's "
		"work. It is the layer above it: who gets an environment, how they reach it, and how it "
		"goes away.</p>"
	),
	"faq_title": "Questions people actually ask",
	"faq_items": [
		{
			"question": "Is BenchPress a replacement for frappe_docker?",
			"answer": (
				"No. BenchPress is a layer above it. frappe_docker defines how a Frappe bench "
				"runs in Docker; BenchPress turns one bench definition into something a whole "
				"team can each deploy for themselves, with access control, a private address "
				"and a teardown button."
			),
			"default_open": 1,
		},
		{
			"question": "Can I keep using my own frappe_docker setup?",
			"answer": (
				"Yes, and many teams should. BenchPress installs into a Frappe bench on one "
				"host and manages containers there; it does not ask you to abandon a compose "
				"file that already works for production."
			),
			"default_open": 0,
		},
		{
			"question": "Why not just add scripts to frappe_docker?",
			"answer": (
				"Because the missing parts are not scripts. Templates, roles, per-device network "
				"keys, a deploy log, leases and a teardown flow need somewhere to live and "
				"somebody to log in to. That is an application, which is what BenchPress is."
			),
			"default_open": 0,
		},
		{
			"question": "Which one is faster to a working site?",
			"answer": (
				"frappe_docker is faster the first time, on one machine, for someone who knows "
				"it. BenchPress is faster every time after that, for everyone else: a cached "
				"template deploys in about a minute, and the first person to need it is not the "
				"one who configured it."
			),
			"default_open": 0,
		},
	],
	"closing_title": "See what running it takes.",
	"closing_body": (
		"The preconditions, the real commands and the six things that break on a first install "
		"are on one page. If it looks like more than you want to own, the repo is right there "
		"and frappe_docker is not going anywhere."
	),
	"closing_cta_label": "Read the self-host page",
	"closing_cta_url": SELF_HOST_ROUTE,
	"closing_cta2_label": "Read the install guide",
	"closing_cta2_url": DOCS_INSTALL_ROUTE,
	"meta_title": "BenchPress vs frappe_docker — a bench, or a way to hand benches out",
	"meta_description": (
		"frappe_docker builds a Frappe bench; BenchPress hands one to each person who needs "
		"it. An honest comparison, including the four rows frappe_docker wins."
	),
	"og_image": "",
}


def get_context(context):
	return render(context, ROUTE, COMPARISON_SEED)
