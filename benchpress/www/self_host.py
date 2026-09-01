# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from benchpress import structured_data
from benchpress.benchpress.site_content import (
	DOCS_INSTALL_ROUTE,
	DOCS_PREREQ_ROUTE,
	INSTALL_COMMANDS,
	REPO_URL,
	SELF_HOST_ROUTE,
	SETUP_COMMAND,
	VS_FRAPPE_DOCKER_ROUTE,
	canonical_url,
	chrome_content,
	preview_tags,
)
from benchpress.public_site import require_public_site

DEFAULT_TITLE = "Self-host BenchPress"

no_cache = 1
sitemap = 1

SELF_HOST_SEED = {
	"eyebrow": "Self-hosted",
	"title": "Run BenchPress on your own server.",
	"lede": (
		"<p>One install, on one Linux box, for the whole team. Every environment is a Docker "
		"container on your host, reachable on your own WireGuard network. No account, no "
		"telemetry, no ceiling on labs, and no bill — it is AGPL-3.0.</p>"
	),
	"cta_label": "Read the install guide",
	"cta_url": DOCS_INSTALL_ROUTE,
	"cta2_label": "Read the repo",
	"cta2_url": REPO_URL,
	"compare_label": "Still comparing? BenchPress and frappe_docker",
	"compare_url": VS_FRAPPE_DOCKER_ROUTE,
	# The README leads with this and so does the page. A reader who finds it out later is
	# entitled to be angry.
	"warn_title": "Read this first",
	"warn_body": (
		"<p>BenchPress is alpha. A lab user holds root inside their own bench, and without a "
		"user-namespace boundary that is root on the host — so <code>setup.sh</code> checks for "
		"<code>sysbox-runc</code> or Docker <code>userns-remap</code> before anything else. Put "
		"this on a development box or a VM you can rebuild. Never on a workstation, and never "
		"on a host that carries production.</p>"
	),
	"reqs_title": "What you need before you start",
	"reqs_note_label": "The preconditions and the measured sizing, in full",
	"reqs_note_url": DOCS_PREREQ_ROUTE,
	"reqs_lede": (
		"<p>Six things, and none of them can be fixed from inside the app. Each one blocks the "
		"install or the first deploy.</p>"
	),
	"req_cards": [
		{
			"icon": "server",
			"title": "A Linux host",
			"body": (
				"The setup script uses apt and sysctl. There is no macOS or Windows build, and a "
				"laptop is the wrong machine for it."
			),
		},
		{
			"icon": "terminal",
			"title": "A Frappe v16 bench",
			"body": (
				"BenchPress installs into a bench you already run and drives that host's Docker. "
				"It is not a standalone service. Python 3.14+, Node 24, Docker 20+."
			),
		},
		{
			"icon": "shield",
			"title": "A container privilege boundary",
			"body": (
				"sysbox-runc registered with Docker, or userns-remap. Without one, root inside a "
				"bench is root on the host."
			),
		},
		{
			"icon": "lock",
			"title": "IP forwarding on",
			"body": (
				"net.ipv4.ip_forward = 1, or the kernel drops tunnel traffic on its way to a "
				"bench and the deploy fails on the network step."
			),
		},
		{
			"icon": "users",
			"title": "44556/UDP open",
			"body": (
				"On ufw and on any cloud firewall or security group in front of the host. ufw "
				"cannot see that layer, and a WireGuard peer never handshakes without it."
			),
		},
		{
			"icon": "clock",
			"title": "A domain you control",
			"body": (
				"Sites are addressed as <instance>.<base domain>, and base_domain is the one "
				"required field on the settings form."
			),
		},
	],
	"sizing_title": "Size the host before you buy it",
	"sizing_lede": (
		"<p>Disk is the constraint, not CPU. These are measured on the host that runs this "
		"site, not estimated — a 20 GB or 40 GB VPS root disk fails in the middle of an image "
		"build, which is the worst place to find out.</p>"
	),
	"sizing_stats": [
		{"value": "100 GB", "label": "Free disk for one lab image, with room to rebuild it"},
		{"value": "250 GB", "label": "For a catalog the size of this host's — twelve images, 54.74 GB"},
		{"value": "5.5-19.7 GB", "label": "Per lab image, smallest to largest measured"},
		{"value": "1 core", "label": "Per bench, the enforced floor. Measured need was half that"},
	],
	"install_title": "The install, in six steps",
	"install_lede": (
		"<p>Two of them are commands. The guide has all six, with the output each one prints "
		"and the error it raises when a precondition is missing.</p>"
	),
	"install_steps": [
		{
			"number": "1",
			"title": "Install both apps into the bench",
			"body": (
				"There are two repositories and you clone both. BenchPress names vpn_management "
				"in required_apps, but bench resolves a bare name under the frappe and erpnext "
				"accounts only — so it will not find it for you."
			),
			"command": INSTALL_COMMANDS,
		},
		{
			"number": "2",
			"title": "Run the setup script",
			"body": (
				"It is idempotent, so a second run reports what is already correct and changes "
				"nothing. Four steps: the docker group, the privilege boundary, the shared "
				"MariaDB and Redis containers, and IP forwarding. --strict exits rather than "
				"warning when there is no boundary."
			),
			"command": SETUP_COMMAND,
		},
		{
			"number": "3",
			"title": "Finish in the guide",
			"body": (
				"Build the frontend, open 44556/UDP, set your base domain in Settings, and open "
				"the dashboard. Then run the app's own diagnostics — twelve read-only checks that "
				"ask Docker, MariaDB and the kernel what is true instead of reading the config."
			),
			"command": "",
		},
	],
	"next_title": "What happens after it is running",
	"next_cards": [
		{
			"icon": "eye",
			"title": "The first screen is the Overview",
			"body": (
				"How many environments are running, stopped or broken, the average deploy time "
				"over the last seven days, and twelve infrastructure checks. Seven days is not a "
				"setting: deploy logs are cleared on that schedule."
			),
		},
		{
			"icon": "terminal",
			"title": "The first deploy builds an image",
			"body": (
				"An uncached template takes tens of minutes and several gigabytes the first time. "
				"Every deploy after it restores from that image — 51 seconds on average across "
				"50 runs on the host that serves this page."
			),
		},
		{
			"icon": "shield",
			"title": "A teammate gets a key, not a port",
			"body": (
				"They register a device, import the WireGuard config, and reach the site and the "
				"browser VS Code session over the tunnel. One key per device, revocable in a "
				"click. Nothing is published to the internet."
			),
		},
	],
	"breaks_title": "What breaks, and what it means",
	"breaks_lede": (
		"<p>The six failures a first install actually hits. Every one of them has a named cause, "
		"which is the point of writing them down.</p>"
	),
	"breaks": [
		{
			"symptom": "install-app fails with an empty InvalidRemoteException",
			"meaning": (
				"vpn_management was never cloned. Frappe looked for it under the frappe and "
				"erpnext accounts, gave up there, and never reported a missing app. Run the first "
				"get-app, then install-app again."
			),
		},
		{
			"symptom": "The dashboard is blank or unstyled",
			"meaning": "The frontend was never built. Build it, then clear the site cache.",
		},
		{
			"symptom": "Settings will not save",
			"meaning": "base_domain is empty, and it is required. Sites are addressed under it.",
		},
		{
			"symptom": "Every deploy fails on a Docker call",
			"meaning": (
				"The bench started before the docker group change took effect. Log out, log back "
				"in, restart the bench."
			),
		},
		{
			"symptom": "setup.sh warns that there is no privilege boundary",
			"meaning": (
				"Neither sysbox-runc nor userns-remap is present, so container root is host root. "
				"Read Production safety before running anything you care about."
			),
		},
		{
			"symptom": "A build dies partway through",
			"meaning": (
				"The disk filled. A build holds the new image while its base layers are still "
				"there, so the floor is higher than one image."
			),
		},
	],
	"breaks_note_label": "Every symptom, cause and fix",
	"breaks_note_url": DOCS_INSTALL_ROUTE,
	"closing_title": "Or have us do it.",
	"closing_body": (
		"The install is documented because it should be possible without us. When you would "
		"rather it were done in an afternoon by someone who has done it before, that is a "
		"fixed-scope engagement — and the hosted build is the same repository with billing "
		"attached, if you would rather not run a server at all."
	),
	"closing_cta_label": "Read the install guide",
	"closing_cta_url": DOCS_INSTALL_ROUTE,
	"closing_cta2_label": "Have us install it",
	"closing_cta2_url": "/#services",
	"meta_title": "Self-host BenchPress — Frappe dev environments on your own server",
	"meta_description": (
		"What it takes to run BenchPress yourself: the six preconditions, the real install "
		"commands, the measured disk floor, and the six things that break on a first install."
	),
	"og_image": "",
}


def get_context(context):
	require_public_site()

	context.no_cache = 1
	context.bp_canonical = canonical_url(SELF_HOST_ROUTE)
	context.body_class = "bp-body"
	context.mode_default = "dark"

	# Only `settings`, never a bare update: the seed carries a `title` of its own and the
	# framework reads `context.title` for the document title.
	context.settings = SELF_HOST_SEED
	context.update(chrome_content())

	context.title = SELF_HOST_SEED["meta_title"]
	context.metatags = preview_tags(context.title, SELF_HOST_SEED["meta_description"])
	context.bp_schema = structured_data.self_host(SELF_HOST_SEED["meta_description"])
	return context
