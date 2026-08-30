# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""The eleven deploy steps as `deploy_pipeline.DEPLOY_STEPS` runs them, grouped into four phases.
Every `cmd` is a line the pipeline actually writes or a command it actually runs — quote, don't invent.
"""

PHASES = [
	{
		"key": "prepare",
		"label": "Prepare",
		"range": "Steps 1-2",
		"summary": "The run proves the shared database is up and the lab's image is on the host. The deploy itself never builds one.",
		"timing": "One click on an unbuilt lab builds the image ahead of this step, under a lock so two clicks cannot build the same tag twice.",
		"nodes": ["control", "host"],
		"chips": ["api", "queue"],
		"steps": [
			{
				"n": 1,
				"title": "Check the shared infrastructure",
				"detail": "One MariaDB and one Redis are shared by every bench. Both are started if they are down, and the run waits until MariaDB accepts connections.",
				"cmd": "MariaDB reachable at benchpress-mariadb:3306",
			},
			{
				"n": 2,
				"title": "Resolve the lab image",
				"detail": "The lab's tag has to be on the host already, or this step stops the run and says to build it — a deploy is never a 10-40 minute build in disguise. The log also says whether the image carries a golden database dump.",
				"cmd": "Using built image benchpress/crm:lab",
			},
		],
	},
	{
		"key": "container",
		"label": "Container",
		"range": "Steps 3-5",
		"summary": "The container is created at its instance size, started on a BenchPress bridge, and given a tunnel address.",
		"timing": "No port is published on the host — the bench is reached through the bridge or the tunnel.",
		"nodes": ["host", "container", "wg"],
		"chips": [],
		"steps": [
			{
				"n": 3,
				"title": "Create the container",
				"detail": "Memory, CPU, PIDs and disk come from the Instance Size, read at deploy time. The container is never privileged; isolation comes from the runtime.",
				"cmd": "container runtime sysbox-runc",
			},
			{
				"n": 4,
				"title": "Wait for the container IP",
				"detail": "Nothing can be written into the bench or routed at it until it reports an address on its bridge.",
				"cmd": "container_ip <address on the bench bridge>",
			},
			{
				"n": 5,
				"title": "Configure the WireGuard peer",
				"detail": "Any stale peer is removed, a fresh tunnel IP is claimed from vpn_management, and the container is configured with it.",
				"cmd": "VPN peer <peer> registered, claimed IP <tunnel ip>",
			},
		],
	},
	{
		"key": "site",
		"label": "Site",
		"range": "Steps 6-8",
		"summary": "Config is written into the container and the site is made — restored from the image's dump when it has one, created app by app when it does not.",
		"timing": "For a CRM lab on an idle 2-vCPU host, the site step is 9.1s of a 13.3s deploy when the dump is restored; 37.2s of 43.3s when it is refused.",
		"nodes": ["host", "container", "services"],
		"chips": [],
		"steps": [
			{
				"n": 6,
				"title": "Write common_site_config.json",
				"detail": "The shared database host and credentials, three Redis URLs, the socket.io port and the site's own port, written into the container.",
				"cmd": "/home/frappe/frappe-bench/sites/common_site_config.json written",
			},
			{
				"n": 7,
				"title": "Create the site",
				"detail": "setup-site.sh runs as the bench user against a temporary MariaDB account that is dropped afterwards. It restores the image's golden dump when restore is left on in Settings, the image carries a dump and the server's MariaDB major version matches; it installs the apps itself when any of the three does not hold.",
				"cmd": "bash /opt/benchpress/scripts/setup-site.sh",
			},
			{
				"n": 8,
				"title": "Assets",
				"detail": "Nothing is built here. Frontend bundles are baked into the lab image at build time; a stale bundle is fixed by rebuilding the lab.",
				"cmd": "Assets ship in the image — bundled at build time",
			},
		],
	},
	{
		"key": "access",
		"label": "Access",
		"range": "Steps 9-11",
		"summary": "The tenant's account is made inside the container, the site is served, and only then is the instance marked Running.",
		"timing": "Nothing before this line counts: a deploy that never reaches step 11 leaves no running bench.",
		"nodes": ["host", "container", "device"],
		"chips": [],
		"steps": [
			{
				"n": 9,
				"title": "Provision the SSH user",
				"detail": "linkuser.sh creates the account inside the container with a generated password. The app's own copy of the script is written in first, so it wins over the one baked into the image.",
				"cmd": "bash /opt/benchpress/scripts/linkuser.sh <username>",
			},
			{
				"n": 10,
				"title": "Start the lab's services",
				"detail": "serve.sh serves the site on port 8000. code-server is configured and started on 8080 when the lab and its size include it, and the log says so when it is skipped.",
				"cmd": "bash /opt/benchpress/scripts/serve.sh <username>",
			},
			{
				"n": 11,
				"title": "Deploy complete",
				"detail": "The instance goes to Running, the deploy log is marked a success and the owner is notified. The last line carries the run's total elapsed time.",
				"cmd": "=== Step 11/11: Deploy complete [complete @13.3s] ===",
			},
		],
	},
]

ACTIVE_PHASE = "site"
