"""Fixed Asset Register chart adapter — allocate by period bounds, not labels.

Upstream ``prepare_chart_data`` seeds buckets with ``get_period_list`` labels then
looks up rows via ``formatdate(date, "MMM YYYY")``. Under Jalali Business Calendar
those strings diverge (``Farvardin 1405`` vs ``Apr 2026``) → ``KeyError``.

This adapter:

- Gregorian / missing company → captured stock ``prepare_chart_data`` (parity)
- Jalali company → same chart structure, allocate via ``from_date``/``to_date``,
  emit Jalali ``period.label`` only for presentation
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from persian_calendar.calendar.adapter_helpers import (
	aggregate_by_period_bounds,
	company_from_filters,
	resolve_business_calendar,
)
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_JALALI,
	get_business_calendar_for_company,
)

_original_prepare_chart_data: Callable[..., Any] | None = None


def set_original_prepare_chart_data(fn: Callable[..., Any]) -> None:
	global _original_prepare_chart_data
	if _original_prepare_chart_data is None:
		_original_prepare_chart_data = fn


def get_original_prepare_chart_data() -> Callable[..., Any] | None:
	return _original_prepare_chart_data


def prepare_chart_data(data, filters):
	"""Drop-in for ``fixed_asset_register.prepare_chart_data``."""
	filters = frappe._dict(filters or {})
	company = company_from_filters(filters)
	bc = resolve_business_calendar(company, get_bc=get_business_calendar_for_company)

	if bc != BUSINESS_CALENDAR_JALALI:
		if _original_prepare_chart_data is None:
			frappe.throw(
				_(
					"Fixed Asset Register chart adapter is active but the original "
					"prepare_chart_data was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_prepare_chart_data(data, filters)

	return _jalali_prepare_chart_data(data, filters)


def _resolve_chart_date_context(data, filters):
	"""Mirror upstream date-field / range selection without using labels as keys."""
	if filters.filter_based_on not in ("Date Range", "Fiscal Year"):
		filters_filter_based_on = "Date Range"
		date_field = "purchase_date"
		filtered_data = [d for d in data if d.get(date_field)]
		if not filtered_data:
			return None
		filters_from_date = min(filtered_data, key=lambda a: a.get(date_field)).get(date_field)
		filters_to_date = max(filtered_data, key=lambda a: a.get(date_field)).get(date_field)
	else:
		filters_filter_based_on = filters.filter_based_on
		date_field = frappe.scrub(filters.date_based_on or "Purchase Date")
		filters_from_date = filters.from_date
		filters_to_date = filters.to_date

	return frappe._dict(
		date_field=date_field,
		filters_filter_based_on=filters_filter_based_on,
		filters_from_date=filters_from_date,
		filters_to_date=filters_to_date,
	)


def _jalali_prepare_chart_data(data, filters):
	if not data:
		return

	ctx = _resolve_chart_date_context(data, filters)
	if ctx is None:
		return

	# Import after patches so FS adapter (with company) is visible.
	from erpnext.accounts.report.financial_statements import get_period_list

	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		ctx.filters_from_date,
		ctx.filters_to_date,
		ctx.filters_filter_based_on,
		"Monthly",
		company=filters.company,
		ignore_fiscal_year=True,
	)
	if not period_list:
		return

	date_field = ctx.date_field

	def date_of(row):
		return row.get(date_field)

	def accumulate(bucket, row):
		bucket["asset_value"] += flt(row.get("asset_value"))
		bucket["depreciated_amount"] += flt(row.get("depreciated_amount"))

	pairs = aggregate_by_period_bounds(
		period_list,
		[d for d in data if d.get(date_field)],
		date_of=date_of,
		accumulate=accumulate,
		empty_bucket=lambda: {"asset_value": 0.0, "depreciated_amount": 0.0},
	)

	labels = [p.get("label") for p, _b in pairs]
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Asset Value"),
					"values": [flt(b.get("asset_value"), 2) for _p, b in pairs],
				},
				{
					"name": _("Depreciated Amount"),
					"values": [flt(b.get("depreciated_amount"), 2) for _p, b in pairs],
				},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
	}
