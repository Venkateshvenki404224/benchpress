# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The read side of the public site: the shipped copy, shaped the way each template reads it."""

import frappe
from frappe.utils import cint

from benchpress.credits.config import SIGNUP_ROUTE, credits_enabled, waitlist_open
from benchpress.request_cache import clear_local_cache, local_cache

LANDING_ATTRIBUTE = "benchpress_landing_content"
ABOUT_ATTRIBUTE = "benchpress_about_content"

REPO_URL = "https://github.com/Venkateshvenki404224/benchpress"

# The branded access-request page; `SIGNUP_ROUTE` is Frappe's own login page. Never both open.
WAITLIST_ROUTE = "/signup"

# A nav CTA aimed at either follows the switch; one aimed anywhere else is left alone.
SIGNUP_DOORS = (WAITLIST_ROUTE, SIGNUP_ROUTE)

LOGIN_ROUTE = "/login"
CONSOLE_ROUTE = "/frontend"

# Both logout endpoints are POST-only, so the header signs out through a form, not a link.
LOGOUT_METHOD = "frappe.handler.web_logout"

WITHOUT_COLUMN = "Without BenchPress"
WITH_COLUMN = "With BenchPress"

SITE_NAME = "BenchPress"
OG_TYPE = "website"

DEFAULT_OG_IMAGE = "/assets/benchpress/images/logo/mark.png"


def landing_content() -> dict:
	"""Everything `www/index.html` renders, assembled once per request."""
	return local_cache(LANDING_ATTRIBUTE, build_landing_content)


def about_content() -> dict:
	"""Everything `www/about.html` renders, assembled once per request."""
	return local_cache(ABOUT_ATTRIBUTE, build_about_content)


def chrome_content() -> dict:
	"""Header and footer copy for any public page. All five pages share one source."""
	landing = landing_content()
	route = signup_route()
	return {
		"nav_items": nav_items(landing["nav_items"], landing["settings"], route),
		"signup_route": route,
		"footer_columns": landing["footer_columns"],
		"footer_tagline": landing["settings"].footer_tagline,
		"footer_copyright": landing["settings"].footer_copyright,
		"footer_trademark": landing["settings"].footer_trademark,
		"repo_url": REPO_URL,
		"is_signed_in": frappe.session.user != "Guest",
		"login_route": LOGIN_ROUTE,
		"console_route": CONSOLE_ROUTE,
		"logout_method": LOGOUT_METHOD,
		"csrf_token": session_csrf_token(),
	}


def preview_tags(title: str, description: str, image: str = "") -> dict:
	"""`context.metatags`; the framework derives the og: and twitter: pairs and absolutises the image."""
	return {
		"og:type": OG_TYPE,
		"og:site_name": SITE_NAME,
		"title": title,
		"description": description,
		"image": image or DEFAULT_OG_IMAGE,
	}


def session_csrf_token() -> str:
	"""The token the header's sign-out form posts. Empty when there is nothing to protect."""
	# Guests are exempt from CSRF, and outside a request there is no session object to mint from.
	if frappe.session.user == "Guest" or not getattr(frappe.local, "session_obj", None):
		return ""
	return frappe.sessions.get_csrf_token()


def signup_route() -> str:
	"""The one hosted front door, resolved once."""
	return WAITLIST_ROUTE if credits_enabled() and waitlist_open() else SIGNUP_ROUTE


def nav_items(items: list, settings, route: str) -> list:
	"""The header's link rows, with the CTA pointed at whichever door is actually open."""
	if not credits_enabled():
		return [*(row for row in items if not cint(row.is_cta)), selfhost_cta(settings)]
	return [repointed(row, route) if cint(row.is_cta) else row for row in items]


def repointed(row, route: str):
	"""One nav row, aimed at `route` if it points at either signup door."""
	if row.anchor not in SIGNUP_DOORS:
		return row
	return frappe._dict({**row, "anchor": route})


def selfhost_cta(settings):
	"""The header CTA when credits are off: there is no hosted account to sign up for."""
	return frappe._dict(
		{
			"label": settings.paths_self_cta_label or "Read the repo",
			"anchor": settings.paths_self_cta_url or REPO_URL,
			"is_cta": 1,
		}
	)


def clear_content_cache() -> None:
	"""Drop the request-scoped assembly."""
	clear_local_cache(LANDING_ATTRIBUTE)
	clear_local_cache(ABOUT_ATTRIBUTE)


