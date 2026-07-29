"""Trends period adapter — Business Calendar-aware get_period_date_ranges.

Stock signature (ERPNext v16.29)::

    get_period_date_ranges(period, fiscal_year=None, year_start_date=None)
        → list[[start_date, end_date], ...]

No company argument exists on the stock function. Resolution order:

1. Explicit ``company`` keyword (adapter extension; stock callers omit it)
2. Fiscal Year company links (all must share one Business Calendar)
3. CalendarEngine company fallback (user default / Global Defaults)
4. Gregorian safe default

Gregorian Business Calendar → captured real ERPNext function.
Jalali → BusinessPeriodEngine (Gregorian storage dates).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	get_business_calendar_for_company,
)

_original_get_period_date_ranges: Callable[..., Any] | None = None


def set_original_get_period_date_ranges(fn: Callable[..., Any]) -> None:
	global _original_get_period_date_ranges
	if _original_get_period_date_ranges is None:
		_original_get_period_date_ranges = fn


def get_original_get_period_date_ranges() -> Callable[..., Any] | None:
	return _original_get_period_date_ranges


def get_period_date_ranges(period, fiscal_year=None, year_start_date=None, company=None):
	"""Drop-in replacement for ``erpnext.controllers.trends.get_period_date_ranges``."""
	company = company or _resolve_company(fiscal_year)
	bc = get_business_calendar_for_company(company) if company else BUSINESS_CALENDAR_GREGORIAN

	if bc == BUSINESS_CALENDAR_GREGORIAN:
		if _original_get_period_date_ranges is None:
			frappe.throw(
				_(
					"Trends period adapter is active but the original "
					"get_period_date_ranges was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_get_period_date_ranges(period, fiscal_year, year_start_date)

	return _jalali_period_date_ranges(period, fiscal_year, year_start_date)


def _jalali_period_date_ranges(period, fiscal_year, year_start_date):
	year_start, year_end = _fiscal_bounds(fiscal_year, year_start_date)
	cal = CalendarEngine.jalali()
	bp_list = BusinessPeriodEngine.generate(
		start_date=year_start,
		end_date=year_end,
		periodicity=period,
		provider=cal,
	)
	# Stock return shape: list of [start, end] (mutable lists)
	return [[bp.from_date, bp.to_date] for bp in bp_list]


def _fiscal_bounds(fiscal_year, year_start_date):
	if year_start_date and fiscal_year:
		year_start_date = getdate(year_start_date)
		year_end_date = getdate(frappe.get_cached_value("Fiscal Year", fiscal_year, "year_end_date"))
		return year_start_date, year_end_date

	if year_start_date and not fiscal_year:
		# Stock path leaves year_end unbound — mirror by requiring FY when possible.
		# If only start is given, treat as single-day fallback (should not happen in BVR).
		start = getdate(year_start_date)
		return start, start

	year_start_date, year_end_date = frappe.get_cached_value(
		"Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"]
	)
	return getdate(year_start_date), getdate(year_end_date)


def _resolve_company(fiscal_year: str | None) -> str | None:
	"""Resolve company for Business Calendar without using Display Calendar."""
	# 1. Report / form filters when present
	try:
		form = getattr(frappe.local, "form_dict", None) or {}
		company = form.get("company")
		if company:
			return company
	except Exception:
		pass

	# 2. Fiscal Year company links — reject mixed calendars
	if fiscal_year:
		companies = frappe.get_all(
			"Fiscal Year Company",
			filters={"parent": fiscal_year},
			pluck="company",
		)
		if companies:
			unique = {get_business_calendar_for_company(c) for c in companies}
			if len(unique) > 1:
				frappe.throw(
					_(
						"Fiscal Year {0} is linked to companies with different Business "
						"Calendars ({1}). Trends/Budget Variance require a single Business "
						"Calendar. Select one company or align Company.business_calendar."
					).format(fiscal_year, ", ".join(sorted(unique)))
				)
			return companies[0]

	# 3. CalendarEngine / resolver fallback (user default company → Global Defaults)
	try:
		from frappe.defaults import get_user_default

		company = get_user_default("company")
		if company:
			return company
	except Exception:
		pass

	try:
		return frappe.db.get_single_value("Global Defaults", "default_company")
	except Exception:
		return None
