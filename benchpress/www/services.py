# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress import structured_data
from benchpress.benchpress.site_content import (
	DOCS_INSTALL_ROUTE,
	SELF_HOST_ROUTE,
	SERVICES_ROUTE,
	canonical_url,
	chrome_content,
	preview_tags,
)
from benchpress.public_site import require_public_site

no_cache = 1
sitemap = 1

# No price, no rate and no response window: pricing is not decided, and a number on this page
# would be the only one on the site.
SERVICES_SEED = {
	"eyebrow": "Done for you",
	"title": "Have us do the parts you would rather not.",
	"lede": (
		"<p>The software is free. The afternoons are what we sell. Run BenchPress yourself and "
		"it costs nothing but a server — these are the four engagements for when you would "
		"rather hand a piece of it over.</p>"
	),
	"cta_label": "Book a 20-minute call",
	"cta_url": "/contact",
	"cta2_label": "Or install it yourself",
	"cta2_url": SELF_HOST_ROUTE,
	"warn_title": "You may not need us",
	"warn_body": (
		"<p>The install is documented step by step, and self-hosting is free forever with no "
		"account and no ceiling on labs. If you have a spare Linux box, a Frappe v16 bench and "
		"an afternoon, do it yourself — the guide exists so that you can. Pay us when the "
		"afternoon is worth more than the money, or when you want the host to be somebody "
		"else's problem.</p>"
	),
	"offers_title": "The four engagements",
	"offers": [
		{
			"number": "01",
			"icon": "server",
			"title": "Managed hosting",
			"meta_label": "Hosted, monthly",
			"body": (
				"We run the host, the WireGuard plane and the upgrades. Your team gets a console, "
				"a credit balance and a ledger that shows every line."
			),
			"includes": [
				"A host we run, patch and watch",
				"Per-device WireGuard keys, revocable in a click",
				"Nightly database dumps, and the restore path tested",
				"Upgrades, including the lab images",
			],
			"excludes": (
				"Not production hosting. BenchPress runs development and demo environments; a "
				"live client site does not belong on it."
			),
			"needs": "Your app list and the Frappe versions your team works on.",
		},
		{
			"number": "02",
			"icon": "hammer",
			"title": "Setup on your server",
			"meta_label": "One-time, fixed scope",
			"body": (
				"One engagement, on your machine, ending in a deploy you watched succeed. The "
				"same six steps the guide describes, done by someone who has done them before."
			),
			"includes": [
				"The preconditions checked on the host before anything is installed",
				"Both apps installed, the setup script run under --strict",
				"WireGuard configured and your first device enrolled",
				"Your lab templates seeded, and a first deploy proven green",
				"The twelve diagnostics run in front of you, and the keys handed over",
			],
			"excludes": "Not buying, sizing or hardening the server. That stays yours.",
			"needs": (
				"Shell access to a host that meets the prerequisites, and a domain you control "
				"for the base domain."
			),
		},
		{
			"number": "03",
			"icon": "terminal",
			"title": "Custom Frappe apps",
			"meta_label": "Project, by sprint",
			"body": (
				"The app your process actually needs, built against a BenchPress lab so every "
				"review runs on a real site with your app set and your version."
			),
			"includes": [
				"A lab template pinned to the versions you run",
				"The app, its tests and its documentation",
				"A review at the end of each sprint, on a live environment you can open",
			],
			"excludes": "Not hosting the result. Deploy it wherever your production lives.",
			"needs": "Whoever owns the process, available for one review per sprint.",
		},
		{
			"number": "04",
			"icon": "layout-template",
			"title": "Team training",
			"meta_label": "Half a day, remote or on-site",
			"body": (
				"So the next new joiner onboards themselves, and nobody senior is the "
				"environment help desk any more."
			),
			"includes": [
				"Labs and templates: defining a stack once and handing it out",
				"The deploy pipeline, and reading the step that failed",
				"The VPN, devices and the browser VS Code session",
				"What to do when a build dies, and where the logs are",
			],
			"excludes": "Not a Frappe development course. This is the environment, not the framework.",
			"needs": "The team, half a day, and one host they can all reach.",
		},
	],
	"how_title": "How an engagement starts",
	"how_steps": [
		{
			"number": "1",
			"title": "A 20-minute call",
			"body": (
				"Team size, the server you have, and what breaks today. No deck, and no obligation "
				"to buy anything."
			),
		},
		{
			"number": "2",
			"title": "A scope in writing",
			"body": (
				"What is included, what is not, and what we need from you — the three things every "
				"engagement above already names. If we think you should do it yourself, we say so."
			),
		},
		{
			"number": "3",
			"title": "The work, then a handover",
			"body": (
				"Fixed scope for a setup, by sprint for app work, monthly for hosting. Every "
				"engagement ends with the credentials, the documentation and a working deploy in "
				"your hands."
			),
		},
	],
	"closing_title": "Tell us what breaks today.",
	"closing_body": (
		"Requests are read by a person, not a queue. Say the team size, the server you have and "
		"what is costing you afternoons, and we will say plainly whether you need us at all."
	),
	"closing_cta_label": "Book a 20-minute call",
	"closing_cta_url": "/contact",
	"closing_cta2_label": "Read the install guide",
	"closing_cta2_url": DOCS_INSTALL_ROUTE,
	"meta_title": "Services — managed hosting, setup, app work and training for BenchPress",
	"meta_description": (
		"Four engagements for teams running BenchPress: managed hosting, setup on your server, "
		"custom Frappe apps and half-day training. What each includes, and what it does not."
	),
	"og_image": "",
}


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.bp_canonical = canonical_url(SERVICES_ROUTE)
	context.body_class = "bp-body"
	context.mode_default = "dark"

	context.settings = SERVICES_SEED
	context.update(chrome_content())

	context.title = SERVICES_SEED["meta_title"]
	context.metatags = preview_tags(context.title, SERVICES_SEED["meta_description"])
	context.bp_schema = structured_data.services(SERVICES_SEED["meta_description"])
	return context