def build_landing_content() -> dict:
	settings = shipped(LANDING_SEED)
	for card in settings.service_cards:
		card.meta = card.meta_label
	return {
		"settings": settings,
		"nav_items": settings.nav_items,
		"phases": group_steps(settings.pipeline_phases, settings.pipeline_steps),
		"default_phase": default_phase(settings),
		"hosted_points": [row for row in settings.path_points if row.path != "Self-hosted"],
		"self_points": [row for row in settings.path_points if row.path == "Self-hosted"],
		"footer_columns": group_footer_links(settings.footer_links),
		"meta_title": settings.meta_title,
		"meta_description": settings.meta_description,
		"og_image": settings.og_image,
		"repo_url": REPO_URL,
	}


def build_about_content() -> dict:
	settings = shipped(ABOUT_SEED)
	return {
		"settings": settings,
		"days_without": [row for row in settings.day_entries if row.column != WITH_COLUMN],
		"days_with": [row for row in settings.day_entries if row.column == WITH_COLUMN],
		"stats": settings.stats,
		"principles": settings.principles,
		"timeline": settings.timeline,
		"contrast_rows": settings.contrast_rows,
		"meta_title": settings.meta_title,
		"meta_description": settings.meta_description,
		"og_image": settings.og_image,
		"repo_url": REPO_URL,
	}


def shipped(seed: dict) -> frappe._dict:
	"""One page's copy, as its template reads it."""
	return frappe._dict(
		{key: detach(value) if isinstance(value, list) else value for key, value in seed.items()}
	)


def detach(rows) -> list[frappe._dict]:
	"""Rows a caller may edit without reaching the constant behind them."""
	return [frappe._dict(row) for row in rows]


def group_steps(phases, steps) -> list[dict]:
	"""Each phase carrying its own steps, in step order."""
	by_phase: dict[str, list] = {}
	for step in sorted(steps, key=lambda row: cint(row.step_number)):
		by_phase.setdefault(phase_key(step), []).append(step)
	return [
		{
			"phase_key": phase.phase_key,
			"label": phase.label,
			"step_range": phase.step_range,
			"summary": phase.summary,
			"timing": phase.timing,
			"nodes": split_keys(phase.plane_nodes),
			"chips": split_keys(phase.plane_chips),
			"steps": by_phase.get(phase_key(phase), []),
		}
		for phase in phases
	]


def default_phase(settings) -> str:
	"""The phase open on load, falling back to the first."""
	keys = [phase_key(phase) for phase in settings.pipeline_phases]
	chosen = (settings.pipeline_default_phase or "").strip()
	return chosen if chosen in keys else (keys[0] if keys else "")


def group_footer_links(links) -> list[dict]:
	"""Footer links grouped by heading, first-seen order preserved."""
	columns: dict[str, list] = {}
	for link in links:
		columns.setdefault(link.column_heading, []).append({"label": link.label, "url": link.url})
	return [{"heading": heading, "links": items} for heading, items in columns.items()]


def split_keys(value) -> list[str]:
	"""`device,control` → `["device", "control"]`."""
	return [part.strip() for part in (value or "").split(",") if part.strip()]


def phase_key(row) -> str:
	return (row.phase_key or "").strip()


# The shipped copy: the only thing any public page renders.

HERO_SUBHEAD = (
	"Pick a version and an app set. Press deploy. BenchPress builds an isolated Docker "
	"environment with its own site, database and browser VS Code, and puts it on your "
	"private WireGuard mesh. No bench commands, no SSH, no ticket to the one person who knows."
)

FOOTER_TRADEMARK = (
	"Frappe, ERPNext and Frappe HR are trademarks of Frappe Technologies Pvt. Ltd. "
	"BenchPress is an independent project, not affiliated with or endorsed by Frappe Technologies."
)

APP_ICONS = "/assets/benchpress/images/app-icons"

