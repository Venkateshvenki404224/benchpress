app_name = "benchpress"
app_title = "BenchPress"
app_publisher = "Venkatesh"
app_description = "Press a button. Get a Frappe bench. Self-hosted, Docker-powered, VPN-secured."
app_email = "venkateshvenki404224@gmail.com"
app_license = "AGPL-3.0-only"
app_logo_url = "/assets/benchpress/images/logo/favicon.svg"
app_home = "/desk/benchpress"

# The VPN plane (peers, IP allocation, wg-agent) is fully delegated to vpn_management.
required_apps = ["vpn_management"]

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

# Colour-coded status pills in the desk list views. Frappe inlines these files into the DocType
# meta, so they are independent of the (still commented out) app_include_js bundle.
doctype_list_js = {
	"Lab": "public/js/list_view/lab_list.js",
	"Bench Instance": "public/js/list_view/bench_instance_list.js",
	"Bench Site": "public/js/list_view/bench_site_list.js",
	"Database Server": "public/js/list_view/database_server_list.js",
	"Waitlist Entry": "public/js/list_view/waitlist_entry_list.js",
}

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

# Every tenant-owned doctype needs BOTH dicts. `permission_query_conditions` has only two
# consumers, both in the list engine, so a single-document read never consults it — and with no
# `has_permission` hook registered Frappe's controller check returns True and the role grant alone
# decides, which covers the whole table. `test_doctype_scoping` fails when a doctype has one half
# without the other.
permission_query_conditions = {
	"Bench Instance": "benchpress.permissions.bench_instance_query_conditions",
	"Deploy Log": "benchpress.permissions.deploy_log_query_conditions",
	"Build Log": "benchpress.permissions.build_log_query_conditions",
	"Credit Account": "benchpress.permissions.credit_account_query_conditions",
	"Credit Ledger Entry": "benchpress.permissions.credit_ledger_query_conditions",
	"Bench Event": "benchpress.permissions.bench_event_query_conditions",
}

