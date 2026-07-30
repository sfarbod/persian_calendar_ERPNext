# Copyright (c) 2025, Persian Calendar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

_fiscal_year_validate_dates_patched = False


def setup_fiscal_year_override():
	"""Setup Fiscal Year validation override using Company Business Calendar (not Display)."""
	global _fiscal_year_validate_dates_patched
	if _fiscal_year_validate_dates_patched:
		return

	from erpnext.accounts.doctype.fiscal_year.fiscal_year import FiscalYear as OriginalFiscalYear

	original_validate_dates = OriginalFiscalYear.validate_dates

	def jalali_validate_dates(self):
		"""Override validate_dates to support Jalali Business Calendar.

		Uses Company Business Calendar — NOT the user's Display Calendar.
		"""
		try:
			from persian_calendar.calendar.resolve import get_business_calendar_for_company

			# Determine company: FY may be scoped to companies via child table
			company = None
			if self.get("companies"):
				# Use first linked company's Business Calendar
				company = self.companies[0].get("company")
			if not company:
				company = frappe.defaults.get_user_default("company")

			bc = get_business_calendar_for_company(company)
			if bc != "Jalali":
				return original_validate_dates(self)

			self.validate_from_to_dates("year_start_date", "year_end_date")

			if self.is_short_year:
				return

			start_date = getdate(self.year_start_date)
			end_date = getdate(self.year_end_date)
			days_diff = (end_date - start_date).days

			# Jalali year: 365 or 366 days; allow ±1 day tolerance
			if days_diff < 354 or days_diff > 366:
				frappe.throw(
					frappe._("Fiscal Year should be approximately one Jalali year (354-366 days)"),
					frappe.exceptions.InvalidDates,
				)
		except Exception:
			return original_validate_dates(self)

	OriginalFiscalYear.validate_dates = jalali_validate_dates
	_fiscal_year_validate_dates_patched = True


def remove_fiscal_year_override():
	"""Remove Fiscal Year validation override"""
	pass
