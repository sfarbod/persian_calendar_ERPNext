"""Sales Pipeline Analytics adapter — Company Business Calendar periods.

ERPNext 16.29 Sales Pipeline Analytics groups by Gregorian SQL ``Month`` /
``Quarter`` / ``MonthName`` on ``Opportunity.expected_closing``.

Strategy:

- Gregorian Business Calendar → captured stock ``execute`` (exact parity).
- Jalali Business Calendar → fetch opportunity rows (Gregorian dates), allocate
  with ``BusinessPeriodEngine`` + ``lookup_period_key``, aggregate in Python.

Supported frequencies (upstream UI only): Monthly, Quarterly.

Does not change Display Calendar, forms, lists, print, or email.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import frappe
from frappe import _, scrub
from frappe.utils import flt, getdate

from persian_calendar.calendar.adapter_helpers import (
	build_jalali_periods,
	company_from_filters,
	lookup_period_key,
	period_bounds_index,
	range_from_filters,
	report_locale,
	should_use_jalali_engine,
)
from persian_calendar.calendar.period_engine import BusinessPeriod
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.resolve import get_business_calendar_for_company

_ALLOWED_RANGES = frozenset({"Monthly", "Quarterly"})

_original_execute: Callable[..., Any] | None = None


def set_original_sales_pipeline_execute(fn: Callable[..., Any]) -> None:
	global _original_execute
	if _original_execute is None:
		_original_execute = fn


def get_original_sales_pipeline_execute() -> Callable[..., Any] | None:
	return _original_execute


def execute(filters=None):
	"""Drop-in replacement for sales_pipeline_analytics.execute."""
	filters = filters or {}
	company = company_from_filters(filters)
	rang = range_from_filters(filters)

	if not should_use_jalali_engine(
		company=company,
		rang=rang,
		allowed_ranges=_ALLOWED_RANGES,
		get_bc=get_business_calendar_for_company,
	):
		if _original_execute is None:
			frappe.throw(
				_(
					"Sales Pipeline Analytics adapter is active but the original "
					"execute was not captured. Call apply_calendar_patches()."
				)
			)
		return _original_execute(filters)

	return _jalali_execute(frappe._dict(filters))


def _jalali_execute(filters):
	_validate_filters(filters)

	periods = build_jalali_periods(
		filters.from_date,
		filters.to_date,
		filters.range,
		company_from_filters(filters),
		snap=True,
		allow_half_yearly=False,
	)
	period_meta = _period_meta(periods)
	columns = _jalali_columns(filters, period_meta)

	rows = _fetch_opportunity_rows(filters)
	if filters.get("based_on") == "Amount":
		_convert_amounts_to_company_currency(filters, rows)

	periodic = _allocate(filters, rows, period_bounds_index(periods))
	data = _build_data_rows(filters, periodic, period_meta)
	chart = _jalali_chart(filters, period_meta, data)
	return columns, data, None, chart


def _validate_filters(filters):
	if not filters.get("from_date"):
		frappe.throw(_("From Date is mandatory"))
	if not filters.get("to_date"):
		frappe.throw(_("To Date is mandatory"))
	if filters.get("range") not in _ALLOWED_RANGES:
		frappe.throw(_("Range must be Monthly or Quarterly"))


def _period_meta(periods: list[BusinessPeriod]) -> list[dict[str, Any]]:
	locale = report_locale()
	out = []
	for bp in periods:
		key = bp.key
		out.append(
			{
				"key": key,
				"fieldname": scrub(key),
				"label": format_period_label(bp, locale=locale),
				"from_date": bp.from_date,
				"to_date": bp.to_date,
			}
		)
	return out


def _jalali_columns(filters, period_meta: list[dict[str, Any]]) -> list[dict]:
	based_on = {"Number": "Int", "Amount": "Currency"}[filters.get("based_on")]
	columns: list[dict] = []

	if filters.get("pipeline_by") == "Owner":
		columns.append(
			{"fieldname": "opportunity_owner", "label": _("Opportunity Owner"), "width": 200}
		)
	elif filters.get("pipeline_by") == "Sales Stage":
		columns.append({"fieldname": "sales_stage", "label": _("Sales Stage"), "width": 200})

	for meta in period_meta:
		columns.append(
			{
				"fieldname": meta["fieldname"],
				"fieldtype": based_on,
				"label": meta["label"],
				"width": 200,
			}
		)
	return columns


def _get_conditions(filters) -> list:
	"""Mirror upstream SalesPipelineAnalytics.get_conditions."""
	conditions = []
	if filters.get("opportunity_source"):
		conditions.append({"utm_source": filters.get("opportunity_source")})
	if filters.get("opportunity_type"):
		conditions.append({"opportunity_type": filters.get("opportunity_type")})
	if filters.get("status"):
		conditions.append({"status": filters.get("status")})
	if filters.get("company"):
		conditions.append({"company": filters.get("company")})
	if filters.get("from_date") and filters.get("to_date"):
		conditions.append(
			["expected_closing", "between", [filters.get("from_date"), filters.get("to_date")]]
		)
	return conditions


def _fetch_opportunity_rows(filters) -> list[dict]:
	"""Fetch opportunity rows with Gregorian ``expected_closing`` (no SQL month/quarter)."""
	opp = frappe.qb.DocType("Opportunity")
	pipeline_by = {"Owner": "opportunity_owner", "Sales Stage": "sales_stage"}[
		filters.get("pipeline_by")
	]
	group_by_based_on = {"Owner": "_assign", "Sales Stage": "sales_stage"}[
		filters.get("pipeline_by")
	]
	pipeline_field = opp._assign if group_by_based_on == "_assign" else opp.sales_stage

	query = frappe.qb.get_query(
		"Opportunity",
		filters=_get_conditions(filters),
		ignore_permissions=True,
	)

	if filters.get("based_on") == "Number":
		return (
			query.select(
				pipeline_field.as_(pipeline_by),
				opp.expected_closing,
			)
			.run(as_dict=True)
		)

	return (
		query.select(
			pipeline_field.as_(pipeline_by),
			opp.expected_closing,
			opp.opportunity_amount.as_("amount"),
			opp.currency,
		)
		.run(as_dict=True)
	)


def _convert_amounts_to_company_currency(filters, rows: list[dict]) -> None:
	"""Preserve upstream exchange-rate behaviour (flt + cache)."""
	from erpnext.setup.utils import get_exchange_rate

	company = filters.get("company")
	default_currency = frappe.db.get_value("Company", company, "default_currency") if company else None
	if not default_currency:
		return

	cacheobj = frappe.cache()
	for data in rows:
		if data.get("currency") == default_currency:
			continue
		from_currency = data.get("currency")
		if not from_currency:
			continue
		cached = cacheobj.get(from_currency)
		if cached:
			rate = flt(str(cached, "UTF-8"))
		else:
			rate = get_exchange_rate(from_currency, default_currency)
			cacheobj.set(from_currency, rate)
			rate = flt(str(cacheobj.get(from_currency), "UTF-8"))
		data["amount"] = flt(data.get("amount")) * rate


def _allocate(filters, rows: list[dict], bounds) -> dict[str, dict[str, float]]:
	"""pipeline_value → {period_fieldname → metric}."""
	pipeline_by = {"Owner": "opportunity_owner", "Sales Stage": "sales_stage"}[
		filters.get("pipeline_by")
	]
	metric_key = {"Number": "count", "Amount": "amount"}[filters.get("based_on")]
	periodic: dict[str, dict[str, float]] = {}

	# Map BusinessPeriod.key → scrubbed fieldname once
	key_to_field = {start_end_key[2]: scrub(start_end_key[2]) for start_end_key in bounds}

	for row in rows:
		closing = row.get("expected_closing")
		if not closing:
			continue
		period_key = lookup_period_key(closing, bounds)
		if not period_key:
			continue
		fieldname = key_to_field[period_key]
		raw_value = row.get(pipeline_by)
		metric = 1.0 if metric_key == "count" else flt(row.get("amount"))

		if filters.get("pipeline_by") == "Owner":
			_allocate_owner(filters, periodic, fieldname, raw_value, metric)
		else:
			_bump(periodic, raw_value, fieldname, metric)

	return periodic


def _allocate_owner(filters, periodic, fieldname, raw_value, metric) -> None:
	"""Mirror upstream Owner / _assign expansion and assigned_to filter."""
	if raw_value == "Not Assigned" or raw_value == "[]" or raw_value is None or not raw_value:
		assigned_to = ["Not Assigned"]
	else:
		try:
			assigned_to = json.loads(raw_value)
		except (TypeError, ValueError, json.JSONDecodeError):
			assigned_to = ["Not Assigned"]

	assigned_filter = filters.get("assigned_to")
	if assigned_filter:
		if assigned_filter not in assigned_to:
			return
		_bump(periodic, assigned_filter, fieldname, metric)
		return

	if len(assigned_to) > 1:
		for user in assigned_to:
			_bump(periodic, user, fieldname, metric)
	else:
		_bump(periodic, assigned_to[0], fieldname, metric)


def _bump(periodic: dict, pipeline_value, fieldname: str, metric: float) -> None:
	if pipeline_value is None:
		pipeline_value = "Not Assigned"
	periodic.setdefault(pipeline_value, {})
	periodic[pipeline_value][fieldname] = periodic[pipeline_value].get(fieldname, 0.0) + metric


def _build_data_rows(filters, periodic, period_meta: list[dict[str, Any]]) -> list[dict]:
	pipeline_by = {"Owner": "opportunity_owner", "Sales Stage": "sales_stage"}[
		filters.get("pipeline_by")
	]
	data = []
	for pipeline, period_data in periodic.items():
		row = {pipeline_by: pipeline}
		for meta in period_meta:
			fn = meta["fieldname"]
			row[fn] = period_data.get(fn, 0.0)
		data.append(row)
	return data


def _jalali_chart(filters, period_meta: list[dict[str, Any]], data: list[dict]) -> dict:
	"""Chart labels/datasets from the same period list as table columns."""
	based_on = {"Amount": "amount", "Number": "count"}[filters.get("based_on")]
	labels = [meta["label"] for meta in period_meta]
	values = []
	for meta in period_meta:
		fn = meta["fieldname"]
		total = 0.0
		for row in data:
			total += flt(row.get(fn))
		values.append(total)
	return {
		"data": {"labels": labels, "datasets": [{"name": based_on, "values": values}]},
		"type": "line",
	}
