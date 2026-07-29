"""Financial Statements adapter — routes get_period_list through Business Period Engine.

Compatibility boundary only. Period arithmetic lives in BusinessPeriodEngine.
The runtime patch is applied by ``persian_calendar.calendar.patches``.
"""

from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	get_business_calendar_for_company,
)

# Captured once by the patch applicator before replacement. Never set to the adapter.
_original_get_period_list: Callable[..., Any] | None = None


def set_original_get_period_list(fn: Callable[..., Any]) -> None:
	"""Store the real ERPNext stock function (called by the patch applicator)."""
	global _original_get_period_list
	if _original_get_period_list is None:
		_original_get_period_list = fn


def get_original_get_period_list() -> Callable[..., Any] | None:
	return _original_get_period_list


def get_period_list(
	from_fiscal_year,
	to_fiscal_year,
	period_start_date,
	period_end_date,
	filter_based_on,
	periodicity,
	accumulated_values=False,
	company=None,
	reset_period_on_fy_change=True,
	ignore_fiscal_year=False,
):
	"""Drop-in replacement for ERPNext ``financial_statements.get_period_list``.

	Gregorian Business Calendar → real captured stock function (exact ERPNext behavior).
	Non-Gregorian → Business Period Engine + server-side labels.
	"""
	bc = get_business_calendar_for_company(company) if company else BUSINESS_CALENDAR_GREGORIAN

	if bc == BUSINESS_CALENDAR_GREGORIAN:
		if _original_get_period_list is None:
			frappe.throw(
				_(
					"Calendar Framework period adapter is active but the original "
					"ERPNext get_period_list was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_get_period_list(
			from_fiscal_year,
			to_fiscal_year,
			period_start_date,
			period_end_date,
			filter_based_on,
			periodicity,
			accumulated_values=accumulated_values,
			company=company,
			reset_period_on_fy_change=reset_period_on_fy_change,
			ignore_fiscal_year=ignore_fiscal_year,
		)

	return _business_calendar_period_list(
		from_fiscal_year,
		to_fiscal_year,
		period_start_date,
		period_end_date,
		filter_based_on,
		periodicity,
		accumulated_values=accumulated_values,
		company=company,
		reset_period_on_fy_change=reset_period_on_fy_change,
		ignore_fiscal_year=ignore_fiscal_year,
		calendar_name=bc,
	)


def _business_calendar_period_list(
	from_fiscal_year,
	to_fiscal_year,
	period_start_date,
	period_end_date,
	filter_based_on,
	periodicity,
	accumulated_values=False,
	company=None,
	reset_period_on_fy_change=True,
	ignore_fiscal_year=False,
	calendar_name="Jalali",
):
	"""Generate period list using Business Period Engine for non-Gregorian calendars."""
	from erpnext.accounts.report.financial_statements import (
		get_fiscal_year_data,
		validate_dates,
		validate_fiscal_year,
	)
	from erpnext.accounts.utils import get_fiscal_year

	if filter_based_on == "Fiscal Year":
		fiscal_year = get_fiscal_year_data(from_fiscal_year, to_fiscal_year)
		validate_fiscal_year(fiscal_year, from_fiscal_year, to_fiscal_year)
		year_start_date = getdate(fiscal_year.year_start_date)
		year_end_date = getdate(fiscal_year.year_end_date)
	else:
		validate_dates(period_start_date, period_end_date)
		year_start_date = getdate(period_start_date)
		year_end_date = getdate(period_end_date)

	cal = CalendarEngine.for_calendar(calendar_name)
	bp_list = BusinessPeriodEngine.generate(
		start_date=year_start_date,
		end_date=year_end_date,
		periodicity=periodicity,
		provider=cal,
	)

	lang = getattr(frappe.local, "lang", None) or "en"
	locale = "fa" if lang in ("fa", "ar") else "en"

	period_list = []
	for bp in bp_list:
		period = frappe._dict(
			{
				"from_date": bp.from_date,
				"to_date": bp.to_date,
				"key": bp.key,
				"year_start_date": year_start_date,
				"year_end_date": year_end_date,
			}
		)

		if not ignore_fiscal_year:
			try:
				period.to_date_fiscal_year = get_fiscal_year(period.to_date, company=company)[0]
				period.from_date_fiscal_year_start_date = get_fiscal_year(
					period.from_date, company=company
				)[1]
			except Exception:
				period.to_date_fiscal_year = None
				period.from_date_fiscal_year_start_date = period.from_date

		accumulated_from = None
		if accumulated_values:
			if reset_period_on_fy_change and period.get("from_date_fiscal_year_start_date"):
				accumulated_from = period.from_date_fiscal_year_start_date
			else:
				accumulated_from = bp_list[0].from_date

		period["label"] = format_period_label(
			bp,
			locale=locale,
			accumulated=accumulated_values,
			accumulated_from=accumulated_from,
		)
		period_list.append(period)

	return period_list


def validate_consolidated_calendars(companies: list[str]) -> str | None:
	"""Check that all companies share the same Business Calendar.

	Returns the common calendar name, or raises if mixed.
	"""
	if not companies:
		return BUSINESS_CALENDAR_GREGORIAN

	calendars = {get_business_calendar_for_company(c) for c in companies}
	if len(calendars) > 1:
		frappe.throw(
			_(
				"Consolidated reports require all selected companies to use the same "
				"Business Calendar. Found: {0}"
			).format(", ".join(sorted(calendars)))
		)

	return calendars.pop()
