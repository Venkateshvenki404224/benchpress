# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress.benchpress.site_content import (
	DOCS_INSTALL_ROUTE,
	SELF_HOST_ROUTE,
	VS_FRAPPE_PILOT_ROUTE,
)
from benchpress.www.vs import render

ROUTE = "/vs/frappe-manager"

FRAPPE_MANAGER_URL = "https://github.com/rtCamp/Frappe-Manager"

no_cache = 1
sitemap = 1

# The frame is a different unit of work — per developer against per team — never "better".
# Being generous about Mailpit, Adminer and `fm code` is what buys the rest its credibility.
# Every claim is checked against the repository and its docs, not remembered.
COMPARISON_SEED = {
	"eyebrow": "Comparison",
	"title": "BenchPress and Frappe Manager.",
	"lede": (
		"<p>Frappe Manager makes your environment easy. BenchPress makes somebody else's easy. "
		"The same machinery, one unit apart — and if the only bench you ever need is your own, "
		"<code>fm</code> is the better tool.</p>"
	),
	"cta_label": "See what self-hosting takes",
	"cta_url": SELF_HOST_ROUTE,
	"cta2_label": "Frappe Manager on GitHub",
	"cta2_url": FRAPPE_MANAGER_URL,
	"related_label": "Also comparing? BenchPress and Frappe Pilot",
	"related_url": VS_FRAPPE_PILOT_ROUTE,
	"credit_title": "What Frappe Manager is",
	"credit_body": (
		"<p><b>One CLI that creates and runs isolated Frappe benches</b>, from rtCamp — an agency "
		"with a long Frappe track record — under MIT, installed from PyPI with "
		"<code>uv tool install frappe-manager</code>. A single command gives you a bench at "
		"<code>&lt;name&gt;.localhost</code> with the database, the web server and the workers "
		"already wired together.</p>"
		"<p>It is well made, and it ships things BenchPress does not: <b>Mailpit</b> for catching "
		"mail, <b>Adminer</b> for the database, and <code>fm code</code>, which opens the bench in "
		"VS Code with a debugger already attached. If you are one developer looking after your "
		"own environment, that is a better answer than anything else on this page.</p>"
	),
	"table_title": "The two, side by side",
	"table_lede": (
		"<p>Read the first five rows as the case for Frappe Manager. It wins them, and it should.</p>"
	),
	"table_head": ["", "Frappe Manager", "BenchPress"],
	"table_rows": [
		{
			"label": "Maintained by",
			"theirs": "rtCamp, an agency with a long Frappe track record",
			"ours": "One author. Alpha, and the README says so first",
			"wins": "theirs",
		},
		{
			"label": "Adoption",
			"theirs": "414 stars, on PyPI, and in the Frappe manuals people read",
			"ours": "New, and small",
			"wins": "theirs",
		},
		{
			"label": "Needs a server",
			"theirs": "No. A laptop with Docker and Python 3.13 is enough",
			"ours": "Yes. One Linux host, plus an existing Frappe v16 bench",
			"wins": "theirs",
		},
		{
			"label": "Production",
			"theirs": "Yes, and it now describes itself as a production platform",
			"ours": "No. Development and demo environments only",
			"wins": "theirs",
		},
		{
			"label": "Mail and database tools",
			"theirs": "Mailpit and Adminer on every bench, unconfigured",
			"ours": "Neither yet. Both are on the list because of `fm`",
			"wins": "theirs",
		},
		{
			"label": "Whose environment it is",
			"theirs": "Yours. `fm create` builds a bench on the machine you are at",
			"ours": "Anyone's. You deploy one for the person who needs it",
			"wins": "ours",
		},
		{
			"label": "Describing a stack",
			"theirs": "`fm create <name> --apps ...`, retyped by whoever creates it",
			"ours": "A lab template, pinned once to a version and an app list",
			"wins": "ours",
		},
		{
			"label": "Who can create one",
			"theirs": "Someone comfortable in a terminal, holding the right flags",
			"ours": "Anyone with a login. The bench commands stay in the log",
			"wins": "ours",
		},
		{
			"label": "Who has access",
			"theirs": "Whoever has the shell. There is no user model",
			"ours": "Roles and ownership: users see their own, admins see everything",
			"wins": "ours",
		},
		{
			"label": "Reaching the site",
			"theirs": "`<bench>.localhost` on that machine, a public domain, or an ngrok tunnel",
			"ours": "A WireGuard address per environment, one revocable key per device",
			"wins": "ours",
		},
		{
			"label": "Editing the code",
			"theirs": "`fm code` opens a local VS Code with a debugger attached",
			"ours": "Browser VS Code inside the container that serves the site, shareable",
			"wins": "ours",
		},
		{
			"label": "When a deploy fails",
			"theirs": "CLI output, and `fm logs`",
			"ours": "The failing step named, in a deploy log kept per run",
			"wins": "ours",
		},
	],
	"stay_title": "Stay with Frappe Manager if",
	"stay_points": [
		"The bench you need is your own, on the machine in front of you.",
		"You want mail capture and a database browser without configuring either.",
		"You have no server to dedicate, and a laptop with Docker is what you have.",
		"You are heading for production on one host. That is where fm is going, and BenchPress is not.",
	],
	"switch_title": "BenchPress earns its place when",
	"switch_points": [
		"The environment you have to produce is somebody else's, not your own.",
		"Four clients means four app stacks, and the person deploying is not the person who chose them.",
		"The people who need environments should not have to own a terminal — a joiner, an intern, "
		"a designer, a client reviewing a build.",
		"A beta has to be reachable by the team and by nobody else.",
		"You want to know afterwards who deployed what, and which step failed.",
	],
	"under_title": "One unit apart",
	"under_body": (
		"<p>Both tools do the same unglamorous work: resolve an app list, build an image, create "
		"the site, install the apps, migrate, build the assets, hand back a URL. <code>fm</code> "
		"does it for the machine you are sitting at. BenchPress does it on a server, for whoever "
		"asked.</p>"
		"<p>That is the whole difference, and it settles everything else. A tool whose unit is a "
		"machine needs no users, no roles, no private address and no audit trail, and Frappe "
		"Manager is right not to carry them. A tool whose unit is a person cannot work without "
		"them.</p>"
	),
	"faq_title": "Questions people actually ask",
	"faq_items": [
		{
			"question": "Is BenchPress a replacement for Frappe Manager?",
			"answer": (
				"No. They work at different scales. Frappe Manager gives one developer a bench on "
				"their own machine; BenchPress runs on a server and gives a bench to each person "
				"who needs one, with roles, a private address and a teardown button. If the only "
				"bench you need is your own, fm is the better tool."
			),
			"default_open": 1,
		},
		{
			"question": "Can I use both?",
			"answer": (
				"Yes, and it is a sensible setup. Keep fm on your laptop for your own work, and "
				"run BenchPress on the team's server for the environments you hand to other "
				"people. Neither one knows or cares about the other."
			),
			"default_open": 0,
		},
		{
			"question": "Frappe Manager ships Mailpit and Adminer. Does BenchPress?",
			"answer": (
				"Not yet, and it is a real gap. A BenchPress bench gives you a shell and a browser "
				"VS Code session, so a mail catcher and a database client are things you add "
				"yourself. Both are on the list, and both got there by reading Frappe Manager."
			),
			"default_open": 0,
		},
		{
			"question": "Frappe Manager calls itself a production platform. Is BenchPress one?",
			"answer": (
				"No, and it will not claim to be. BenchPress builds development and demo "
				"environments. A lab user holds root inside their own bench, which without a "
				"user-namespace boundary is root on the host, and the install page says so before "
				"anything runs."
			),
			"default_open": 0,
		},
		{
			"question": "Which is faster to a working bench?",
			"answer": (
				"Frappe Manager, the first time, on your own machine — one install and one "
				"command. BenchPress is faster for the fifth person: a cached template deploys in "
				"about a minute, and nobody after the first has to know what is in it."
			),
			"default_open": 0,
		},
	],
	"closing_title": "See what running it takes.",
	"closing_body": (
		"The preconditions, the real commands and the six things that break on a first install "
		"are on one page. If the only bench you ever need is your own, install fm instead — it is "
		"a good tool and it is one command away."
	),
	"closing_cta_label": "Read the self-host page",
	"closing_cta_url": SELF_HOST_ROUTE,
	"closing_cta2_label": "Read the install guide",
	"closing_cta2_url": DOCS_INSTALL_ROUTE,
	"meta_title": "BenchPress vs Frappe Manager — your own bench, or one for each person",
	"meta_description": (
		"Frappe Manager gives one developer a bench on their own machine. BenchPress hands one to "
		"everyone who needs it — an honest comparison, including the rows fm wins."
	),
	"og_image": "",
}


def get_context(context):
	return render(context, ROUTE, COMPARISON_SEED)
