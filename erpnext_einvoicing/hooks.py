# Copyright (c) 2026, Scopen and contributors
# For license information, please see license.txt

app_name = "erpnext_einvoicing"
app_title = "ERPNext eInvoicing"
app_publisher = "Scopen"
app_description = "Electronic invoicing (e-Invoicing) module for ERPNext"
app_email = "contact@scopen.fr"
app_license = "gpl-3.0"

# Fixtures
# ---------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"Item-einvoice_source",
					"Purchase Invoice-einvoice_source",
					"Purchase Invoice Item-po_match_status",
					"Company-einvoicing_section",
					"Company-einvoicing_approved_platform",
					"Company-einvoicing_live_mode",
					"Company-einvoicing_client_id",
					"Company-einvoicing_client_secret",
					"Company-einvoicing_api_key",
					"Company-einvoicing_column_break_auth",
					"Company-einvoicing_access_token",
					"Company-einvoicing_token_expires_at",
					"Company-einvoicing_column_break_buttons",
					"Company-einvoicing_healthcheck",
					"Company-einvoicing_recreate_token",
					"Company-einvoicing_delete_token",
					"Company-einvoicing_rebuild_lifecycle_logs",
					"Company-einvoicing_po_required",
					"Company-einvoicing_pr_required",
					"Company-einvoicing_auto_sync",
					"Company-einvoicing_tab",
					"Company-einvoicing_platform_section",
					"Company-einvoicing_auth_section",
					"Company-einvoicing_sync_section",
					"Company-einvoicing_column_break_sync",
				],
			]
		],
	},
	{"dt": "eInvoicing Refusal Reason"},
]

# Apps
# ------------------

required_apps = ["frappe", "erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erpnext_einvoicing",
# 		"logo": "/assets/erpnext_einvoicing/logo.png",
# 		"title": "ERPNext eInvoicing",
# 		"route": "/erpnext_einvoicing",
# 		"has_permission": "erpnext_einvoicing.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_einvoicing/css/erpnext_einvoicing.css"
# app_include_js = "/assets/erpnext_einvoicing/js/erpnext_einvoicing.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_einvoicing/css/erpnext_einvoicing.css"
# web_include_js = "/assets/erpnext_einvoicing/js/erpnext_einvoicing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_einvoicing/public/scss/website"

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
doctype_js = {
	"Company": "public/js/company.js",
	"Purchase Invoice": "public/js/purchase_invoice.js",
}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erpnext_einvoicing/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpnext_einvoicing.utils.jinja_methods",
# 	"filters": "erpnext_einvoicing.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpnext_einvoicing.install.before_install"
# after_install = "erpnext_einvoicing.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "erpnext_einvoicing.uninstall.before_uninstall"
# after_uninstall = "erpnext_einvoicing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpnext_einvoicing.utils.before_app_install"
# after_app_install = "erpnext_einvoicing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpnext_einvoicing.utils.before_app_uninstall"
# after_app_uninstall = "erpnext_einvoicing.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "erpnext_einvoicing.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_einvoicing.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }


# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Custom Field": {
		# Supplier
		"after_insert": "erpnext_einvoicing.doc_events.custom_field_supplier.on_create",
		"on_trash": "erpnext_einvoicing.doc_events.custom_field_supplier.on_delete",
	},
	"Payment Entry": {
		"on_submit": "erpnext_einvoicing.doc_events.payment_entry.on_submit",
	},
	"Purchase Invoice": {
		"on_submit": "erpnext_einvoicing.doc_events.purchase_invoice.on_submit",
		"on_cancel": "erpnext_einvoicing.doc_events.purchase_invoice.on_cancel",
		"on_trash": "erpnext_einvoicing.doc_events.purchase_invoice.on_trash",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/30 * * * *": [
			"erpnext_einvoicing.providers.sync.sync_incoming_flows",
		],
		"*/5 * * * *": [
			"erpnext_einvoicing.providers.sync.poll_lifecycle_acknowledgements",
		],
	},
	# "all": [
	# 	"erpnext_einvoicing.tasks.all"
	# ],
	# "daily": [
	# 	"erpnext_einvoicing.tasks.daily"
	# ],
	# "hourly": [
	# 	"erpnext_einvoicing.tasks.hourly"
	# ],
	# "weekly": [
	# 	"erpnext_einvoicing.tasks.weekly"
	# ],
	# "monthly": [
	# 	"erpnext_einvoicing.tasks.monthly"
	# ],
}

# Testing
# -------

# before_tests = "erpnext_einvoicing.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "erpnext_einvoicing.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_einvoicing.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnext_einvoicing.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnext_einvoicing.utils.before_request"]
# after_request = ["erpnext_einvoicing.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnext_einvoicing.utils.before_job"]
# after_job = ["erpnext_einvoicing.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnext_einvoicing.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

after_install = "erpnext_einvoicing.install.after_install"
after_migrate = "erpnext_einvoicing.migrate.after_migrate"

# Log retention
# -------------

default_log_clearing_doctypes = {
	"eInvoicing Sync Log": 90,
	"eInvoicing Lifecycle Log": 90,
}
# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
