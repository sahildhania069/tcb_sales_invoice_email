app_name = "tcb_sales_invoice_email"
app_title = "TCB Sales Invoice Email"
app_publisher = "Vaibhav"
app_description = "Auto Email App"
app_email = "test@example.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tcb_sales_invoice_email",
# 		"logo": "/assets/tcb_sales_invoice_email/logo.png",
# 		"title": "TCB Sales Invoice Email",
# 		"route": "/tcb_sales_invoice_email",
# 		"has_permission": "tcb_sales_invoice_email.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tcb_sales_invoice_email/css/tcb_sales_invoice_email.css"
# app_include_js = "/assets/tcb_sales_invoice_email/js/tcb_sales_invoice_email.js"

# include js, css files in header of web template
# web_include_css = "/assets/tcb_sales_invoice_email/css/tcb_sales_invoice_email.css"
# web_include_js = "/assets/tcb_sales_invoice_email/js/tcb_sales_invoice_email.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tcb_sales_invoice_email/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"Sales Order": "public/js/sales_order.js",
	"Delivery Note": "public/js/delivery_note.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tcb_sales_invoice_email/public/icons.svg"

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
# 	"methods": "tcb_sales_invoice_email.utils.jinja_methods",
# 	"filters": "tcb_sales_invoice_email.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tcb_sales_invoice_email.install.before_install"
# after_install = "tcb_sales_invoice_email.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tcb_sales_invoice_email.uninstall.before_uninstall"
# after_uninstall = "tcb_sales_invoice_email.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tcb_sales_invoice_email.utils.before_app_install"
# after_app_install = "tcb_sales_invoice_email.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tcb_sales_invoice_email.utils.before_app_uninstall"
# after_app_uninstall = "tcb_sales_invoice_email.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tcb_sales_invoice_email.notifications.get_notification_config"

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

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"0 0 * * *": [
			# Runs at midnight (00:00)
			"tcb_sales_invoice_email.tasks.send_delivery_emails"
		],
		"0 0 */4 * *": [
			# Runs at midnight (00:00) every 4 days
			"tcb_sales_invoice_email.tasks.send_overdue_invoice_emails"
		]
	}
}

# Testing
# -------

# before_tests = "tcb_sales_invoice_email.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tcb_sales_invoice_email.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tcb_sales_invoice_email.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tcb_sales_invoice_email.utils.before_request"]
# after_request = ["tcb_sales_invoice_email.utils.after_request"]

# Job Events
# ----------
# before_job = ["tcb_sales_invoice_email.utils.before_job"]
# after_job = ["tcb_sales_invoice_email.utils.after_job"]

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
# 	"tcb_sales_invoice_email.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }


fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "module",
                "in",
                (
                    "TCB Sales Invoice Email"
                ),
            ]
        ],
    }
]
