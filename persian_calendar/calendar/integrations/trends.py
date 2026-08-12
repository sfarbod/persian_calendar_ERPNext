"""Trends adapters — Business Calendar-aware period ranges and column labels.

Stock surfaces (ERPNext v16)::

    get_period_date_ranges(period, fiscal_year=None, year_start_date=None)
        → list[[start_date, end_date], ...]

    period_wise_columns_query(filters, trans)
        → (period_columns, period_select_sql)

``get_period_date_ranges`` has no company argument on stock. Resolution order:

1. Explicit ``company`` keyword (adapter extension; stock callers omit it)
2. Fiscal Year company links (all must share one Business Calendar)
3. CalendarEngine company fallback (user default / Global Defaults)
4. Gregorian safe default

Gregorian Business Calendar → captured real ERPNext functions.
Jalali → BusinessPeriodEngine ranges (Gregorian storage dates) + Jalali column labels.

Aggregation already uses ``SUM(IF(date BETWEEN sd AND ed, …))`` against those
ranges. Version 2.0.1 fixes column **labels** that previously used ``strftime("%b")``
on the range start (Gregorian abbr) even when ranges were Jalali.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.adapter_helpers import (
	company_from_filters,
	report_locale,
	resolve_business_calendar,
)
from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_trends_column_label
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	get_business_calendar_for_company,
)

_original_get_period_date_ranges: Callable[..., Any] | None = None
_original_period_wise_columns_query: Callable[..., Any] | None = None


def set_original_get_period_date_ranges(fn: Callable[..., Any]) -> None:
	global _original_get_period_date_ranges
	if _original_get_period_date_ranges is None:
		_original_get_period_date_ranges = fn


def get_original_get_period_date_ranges() -> Callable[..., Any] | None:
	return _original_get_period_date_ranges


def set_original_period_wise_columns_query(fn: Callable[..., Any]) -> None:
	global _original_period_wise_columns_query
	if _original_period_wise_columns_query is None:
		_original_period_wise_columns_query = fn


def get_original_period_wise_columns_query() -> Callable[..., Any] | None:
	return _original_period_wise_columns_query


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


def period_wise_columns_query(filters, trans):
	"""Drop-in for ``erpnext.controllers.trends.period_wise_columns_query``.

	Jalali Business Calendar:
	- Passes ``company`` into ``get_period_date_ranges`` (stable multi-company)
	- Labels periods with Jalali month/quarter names (not Gregorian ``%b``)
	- SQL still allocates via ``BETWEEN`` on Gregorian storage dates

	Gregorian Business Calendar → captured stock implementation unchanged.
	"""
	company = company_from_filters(filters)
	bc = resolve_business_calendar(company, get_bc=get_business_calendar_for_company)

	if bc != BUSINESS_CALENDAR_JALALI:
		if _original_period_wise_columns_query is None:
			frappe.throw(
				_(
					"Trends columns adapter is active but the original "
					"period_wise_columns_query was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_period_wise_columns_query(filters, trans)

	return _jalali_period_wise_columns_query(filters, trans)


def _jalali_period_wise_columns_query(filters, trans):
	"""Mirror stock Trends column/SQL construction with Jalali labels + company."""
	query_details = ""
	pwc = []
	company = company_from_filters(filters)
	period = filters.get("period")
	bet_dates = get_period_date_ranges(period, filters.get("fiscal_year"), company=company)

	if trans in ["Purchase Receipt", "Delivery Note", "Purchase Invoice", "Sales Invoice"]:
		trans_date = "posting_date"
		if filters.get("period_based_on") and trans in ["Purchase Invoice", "Sales Invoice"]:
			trans_date = filters.get("period_based_on")
	else:
		trans_date = "transaction_date"

	if period != "Yearly":
		locale = report_locale()
		for dt in bet_dates:
			_append_jalali_period_columns(dt, period, pwc, locale=locale)
			query_details = _period_wise_query(dt, trans_date, query_details)
	else:
		fy = filters.get("fiscal_year")
		pwc = [
			_(fy) + " (" + _("Qty") + "):Float:120",
			_(fy) + " (" + _("Amt") + "):Currency/currency:120",
		]
		query_details = " SUM(t2.stock_qty), SUM(t2.base_net_amount),"

	query_details += "SUM(t2.stock_qty), SUM(t2.base_net_amount)"
	return pwc, query_details


def _append_jalali_period_columns(bet_dates, period, pwc, *, locale: str) -> None:
	sd = getdate(bet_dates[0])
	ed = getdate(bet_dates[1])
	label = format_trends_column_label(sd, ed, period, locale=locale)
	pwc += [
		_(label) + " (" + _("Qty") + "):Float:120",
		_(label) + " (" + _("Amt") + "):Currency/currency:120",
	]


def _period_wise_query(bet_dates, trans_date, query_details):
	# Same SQL shape as stock get_period_wise_query — inclusive Gregorian bounds
	sd = bet_dates[0]
	ed = bet_dates[1]
	query_details += (
		f"SUM(IF(t1.{trans_date} BETWEEN '{sd}' AND '{ed}', t2.stock_qty, NULL)),"
		f"\n\t\t\t\t\tSUM(IF(t1.{trans_date} BETWEEN '{sd}' AND '{ed}', t2.base_net_amount, NULL)),"
		"\n\t\t\t\t"
	)
	return query_details


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