LANDING_SEED = {
	# hero
	"hero_badge_text": "Open source, AGPL-3.0",
	"hero_badge_version": "v16",
	"hero_headline": "A Frappe environment in the time it takes to read this line.",
	"hero_headline_accent": "read this line.",
	"hero_subhead": HERO_SUBHEAD,
	"hero_cta_primary_label": "Start free",
	"hero_cta_primary_url": "/signup",
	"hero_cta_secondary_label": "Self-host it instead",
	"hero_cta_secondary_url": "#paths",
	"hero_assurances": [
		{"label": "No card required"},
		{"label": "Bring your own server"},
		{"label": "Failed builds are free"},
	],
	# templates marquee
	"templates_eyebrow": "Templates",
	"template_cards": [
		{"app_name": "ERPNext v15", "build_time": "~90s", "icon": f"{APP_ICONS}/erpnext.svg"},
		{"app_name": "Frappe HR", "build_time": "~2m", "icon": f"{APP_ICONS}/hrms.svg"},
		{"app_name": "Frappe CRM", "build_time": "~60s", "icon": f"{APP_ICONS}/crm.svg"},
		{"app_name": "Helpdesk", "build_time": "~75s", "icon": f"{APP_ICONS}/helpdesk.svg"},
		{"app_name": "Frappe Learning", "build_time": "~90s", "icon": f"{APP_ICONS}/lms.svg"},
		{"app_name": "Custom image", "build_time": "build once", "icon": f"{APP_ICONS}/frappe.svg"},
	],
	# paths
	"paths_hosted_eyebrow": "Hosted",
	"paths_hosted_badge": "Fastest way in",
	"paths_hosted_title": "You want a site, not a server.",
	"paths_hosted_body": (
		"Sign in, deploy a lab, get the URL and the IDE link. We run the host, the mesh and "
		"the upgrades. No card, no commitment."
	),
	"paths_hosted_cta_label": "Start free",
	"paths_hosted_cta_url": "/signup",
	"paths_hosted_cta2_label": "Talk to us",
	"paths_hosted_cta2_url": "/contact",
	"paths_self_eyebrow": "Self-hosted",
	"paths_self_title": "You already have the server.",
	"paths_self_body": (
		"Clone it, point it at your Docker daemon, keep every container and credential "
		"in-house. No account, no telemetry, no ceiling on labs."
	),
	"paths_self_terminal": (
		"$ git clone github.com/Venkateshvenki404224/benchpress\n$ cd benchpress && ./setup.sh"
	),
	"paths_self_cta_label": "Read the repo",
	"paths_self_cta_url": REPO_URL,
	"paths_self_cta2_label": "Have us install it",
	"paths_self_cta2_url": "#services",
	"paths_footnote": "Same code either way — the hosted build is this repo with billing attached.",
	"path_points": [
		{
			"path": "Hosted",
			"point": "Nothing to install — first environment in about 90 seconds",
		},
		{
			"path": "Hosted",
			"point": "WireGuard config issued per device, revocable in one click",
		},
		{"path": "Hosted", "point": "Failed builds and stopped instances cost nothing"},
		{"path": "Self-hosted", "point": "AGPL-3.0"},
		{"path": "Self-hosted", "point": "Docker + WireGuard"},
		{"path": "Self-hosted", "point": "Your data, your host"},
	],
	# bento
	"bento_eyebrow": "What you get",
	"bento_title": "Four things per lab, every time, without anyone typing bench.",
	"bento_body": (
		"A Lab template pins the Frappe version, the app set and the seed data — so the "
		"environment your intern gets is the environment you tested."
	),
	"feature_cards": [
		{
			"title": "Browser VS Code, attached to the container",
			"body": (
				"code-server runs inside the same container as the site, so the file you edit "
				"is the file the site serves. No local bench, no Docker Desktop, no "
				'"works on my machine".'
			),
			"icon": "terminal",
			"span": "Wide",
		},
		{
			"title": "Nothing on the public internet",
			"body": (
				"Every site answers on a WireGuard mesh address, one key per device, revocable in a click."
			),
			"icon": "shield",
			"span": "Standard",
		},
		{
			"title": "Metering you can argue with",
			"body": (
				"Deploys are free. Stopped instances and failed builds are free. Every line "
				"lands in the ledger."
			),
			"icon": "credit-card",
			"span": "Standard",
		},
		{
			"title": "Reusable lab templates",
			"body": (
				"Pin the version, the apps and the branches once. Build a custom image from "
				"your own repo and deploy from it forever."
			),
			"icon": "layout-template",
			"span": "Standard",
		},
		{
			"title": "Disposable on purpose",
			"body": (
				"Remove the environment when the work is done. The confirmation tells you "
				"exactly what gets destroyed — container, site, databases — before you type "
				"the name."
			),
			"icon": "trash-2",
			"span": "Standard",
		},
	],
	# pipeline
	"pipeline_eyebrow": "The pipeline",
	"pipeline_title": "One click, four phases, eleven steps.",
	"pipeline_body": (
		"BenchPress is a control plane, not a host. It talks to a Docker daemon — ours or "
		"yours — runs the bench commands you would have typed, and hands the result to the mesh."
	),
	"pipeline_default_phase": "site",
	"pipeline_phases": [
		{
			"phase_key": "request",
			"label": "Request",
			"step_range": "1-2",
			"summary": (
				"BenchPress checks the plan, confirms the balance and reserves room on the "
				"host before anything is pulled."
			),
			"timing": ("Under a second — deploying is free; nothing is metered until the container runs."),
			"plane_nodes": "device,control",
			"plane_chips": "api,queue,ledger",
		},
		{
			"phase_key": "image",
			"label": "Image",
			"step_range": "3-4",
			"summary": (
				"The app list becomes a layer. Templates reuse a cached image; a custom lab "
				"builds one once and keeps it."
			),
			"timing": "Cached template: ~10s. First custom build: 3-6 minutes.",
			"plane_nodes": "control,host",
			"plane_chips": "queue",
		},
		{
			"phase_key": "site",
			"label": "Site",
			"step_range": "5-8",
			"summary": (
				"The container comes up and BenchPress runs the exact bench commands you "
				"would have typed, in order."
			),
			"timing": "Roughly 60-120 seconds depending on the app set.",
			"plane_nodes": "host",
			"plane_chips": "",
		},
		{
			"phase_key": "network",
			"label": "Network",
			"step_range": "9-11",
			"summary": (
				"The environment joins the mesh, gets health-checked, and only then are the "
				"credentials handed over and the meter started."
			),
			"timing": "5-10 seconds, then the environment is yours.",
			"plane_nodes": "host,mesh,device",
			"plane_chips": "ledger",
		},
	],
	"pipeline_steps": [
		{
			"phase_key": "request",
			"step_number": 1,
			"title": "Reserve a container slot",
			"detail": (
				"The API validates the template, checks concurrency against your plan and "
				"reserves CPU, memory and a site name on the target host."
			),
			"command": 'POST /api/method/benchpress.deploy\n{ "template": "erpnext-v15" }',
		},
		{
			"phase_key": "request",
			"step_number": 2,
			"title": "Check the balance",
			"detail": (
				"Deploying costs nothing. BenchPress confirms the account can cover the first "
				"hour of runtime and that you are inside your concurrency cap."
			),
			"command": 'credits.check(user="you@example.com", size="Small")',
		},
		{
			"phase_key": "image",
			"step_number": 3,
			"title": "Resolve the app list",
			"detail": (
				"Frappe version, apps and branches are pinned into an apps.json — the same "
				"file a manual bench build would use."
			),
			"command": "apps.json\n  frappe@version-16\n  erpnext@version-15",
		},
		{
			"phase_key": "image",
			"step_number": 4,
			"title": "Pull or build the image",
			"detail": (
				"A matching layer is pulled from the registry. Custom labs run a real image "
				"build, and its log is streamed into Deploy history line by line."
			),
			"command": "docker build --build-arg APPS_JSON_BASE64=…\n  -t bp/erpnext-v15 .",
		},
		{
			"phase_key": "site",
			"step_number": 5,
			"title": "Start the container and services",
			"detail": (
				"The bench container starts alongside MariaDB, Redis and code-server, with "
				"the sites directory on a named volume so data survives a restart."
			),
			"command": "docker run -v bp_sites:/home/frappe/…/sites",
		},
		{
			"phase_key": "site",
			"step_number": 6,
			"title": "Create the site",
			"detail": (
				"A fresh site is created with a generated administrator password, stored "
				"encrypted and revealed only to you."
			),
			"command": "bench new-site erpnext-demo.bp.local\n  --admin-password ****",
		},
		{
			"phase_key": "site",
			"step_number": 7,
			"title": "Install apps and migrate",
			"detail": (
				"Every app in the template is installed, then migrations run. This is the "
				"step that fails loudest, so its output is kept verbatim."
			),
			"command": ("bench --site erpnext-demo.bp.local install-app erpnext\nbench migrate"),
		},
		{
			"phase_key": "site",
			"step_number": 8,
			"title": "Build assets",
			"detail": (
				"Frontend bundles are built inside the container and served by its own nginx "
				"— no shared asset host to drift out of sync."
			),
			"command": "bench build --production",
		},
		{
			"phase_key": "network",
			"step_number": 9,
			"title": "Attach the WireGuard route",
			"detail": (
				"The container is given a mesh address and a peer entry per registered "
				"device. Nothing is bound to a public interface."
			),
			"command": "wg set wg0 peer <pubkey>\n  allowed-ips 10.13.13.24/32",
		},
		{
			"phase_key": "network",
			"step_number": 10,
			"title": "Health check",
			"detail": (
				"BenchPress fetches the site over the mesh until it answers. If it never "
				"does, the run is marked failed and the container is torn down."
			),
			"command": "GET /api/method/ping → pong",
		},
		{
			"phase_key": "network",
			"step_number": 11,
			"title": "Hand over credentials",
			"detail": (
				"Site URL, mesh IP, code-server link and passwords appear on the lab page. "
				"The hourly meter starts at this point, and only this point."
			),
			"command": 'ledger.start(lab="erpnext-demo", size="Small")',
		},
	],
	"pipeline_failure_title": "If a step fails",
	"pipeline_failure_body": (
		"the run stops at that step, the container is discarded, and nothing is metered — a "
		"failed run costs nothing."
	),
	# console
	"console_eyebrow": "The console",
	"console_title": "Status you can read at a glance.",
	"console_body": (
		"Bench status and container health are separate columns, because they fail "
		"separately. Deploy history keeps every log line. Devices shows who is on the mesh."
	),
	"console_callouts": [
		{
			"title": "Secrets stay hidden",
			"body": (
				"Administrator passwords are stored encrypted and revealed once, to you, behind a click."
			),
			"icon": "eye-off",
		},
		{
			"title": "Elapsed time per step",
			"body": ("You can see which step is slow, and the exact failing command when a build breaks."),
			"icon": "timer",
		},
		{
			"title": "Role-aware",
			"body": (
				"Users see instances and deploy. Admins get templates, build logs, devices and billing."
			),
			"icon": "users",
		},
	],
	# agents
	"agents_eyebrow": "For AI coding agents",
	"agents_title": "Disposable environments, spawned by API.",
	"agents_body": (
		"Everything the console does is an endpoint. An agent asks for a fresh ERPNext "
		"environment, runs against it, reads the logs and tears it down — inside the mesh, "
		"with a credit ceiling so a runaway loop can't run up a bill."
	),
	"agents_badge": "202 accepted",
	"agents_footnote": "ttl_minutes and credit_ceiling are both enforced server-side.",
	"agent_points": [
		{"icon": "bot", "text": "One container per agent run — no shared state"},
		{"icon": "terminal", "text": "Logs and bench output returned as JSON"},
		{"icon": "lock", "text": "Scoped tokens, per-key credit limits, auto-expiry"},
	],
	"agent_api_examples": [
		{
			"tab_label": "deploy",
			"code": (
				"POST /api/method/benchpress.deploy\n"
				"{\n"
				'  "template": "erpnext-v15",\n'
				'  "name": "agent-run-4821",\n'
				'  "ttl_minutes": 30,\n'
				'  "credit_ceiling": 20\n'
				"}\n"
				"\n"
				"→ 202 {\n"
				'  "instance": "agent-run-4821",\n'
				'  "status": "deploying",\n'
				'  "url":  "https://agent-run-4821.vpn",\n'
				'  "ide":  "https://agent-run-4821.vpn:8443",\n'
				'  "logs": "/api/.../BLD-26-242"\n'
				"}"
			),
		},
		{
			"tab_label": "logs",
			"code": (
				"GET /api/method/benchpress.logs?run=BLD-26-242\n"
				"\n"
				"→ 200 {\n"
				'  "step": 7,\n'
				'  "title": "Install apps and migrate",\n'
				'  "elapsed": "1m 45s",\n'
				'  "lines": [\n'
				'    "Installing app erpnext...",\n'
				'    "Updating DocTypes for erpnext : 100%",\n'
				'    "$ bench build --production"\n'
				"  ]\n"
				"}"
			),
		},
		{
			"tab_label": "destroy",
			"code": (
				"DELETE /api/method/benchpress.instance\n"
				'{ "instance": "agent-run-4821" }\n'
				"\n"
				"→ 200 {\n"
				'  "destroyed": true,\n'
				'  "container": "removed",\n'
				'  "databases": "dropped",\n'
				'  "credits_charged": 6\n'
				"}"
			),
		},
	],
	# compare
	"compare_eyebrow": "Versus doing it by hand",
	"compare_title": "The same environment, minus the afternoon.",
	"compare_col_manual": "Manual bench",
	"compare_col_bp": "BenchPress",
	"compare_col_bp_badge": "One click",
	"comparison_rows": [
		{
			"aspect": "New environment",
			"manual": "30–90 min, SSH required",  # noqa: RUF001 -- en dash is verbatim spec copy
			"benchpress": "One click, ~90 seconds",
		},
		{
			"aspect": "Who can do it",
			"manual": "Someone who knows bench",
			"benchpress": "Anyone on the team",
		},
		{
			"aspect": "An intern's first day",
			"manual": "A morning of setup calls",
			"benchpress": "A link and a password",
		},
		{
			"aspect": "When it breaks",
			"manual": "Scroll the terminal, guess",
			"benchpress": "Named failing step, then rebuild",
		},
		{
			"aspect": "Access",
			"manual": "Open a port, hope",
			"benchpress": "Mesh-only, per-device keys",
		},
		{
			"aspect": "Automation",
			"manual": "Shell scripts you maintain",
			"benchpress": "HTTP API with credit ceilings",
		},
	],
	# services
	"services_eyebrow": "Done for you",
	"services_title": "The software is free. The afternoons are what we sell.",
	"services_body": (
		"Run BenchPress yourself and it costs nothing but a server. When you would rather "
		"hand it over, these are the four things we do."
	),
	"service_cards": [
		{
			"number": "01",
			"icon": "server",
			"title": "Managed hosting",
			"body": (
				"We run the host, the mesh and the upgrades. You get a console, a credit "
				"balance and someone to call."
			),
			"meta_label": "Hosted · monthly",
		},
		{
			"number": "02",
			"icon": "hammer",
			"title": "Setup on your server",
			"body": (
				"One engagement: BenchPress installed on your machine, WireGuard configured, "
				"templates seeded, keys handed over."
			),
			"meta_label": "One-time · fixed scope",
		},
		{
			"number": "03",
			"icon": "terminal",
			"title": "Custom Frappe apps",
			"body": (
				"The app your process actually needs, built against a BenchPress lab so every "
				"review runs on a real site."
			),
			"meta_label": "Project · by sprint",
		},
		{
			"number": "04",
			"icon": "layout-template",
			"title": "Team training",
			"body": (
				"Half a day on bench, labs and the deploy pipeline, so the next new joiner "
				"onboards themselves."
			),
			"meta_label": "Remote or on-site",
		},
	],
	"services_cta_title": "Not sure which door is yours?",
	"services_cta_body": (
		"Tell us the team size, the server you have and what breaks today. We will say "
		"plainly whether you need us at all."
	),
	"services_cta_label": "Book a 20-minute call",
	"services_cta_url": "/contact",
	# about — a teaser for `/about`; the numbers below it come from `ABOUT_SEED`.
	"about_eyebrow": "About",
	"about_title": "We built this because onboarding cost us half a day, every time.",
	"about_body": (
		"Frappe's own tooling creates a bench well enough. Our problem started after that: "
		"every new developer, and every client stack they moved between, meant matching "
		"versions and wiring apps by hand. BenchPress is that half-day, spent once."
	),
	"about_link_label": "Read the full story",
	"about_link_url": "/about",
	# faq
	"faq_title": "Questions",
	"faq_items": [
		{
			"question": "Do I need to know bench or Docker?",
			"answer": (
				"No. Deploying a template needs a name and a click. Bench commands only show "
				"up in the log, and only if you expand it."
			),
			"default_open": 1,
		},
		{
			"question": "What is the difference between hosted and self-hosted?",
			"answer": (
				"The code — there isn't any. The hosted build is this repo with billing "
				"attached. Hosted means we run the server, the mesh and the upgrades; "
				"self-hosted means you do, for free, forever."
			),
			"default_open": 0,
		},
		{
			"question": "Where do the environments actually run?",
			"answer": (
				"As Docker containers on a server — ours on the hosted build, or one you "
				"connect: your VPS, your bare metal, a machine in the office. BenchPress "
				"orchestrates; it doesn't hold your data."
			),
			"default_open": 0,
		},
		{
			"question": "Can an agent spin environments up and down on its own?",
			"answer": (
				"Yes. Issue a scoped API key with a credit ceiling and a TTL. The agent "
				"deploys, works, reads logs and destroys the instance; the ceiling stops a "
				"runaway loop."
			),
			"default_open": 0,
		},
		{
			"question": "What happens to credits if a build fails?",
			"answer": (
				"Nothing is charged. Failed builds and stopped instances are free; the ledger "
				"in Settings shows every line so you can check."
			),
			"default_open": 0,
		},
		{
			"question": "Is the VPN optional?",
			"answer": (
				"On the hosted build, no — it's the access path. Self-hosted, you can expose "
				"sites yourself, but the default assumes private."
			),
			"default_open": 0,
		},
	],
	# closing cta
	"cta_title": ("Create a Frappe environment, press deploy, get a working site and a VS Code window."),
	"cta_primary_label": "Start free",
	"cta_primary_url": "/signup",
	"cta_secondary_label": "Clone the repo",
	"cta_secondary_url": REPO_URL,
	"cta_footnote": (
		"GitHub sign-in is one click and needs no email verification. Self-hosting needs no account at all."
	),
	# chrome
	"nav_items": [
		{"label": "Hosted or self-host", "anchor": "/#paths", "is_cta": 0},
		{"label": "Pipeline", "anchor": "/#how", "is_cta": 0},
		{"label": "Console", "anchor": "/#console", "is_cta": 0},
		{"label": "Agents", "anchor": "/#agents", "is_cta": 0},
		{"label": "Services", "anchor": "/#services", "is_cta": 0},
		{"label": "About", "anchor": "/about", "is_cta": 0},
		{"label": "Contact", "anchor": "/contact", "is_cta": 0},
		{"label": "Start free", "anchor": "/signup", "is_cta": 1},
	],
	"footer_tagline": (
		"Isolated Frappe environments, deployed in one click and kept on your private network."
	),
	"footer_links": [
		{"column_heading": "Product", "label": "Pipeline", "url": "/#how"},
		{"column_heading": "Product", "label": "Console", "url": "/#console"},
		{"column_heading": "Product", "label": "Templates", "url": "/#top"},
		{"column_heading": "Developers", "label": "Agent API", "url": "/#agents"},
		{"column_heading": "Developers", "label": "Self-hosting guide", "url": "/#paths"},
		{"column_heading": "Developers", "label": "GitHub", "url": REPO_URL},
		{"column_heading": "Services", "label": "Managed hosting", "url": "/#services"},
		{"column_heading": "Services", "label": "Setup on your server", "url": "/#services"},
		{"column_heading": "Services", "label": "App development", "url": "/#services"},
		{"column_heading": "Services", "label": "Training", "url": "/#services"},
		{"column_heading": "Company", "label": "About us", "url": "/about"},
		{"column_heading": "Company", "label": "Contact", "url": "/contact"},
		{"column_heading": "Company", "label": "Sign in", "url": LOGIN_ROUTE},
	],
	"footer_copyright": "© 2026 BenchPress. AGPL-3.0 licensed.",
	"footer_trademark": FOOTER_TRADEMARK,
	# seo
	"meta_title": "BenchPress — a Frappe environment in one click",
	"meta_description": HERO_SUBHEAD,
	"og_image": "",
}

