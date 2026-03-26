app_name = "benchpress"
app_title = "BenchPress"
app_publisher = "Venkatesh"
app_description = "Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured."
app_email = "venkateshvenki404224@gmail.com"
app_license = "mit"
app_logo_url = "/assets/benchpress/images/logo/favicon.svg"

# Apps screen entry
add_to_apps_screen = [
	{
		"name": "benchpress",
		"logo": "/assets/benchpress/images/logo/logo.png",
		"title": "BenchPress",
		"route": "/frontend",
		"has_permission": "benchpress.api.has_app_permission",
	}
]

# Website route rules
website_route_rules = [
	{"from_route": "/frontend/<path:app_path>", "to_route": "frontend"},
]

# Scheduled Tasks
scheduler_events = {
	"cron": {
		"*/2 * * * *": [
			"benchpress.stats_collector.collect_all_stats",
		],
	},
}

# Ignore Deploy Log links when deleting Bench Instance
ignore_links_on_delete = ["Deploy Log", "Build Log"]
