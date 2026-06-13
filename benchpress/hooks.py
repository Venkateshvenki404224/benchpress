app_name = "benchpress"
app_title = "BenchPress"
app_publisher = "Venkatesh"
app_description = "Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured."
app_email = "venkateshvenki404224@gmail.com"
app_license = "mit"
app_logo_url = "/assets/benchpress/images/logo/favicon.svg"
app_home = "/desk/benchpress"

# required_apps = []

# Fixtures
fixtures = [{"dt": "Role", "filters": [["role_name", "in", ["BenchPress Admin", "BenchPress User"]]]}]

# Apps screen entry
add_to_apps_screen = [
	{
		"name": "benchpress",
		"logo": "/assets/benchpress/images/logo/logo.png",
		"title": "BenchPress",
		"route": "/frontend",
		"has_permission": "benchpress.permissions.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/benchpress/css/benchpress.css"
# app_include_js = "/assets/benchpress/js/benchpress.js"

# include js, css files in header of web template
# web_include_css = "/assets/benchpress/css/benchpress.css"
# web_include_js = "/assets/benchpress/js/benchpress.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "benchpress/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "benchpress/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "benchpress.utils.jinja_methods",
# 	"filters": "benchpress.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "benchpress.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "benchpress.uninstall.before_uninstall"
# after_uninstall = "benchpress.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps

# before_app_install = "benchpress.utils.before_app_install"
# after_app_install = "benchpress.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps

# before_app_uninstall = "benchpress.utils.before_app_uninstall"
# after_app_uninstall = "benchpress.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "benchpress.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Bench Instance": "benchpress.permissions.bench_instance_query_conditions",
	"Deploy Log": "benchpress.permissions.deploy_log_query_conditions",
}

# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Website route rules
website_route_rules = [
	{"from_route": "/frontend/<path:app_path>", "to_route": "frontend"},
]

# Scheduled Tasks
# ---------------

scheduler_events = {
	# "all": [
	# 	"benchpress.tasks.all"
	# ],
	# "daily": [
	# 	"benchpress.tasks.daily"
	# ],
	# "hourly": [
	# 	"benchpress.tasks.hourly"
	# ],
	# "weekly": [
	# 	"benchpress.tasks.weekly"
	# ],
	# "monthly": [
	# 	"benchpress.tasks.monthly"
	# ],
	"cron": {
		"*/1 * * * *": [
			"benchpress.stats_collector.collect_all_stats",
		],
		"*/5 * * * *": [
			"benchpress.mariadb_manager.scheduled_health_check",
			"benchpress.traefik_manager.scheduled_bench_health_check",
		],
		"0 2 * * *": [
			"benchpress.mariadb_manager.scheduled_backup",
		],
	},
}

# Testing
# -------

# before_tests = "benchpress.install.before_tests"

# Overriding Methods
# --------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "benchpress.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "benchpress.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
ignore_links_on_delete = ["Deploy Log", "Build Log", "Database Server"]

# Request Events
# ----------------
# before_request = ["benchpress.utils.before_request"]
# after_request = ["benchpress.utils.after_request"]

# Job Events
# ----------
# before_job = ["benchpress.utils.before_job"]
# after_job = ["benchpress.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"benchpress.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

default_log_clearing_doctypes = {
	"Deploy Log": 7,
	"Build Log": 7,
}
