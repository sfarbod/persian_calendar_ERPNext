"""Vehicle Expenses (HRMS) chart adapter — Company Business Calendar periods.

Upstream ``get_chart_data`` calls ERPNext ``get_period_list(..., "Monthly")``
**without** ``company``, so the Financial Statements Business Calendar adapter
always takes the Gregorian path.

This adapter:

- Gregorian / missing company → captured stock ``get_chart_data`` (exact parity)
- Jalali Company → same chart logic with ``get_period_list(..., company=…)`` so
  FS Business Calendar / ``BusinessPeriodEngine`` applies

Table columns remain vehicle-log rows (Display Calendar handles Date cells).
No independent Jalali arithmetic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from persian_calendar.calendar.adapter_helpers import company_from_filters, should_use_jalali_engine
from persian_calendar.calendar.resolve import get_business_calendar_for_company

_ALLOWED_RANGES = frozenset({"Monthly"})

_original_get_chart_data: Callable[..., Any] | None = None


def set_original_vehicle_expenses_get_chart_data(fn: Callable[..., Any]) -> None:
	global _original_get_chart_data
	if _original_get_chart_data is None:
		_original_get_chart_data = fn


def get_original_vehicle_expenses_get_chart_data() -> Callable[..., Any] | None:
	return _original_get_chart_data


def get_chart_data(data, filters):
	"""Drop-in for ``hrms.hr.report.vehicle_expenses.vehicle_expenses.get_chart_data``."""
	filters = frappe._dict(filters or {})
	company = company_from_filters(filters)

	if not should_use_jalali_engine(
		company=company,
		rang="Monthly",
		allowed_ranges=_ALLOWED_RANGES,
		get_bc=get_business_calendar_for_company,
	):
		if _original_get_chart_data is None:
			frappe.throw(
				_(
					"Vehicle Expenses adapter is active but the original "
					"get_chart_data was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_get_chart_data(data, filters)

	return _jalali_chart_data(data, filters)


def _jalali_chart_data(data, filters):
	# Import after patches so we hit the FS adapter (or rebound module attr).
	from erpnext.accounts.report.financial_statements import get_period_list

	period_list = get_period_list(
		filters.fiscal_year,
		filters.fiscal_year,
		filters.from_date,
		filters.to_date,
		filters.filter_based_on,
		"Monthly",
		company=filters.company,
	)

	fuel_data, service_data = [], []

	for period in period_list:
		total_fuel_exp = 0
		total_service_exp = 0

		for row in data:
			if row.date <= period.to_date and row.date >= period.from_date:
				total_fuel_exp += flt(row.fuel_expense)
				total_service_exp += flt(row.service_expense)

		fuel_data.append([period.key, total_fuel_exp])
		service_data.append([period.key, total_service_exp])

	labels = [period.label for period in period_list]
	fuel_exp_data = [row[1] for row in fuel_data]
	service_exp_data = [row[1] for row in service_data]

	datasets = []
	if fuel_exp_data:
		datasets.append({"name": _("Fuel Expenses"), "values": fuel_exp_data})

	if service_exp_data:
		datasets.append({"name": _("Service Expenses"), "values": service_exp_data})

	return {
		"data": {"labels": labels, "datasets": datasets},
		"type": "line",
		"fieldtype": "Currency",
	}