ABOUT_SEED = {
	"eyebrow": "About",
	"title": ("A developer joins on Monday. By 9:15 they are working on the client's actual project."),
	"lede": (
		"<p>That sentence is the whole reason BenchPress exists. Not &quot;installing bench "
		"is hard&quot; — Frappe already has good tooling for creating a bench and installing "
		"apps, and if that were our problem we would have simply used it. Our problem started "
		"<i>after</i> the bench existed: every person who joined, and every client they moved "
		"between, needed their own working environment, and somebody senior had to build it "
		"by hand.</p>"
	),
	"situation_eyebrow": "The situation we kept living in",
	"situation_body": (
		"<p>Say you run a 20-person company with four clients — <b>A, B, C and D</b>. Each "
		"one is a different world: a different Frappe version, a different set of apps, "
		"different customisations, different data. You hire a developer to work on client B. "
		"On their first day they need <i>client B's</i> environment — not a generic bench, "
		"not a copy of someone's laptop. The right version, the right apps, the right data, "
		"running and reachable.</p>"
		"<p>Somebody has to build that. In practice it is your most experienced developer, "
		"and it costs them half a day of setup calls, missing branches, port clashes and "
		"&quot;works on mine&quot;. Multiply that by every joiner, every client switch and "
		"every intern who needs a sandbox for two weeks.</p>"
	),
	"days_without_title": "Monday, without BenchPress",
	"days_with_title": "Monday, with BenchPress",
	"day_entries": [
		{
			"column": WITHOUT_COLUMN,
			"time_label": "09:00",
			"text": "New joiner arrives. Nobody has an environment for client B ready.",
		},
		{
			"column": WITHOUT_COLUMN,
			"time_label": "09:20",
			"text": "A senior developer stops their own work to set one up.",
		},
		{
			"column": WITHOUT_COLUMN,
			"time_label": "11:30",
			"text": "Wrong Frappe version, a branch that no longer exists, a port already in use.",
		},
		{
			"column": WITHOUT_COLUMN,
			"time_label": "14:00",
			"text": "Something runs locally. It does not match what the client is on.",
		},
		{
			"column": WITHOUT_COLUMN,
			"time_label": "Day 2",
			"text": "The joiner is still reading setup notes instead of the client's code.",
		},
		{
			"column": WITH_COLUMN,
			"time_label": "09:00",
			"text": "New joiner logs in and sees the labs their team owns.",
		},
		{
			"column": WITH_COLUMN,
			"time_label": "09:01",
			"text": "They click Client B — the template already pins the version, apps and data.",
		},
		{
			"column": WITH_COLUMN,
			"time_label": "09:03",
			"text": "Site is live. Browser VS Code opens on the same container.",
		},
		{
			"column": WITH_COLUMN,
			"time_label": "09:15",
			"text": ("They are reading client B's actual code, on an environment that matches production."),
		},
		{
			"column": WITH_COLUMN,
			"time_label": "Later",
			"text": "Moving them to client D is another click, not another afternoon.",
		},
	],
	"days_closing": (
		"<p>You — the company — host BenchPress once and save a Lab template per client. The "
		"new joiner logs in, clicks <b>Client B</b>, and about a minute later they have a "
		"running site, a browser VS Code window attached to the container, and an address on "
		"the company's private network. Nobody senior was interrupted. Nothing was installed "
		"on their laptop.</p>"
	),
	"contrast_title": "So what is it, exactly — and what is it not?",
	"contrast_lede": (
		"<p>The honest one-liner: BenchPress is an <b>environment-handout system for "
		"teams</b>. Bench creation is a step inside it, not the point of it.</p>"
	),
	"contrast_rows": [
		{
			"not_text": "Not a nicer way to run bench commands on your machine.",
			"is_text": ("A place your team keeps ready-made environments, one per client or project."),
		},
		{
			"not_text": "Not something each developer installs and maintains locally.",
			"is_text": "One install, by you, on one server. Everyone else just clicks.",
		},
		{
			"not_text": "Not a hosting or production platform for client sites.",
			"is_text": (
				"Development and demo environments — disposable on purpose, removed when the work is done."
			),
		},
		{
			"not_text": "Not a laptop-dependent setup that drifts per person.",
			"is_text": (
				"Everyone on a project gets the identical container, so 'works on mine' stops "
				"being a sentence."
			),
		},
		{
			"not_text": "Not open to the internet with ports and proxies to babysit.",
			"is_text": ("Every environment answers on your private WireGuard network, one key per device."),
		},
	],
	"contrast_closing": (
		"<p>It is open source under AGPL-3.0, because a development tool you cannot read is a "
		"development tool you cannot trust. Run it on your own server for free, forever. When "
		"you would rather not run a server, we host it — the same code, with billing "
		"attached.</p>"
	),
	"stats": [
		{"value": "~90s", "label": "From a new joiner's click to a working site and IDE"},
		{"value": "1 install", "label": "On one server, for the whole team — not per laptop"},
		{"value": "0", "label": "Credits charged for a build that fails"},
		{"value": "AGPL-3.0", "label": "Licensed, self-hostable, no telemetry"},
	],
	"principles_title": "What we hold to",
	"principles": [
		{
			"icon": "eye",
			"title": "Show the machine",
			"body": (
				"Every bench command, every log line, every elapsed second is visible. A tool "
				"that hides the terminal cannot be debugged."
			),
		},
		{
			"icon": "shield",
			"title": "Private by default",
			"body": (
				"Environments answer on a WireGuard mesh, not the public internet. Access is a "
				"key per device, revocable in a click."
			),
		},
		{
			"icon": "credit-card",
			"title": "Meter honestly",
			"body": (
				"Deploys are free, stopped instances are free, failed builds are free. "
				"Everything else lands in a ledger you can read."
			),
		},
		{
			"icon": "github",
			"title": "Stay forkable",
			"body": (
				"The hosted product is this repository with billing attached. If we ever stop "
				"being useful, you keep running it yourself."
			),
		},
	],
	"timeline_title": "How it got here",
	"timeline": [
		{
			"period": "2024",
			"title": "An internal script",
			"body": (
				"A shell script that stood up a bench container for whoever joined next. It "
				"broke often and only one person could fix it."
			),
		},
		{
			"period": "2025",
			"title": "A Frappe app",
			"body": (
				"The script became a control plane with a real object model — Lab templates, "
				"Bench Instances, Bench Sites, deploy history."
			),
		},
		{
			"period": "2025",
			"title": "WireGuard and browser VS Code",
			"body": (
				"Access stopped meaning SSH keys and open ports. Every environment got a mesh "
				"address and code-server on :8443."
			),
		},
		{
			"period": "2026",
			"title": "Open sourced, then hosted",
			"body": (
				"Published under AGPL-3.0. The hosted build followed for teams who wanted the "
				"tool without the server."
			),
		},
	],
	"cta_title": "Want the hosted version?",
	"cta_body": "Requests are read by a person, not a queue. Tell us what you plan to run.",
	"cta_label": "Request access",
	"cta_url": "/signup",
	"trademark": (
		"Frappe, ERPNext, Frappe HR, Frappe CRM, Helpdesk and Frappe Learning are trademarks "
		"of Frappe Technologies Pvt. Ltd., used here only to name the software each template "
		"installs. BenchPress is an independent project, not affiliated with, endorsed by or "
		"sponsored by Frappe Technologies."
	),
	"meta_title": "About BenchPress",
	"meta_description": (
		"A developer joins on Monday. By 9:15 they are working on the client's actual "
		"project — why BenchPress exists, what it is and what it is not."
	),
	"og_image": "",
}
