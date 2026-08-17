# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The eleven deploy steps, as the landing page tells them.

Ported from the design handoff. The only edits are the ones the credit decisions force: a deploy
is free, so nothing is "held" and nothing is "spent" — the hourly meter starts when the container
is handed over, and a run that never gets there costs nothing.

This is copy, not configuration. The rates on the page come from `Credit Pack` / `Instance Size`;
these strings describe the mechanism and change with the code, not in Desk.
"""

PHASES = [
	{
		"key": "request",
		"label": "Request",
		"range": "Steps 1-2",
		"summary": "Benchpress checks the plan, confirms your balance and reserves room on your host before anything is pulled.",
		"timing": "Under a second — deploying is free; nothing is metered until the container runs.",
		"nodes": ["device", "control"],
		"chips": ["api", "queue", "ledger"],
		"steps": [
			{
				"n": 1,
				"title": "Reserve a container slot",
				"detail": "The API validates the template, checks concurrency against your plan and reserves CPU, memory and a site name on the target host.",
				"cmd": 'POST /api/method/benchpress.deploy { template: "erpnext-v15" }',
			},
			{
				"n": 2,
				"title": "Check the balance",
				"detail": "Deploying costs nothing. Benchpress confirms the account can cover the first hour of runtime and that you are inside your concurrency cap.",
				"cmd": 'credits.check(user="you@example.com", size="Small")',
			},
		],
	},
	{
		"key": "image",
		"label": "Image",
		"range": "Steps 3-4",
		"summary": "The app list becomes a layer. Templates reuse a cached image; a custom lab builds one once and keeps it.",
		"timing": "Cached template: ~10s. First custom build: 3-6 minutes.",
		"nodes": ["control", "host"],
		"chips": ["queue"],
		"steps": [
			{
				"n": 3,
				"title": "Resolve the app list",
				"detail": "Frappe version, apps and branches are pinned into an apps.json — the same file a manual bench build would use.",
				"cmd": "apps.json → frappe@version-15, erpnext@version-15",
			},
			{
				"n": 4,
				"title": "Pull or build the image",
				"detail": "A matching layer is pulled from the registry. Custom labs run a real image build, and its log is streamed into Build logs line by line.",
				"cmd": "docker build --build-arg APPS_JSON_BASE64=… -t bp/erpnext-v15 .",
			},
		],
	},
	{
		"key": "site",
		"label": "Site",
		"range": "Steps 5-8",
		"summary": "The container comes up and Benchpress runs the exact bench commands you would have typed, in order.",
		"timing": "Roughly 60-120 seconds depending on the app set.",
		"nodes": ["host", "container", "services"],
		"chips": [],
		"steps": [
			{
				"n": 5,
				"title": "Start the container and services",
				"detail": "The bench container starts alongside MariaDB and Redis, with the sites directory on a named volume so data survives a restart.",
				"cmd": "docker run -v bp_sites:/home/frappe/frappe-bench/sites …",
			},
			{
				"n": 6,
				"title": "Create the site",
				"detail": "A fresh site is created with a generated administrator password, which is stored encrypted and revealed only to you.",
				"cmd": "bench new-site erpnext-demo.bp.local --admin-password ****",
			},
			{
				"n": 7,
				"title": "Install apps and migrate",
				"detail": "Every app in the template is installed, then migrations run. This is the step that fails loudest, so its output is kept verbatim.",
				"cmd": "bench --site erpnext-demo.bp.local install-app erpnext && bench migrate",
			},
			{
				"n": 8,
				"title": "Build assets",
				"detail": "Frontend bundles are built inside the container and served by its own nginx — no shared asset host to drift out of sync.",
				"cmd": "bench build --production",
			},
		],
	},
	{
		"key": "network",
		"label": "Network",
		"range": "Steps 9-11",
		"summary": "The site joins your mesh, gets health-checked, and only then are the credentials handed over and the meter started.",
		"timing": "5-10 seconds, then the site is yours.",
		"nodes": ["host", "wg", "device"],
		"chips": ["ledger"],
		"steps": [
			{
				"n": 9,
				"title": "Attach the WireGuard route",
				"detail": "The container is given a mesh address and a peer entry per registered device. Nothing is bound to a public interface.",
				"cmd": "wg set wg0 peer <pubkey> allowed-ips 10.13.13.24/32",
			},
			{
				"n": 10,
				"title": "Health check",
				"detail": "Benchpress fetches the site over the mesh until it answers. If it never does, the run is marked failed and the container is torn down.",
				"cmd": "GET https://erpnext-demo.bp.local/api/method/ping → pong",
			},
			{
				"n": 11,
				"title": "Hand over credentials",
				"detail": "Site URL, mesh IP, code-server link and passwords appear on the lab page. The hourly meter starts at this point, and only this point.",
				"cmd": 'ledger.start(lab="erpnext-demo", size="Small")',
			},
		],
	},
]

ACTIVE_PHASE = "site"