# Not the `has_permission` key inside `add_to_apps_screen` above — that one gates the apps screen.
has_permission = {
	"Credit Account": "benchpress.permissions.credit_account_has_permission",
	"Credit Ledger Entry": "benchpress.permissions.credit_ledger_has_permission",
	"Deploy Log": "benchpress.permissions.deploy_log_has_permission",
	"Build Log": "benchpress.permissions.build_log_has_permission",
	"Bench Event": "benchpress.permissions.bench_event_has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# The payment seam. `razorpay_frappe` is optional and deliberately not in `required_apps`, so this
# entry simply never fires on a site without it — a hook on an absent DocType is inert, which is
# exactly the coupling we want with a gateway a self-hoster must never be forced to install.
#
# `on_update` rather than a webhook route on purpose: it catches the checkout callback, the
# `payment.captured` webhook, its retries and an operator's manual "Sync Status" through one path.
# That makes redelivery the normal case, which is why the handler is idempotent by construction.
#
# `User.after_insert` is the self-serve onboarding seam: it hands a signup the app role, and the
# signup grant when the signup has already proved the address (an OAuth flow). The email path's
# grant waits for `on_session_creation` below, because a `User` row proves nothing about who owns
# the address it holds.
doc_events = {
	"Razorpay Order": {
		"on_update": "benchpress.credits.payments.on_razorpay_update",
	},
	"User": {
		"after_insert": "benchpress.credits.onboarding.after_user_insert",
	},
}

# Fires once per new session, which is the first moment an email signup has demonstrably received
# its verification mail — `sign_up` sets a password the user never sees.
on_session_creation = ["benchpress.credits.onboarding.after_login"]

# The login page's own signup form keeps posting `frappe.core.doctype.user.user.sign_up`; this
# routes that `cmd` through the hosted plan's rate limit, waitlist switch and domain blocklist
# without a second signup endpoint existing anywhere.
override_whitelisted_methods = {
	"frappe.core.doctype.user.user.sign_up": "benchpress.signup.sign_up",
}

# Website route rules
website_route_rules = [
	{"from_route": "/frontend/<path:app_path>", "to_route": "frontend"},
]

# Scheduled Tasks
# ---------------

# A scheduled entry that touches Docker must name an enqueuer, never the work itself.
#
# `ScheduledJobType.get_queue_name()` returns `long` only for a frequency string containing `Long`
# or `Maintenance`, so every entry below lands on `default` — which `queue-long` (Docker socket
# mounted) and `queue-short` (no socket, no `group_add`) both consume. The two workers race the
# same pop and the idle one usually wins, so the busier the platform, the more reliably the job
# lands on the worker that cannot do it. It fails as a socket `FileNotFoundError`, which names
# neither the queue nor the scheduler.
#
# The socket-mounted services are `queue-long` and `queue-stops`. So the entry is a small function
# that calls `frappe.enqueue(..., queue="long")`, and the Docker call lives on the other side of
# it. `enqueue_stats_sweep`, `enqueue_route_reconcile`, `enqueue_health_check`, `enqueue_backup`
# and the two in `image_cache` are all that shape.

scheduler_events = {
	# "all": [
	# 	"benchpress.tasks.all"
	# ],
	"daily": [
		"benchpress.credits.reaper.reap_stopped_instances",
	],
	# "hourly": [
	# 	"benchpress.tasks.hourly"
	# ],
	"weekly": [
		"benchpress.image_cache.enqueue_prewarm_catalog",
		"benchpress.image_cache.enqueue_sweep",
	],
	# "monthly": [
	# 	"benchpress.tasks.monthly"
	# ],
	"cron": {
		# `DEFAULT_SCHEDULER_TICK` is four minutes here, so this fires every four, not every one.
		# The format stays `*/1` so shortening the tick needs no edit.
		"*/1 * * * *": [
			"benchpress.stats_collector.enqueue_stats_sweep",
		],
		"*/5 * * * *": [
			"benchpress.mariadb_manager.enqueue_health_check",
			# Never on the `*/1` stats cron: that job spends ~2s per container on the Docker
			# socket, and a decision queued behind Docker I/O arrives late. The clock is not
			# this job's business — `drain` owns expiry; this one checks balances.
			"benchpress.credits.sweep.enforce_limits",
			# `queue-short` has no route mount either. Lifecycle triggers already converge in
			# seconds — this is the net under them.
			"benchpress.ingress.enqueue_route_reconcile",
			# The net under the lease warden, not the primary path: `DEFAULT_SCHEDULER_TICK` is
			# four minutes here, so no cron entry can promise better than that. The warden claims
			# within seconds; this catches whatever it misses while the warden is restarting.
			# Both use the same conditional claim, so running together cannot double-stop a
			# bench. It makes no Docker calls, so it is safe on either worker.
			"benchpress.credits.drain.sweep_expired_leases",
			# Not the daily list: a slot leaked by a killed worker is a lockout for a caller at
			# their cap, and it costs three grouped reads and no Docker call to find.
			"benchpress.credits.admission_repair.reconcile_admissions",
			# The net under the event listener. Enqueued, never run inline: the pass needs the
			# Docker socket, which only `queue-long` and `backend` carry. A listener that stays
			# down then degrades to the convergence BenchPress had before it, not to silence.
			"benchpress.docker_events.enqueue_reconcile",
		],
		"0 2 * * *": [
			"benchpress.mariadb_manager.enqueue_backup",
		],
	},
}

# Testing
# -------

# before_tests = "benchpress.install.before_tests"

# Overriding Methods
# --------------------
# `override_whitelisted_methods` is declared beside the document events above, next to the hook it
# belongs with.
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
	# Longer than the logs: this is the evidence trail for a failure that may not be looked
	# at the same week.
	"Bench Event": 30,
}
