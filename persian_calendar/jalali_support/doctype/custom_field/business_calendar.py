# Copyright (c) 2026, Persian Calendar and contributors
# For license information, please see license.txt

"""Custom Field: Company.business_calendar (Business Calendar layer)."""

from __future__ import annotations

import frappe


FIELDNAME = "business_calendar"
DOCTYPE = "Company"


def create_business_calendar_field() -> None:
	"""Create Company.business_calendar if missing. Default Gregorian = zero behaviour change."""
	if frappe.db.exists("Custom Field", {"dt": DOCTYPE, "fieldname": FIELDNAME}):
		return

	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": DOCTYPE,
			"module": "Persian Calendar",
			"label": "Business Calendar",
			"fieldname": FIELDNAME,
			"insert_after": "country",
			"fieldtype": "Select",
			"options": "Gregorian\nJalali",
			"default": "Gregorian",
			"reqd": 0,
			"description": (
				"Official calendar for company business period arithmetic "
				"(depreciation, budgets, payroll months). Independent of each user's Display Calendar."
			),
		}
	)
	custom_field.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCTYPE)


def remove_business_calendar_field() -> None:
	"""Remove Company.business_calendar on uninstall."""
	name = frappe.db.get_value("Custom Field", {"dt": DOCTYPE, "fieldname": FIELDNAME}, "name")
	if name:
		frappe.delete_doc("Custom Field", name, ignore_permissions=True)
		frappe.clear_cache(doctype=DOCTYPE)


def on_company_update(doc, method=None) -> None:
	"""Clear Business Calendar resolver cache when a Company is saved."""
	from persian_calendar.calendar.resolve import clear_business_calendar_cache

	clear_business_calendar_cache()
