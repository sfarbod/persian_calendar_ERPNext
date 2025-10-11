app_name = "persian_calendar"
app_title = "Persian Calendar"
app_publisher = "Farbod Siyahpoosh"
app_description = "Jalali Support"
app_email = "sfarbod@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "persian_calendar",
# 		"logo": "/assets/persian_calendar/logo.png",
# 		"title": "Persian Calendar",
# 		"route": "/persian_calendar",
# 		"has_permission": "persian_calendar.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

app_include_js = ["jalali_support.bundle.js"]
#app_include_css = ["persian_calendar.bundle.css"]

# include js, css files in header of desk.html
# app_include_css = "/assets/persian_calendar/css/persian_calendar.css"
# app_include_js = "/assets/persian_calendar/js/persian_calendar.js"

# include js, css files in header of web template
# web_include_css = "/assets/persian_calendar/css/persian_calendar.css"
# web_include_js = "/assets/persian_calendar/js/persian_calendar.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "persian_calendar/public/scss/website"

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
# app_include_icons = "persian_calendar/public/icons.svg"

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
# 	"methods": "persian_calendar.utils.jinja_methods",
# 	"filters": "persian_calendar.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "persian_calendar.install.before_install"
# after_install = "persian_calendar.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "persian_calendar.uninstall.before_uninstall"
# after_uninstall = "persian_calendar.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "persian_calendar.utils.before_app_install"
# after_app_install = "persian_calendar.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "persian_calendar.utils.before_app_uninstall"
# after_app_uninstall = "persian_calendar.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "persian_calendar.notifications.get_notification_config"

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
   "daily": ["persian_calendar.jalali_support.scheduler.month_end_runner"]
}
 
# scheduler_events = {
# 	"all": [
# 		"persian_calendar.tasks.all"
# 	],
# 	"daily": [
# 		"persian_calendar.tasks.daily"
# 	],
# 	"hourly": [
# 		"persian_calendar.tasks.hourly"
# 	],
# 	"weekly": [
# 		"persian_calendar.tasks.weekly"
# 	],
# 	"monthly": [
# 		"persian_calendar.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "persian_calendar.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "persian_calendar.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "persian_calendar.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["persian_calendar.utils.before_request"]
# after_request = ["persian_calendar.utils.after_request"]

# Job Events
# ----------
# before_job = ["persian_calendar.utils.before_job"]
# after_job = ["persian_calendar.utils.after_job"]

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
# 	"persian_calendar.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = ["Custom Field"]
desktop_items = ["jalali_settings"]

# Import formatters to override date formatting for exports
# Import at module level to ensure early loading
try:
    import persian_calendar.jalali_support.formatters
    print("Jalali formatters imported successfully")
except Exception as e:
    print(f"Error importing Jalali formatters: {e}")

# Request Events
# ----------------
before_request = ["persian_calendar.jalali_support.formatters.setup_jalali_formatters"]

# Install/Uninstall Events
# ------------------------
after_install = ["persian_calendar.jalali_support.doctype.custom_field.calendar_preference.create_calendar_preference_field"]
after_uninstall = ["persian_calendar.jalali_support.doctype.custom_field.calendar_preference.remove_calendar_preference_field"]