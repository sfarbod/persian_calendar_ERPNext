"""Sales / Purchase Analytics adapter — Company Business Calendar periods.

ERPNext v16.29 call graph (verified)::

    sales_analytics.execute
      → Analytics(filters)           # get_period_date_ranges in __init__
      → Analytics.run
           → update_company_list_for_parent_company  # may expand subsidiaries
           → get_columns / get_data / get_chart_data
                → get_period(end_date | posting_date)

    purchase_analytics.execute
      → Analytics(filters).run()     # same class object

Stock keys rows with the string returned by ``get_period``, and uses
``scrub(that_string)`` as column fieldnames. Chart data wrongly looks up
``scrub(column_label)`` — for Jalali we set label ≠ key, so ``get_chart_data``
is also patched to read ``fieldname``.

Stable-key strategy (Jalali Monthly / Quarterly / Yearly)
---------------------------------------------------------
- Authoritative bucket id: ``BusinessPeriod.key`` (locale-neutral)
- Column fieldname: ``frappe.scrub(key)``
- Display label: ``format_period_label`` (presentation only)
- Mapping is 1:1 via the same ``get_period`` return value (the key)

Weekly and Gregorian Business Calendar always call captured originals.
Half-Yearly is not exposed in Sales Analytics UI (v16.29); not implemented here.

This adapter is independent of ``controllers.trends.get_period_date_ranges``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.adapter_helpers import (
	build_jalali_periods,
	companies_from_filters,
	company_from_filters,
	lookup_period_key,
	period_bounds_index,
	range_from_filters,
	report_locale,
	should_use_jalali_engine,
)
from persian_calendar.calendar.period_engine import BusinessPeriod
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	get_business_calendar_for_company,
)

_original_get_period_date_ranges: Callable[..., Any] | None = None
_original_get_period: Callable[..., Any] | None = None
_original_get_columns: Callable[..., Any] | None = None
_original_get_chart_data: Callable[..., Any] | None = None
_original_update_company_list: Callable[..., Any] | None = None

_JALALI_ENGINE_RANGES = frozenset({"Monthly", "Quarterly", "Yearly"})


def set_original_sales_analytics_methods(
	get_period_date_ranges_fn,
	get_period_fn,
	get_columns_fn,
	get_chart_data_fn,
	update_company_list_fn,
) -> None:
	"""Capture stock Analytics methods exactly once."""
	global \
		_original_get_period_date_ranges, \
		_original_get_period, \
		_original_get_columns, \
		_original_get_chart_data, \
		_original_update_company_list
	if _original_get_period_date_ranges is None:
		_original_get_period_date_ranges = get_period_date_ranges_fn
	if _original_get_period is None:
		_original_get_period = get_period_fn
	if _original_get_columns is None:
		_original_get_columns = get_columns_fn
	if _original_get_chart_data is None:
		_original_get_chart_data = get_chart_data_fn
	if _original_update_company_list is None:
		_original_update_company_list = update_company_list_fn


def get_original_sales_analytics_methods():
	return (
		_original_get_period_date_ranges,
		_original_get_period,
		_original_get_columns,
		_original_get_chart_data,
		_original_update_company_list,
	)


def _primary_company(filters) -> str | None:
	return company_from_filters(filters)


def _companies_list(filters) -> list[str]:
	return companies_from_filters(filters)


def validate_companies_business_calendar(companies: list[str]) -> str:
	"""Return shared Business Calendar or throw on mixed calendars."""
	if not companies:
		return BUSINESS_CALENDAR_GREGORIAN
	unique = {get_business_calendar_for_company(c) for c in companies}
	if len(unique) > 1:
		detail = ", ".join(f"{c}={get_business_calendar_for_company(c)}" for c in companies)
		frappe.throw(
			_(
				"Sales/Purchase Analytics cannot mix Business Calendars across "
				"companies ({0}). Align Company.business_calendar or disable "
				"subsidiary aggregation."
			).format(detail)
		)
	return next(iter(unique))


def _should_use_jalali_engine(analytics) -> bool:
	"""True when Jalali BC and range is Monthly/Quarterly/Yearly."""
	filters = analytics.filters
	return should_use_jalali_engine(
		company=_primary_company(filters),
		rang=range_from_filters(filters),
		allowed_ranges=_JALALI_ENGINE_RANGES,
		get_bc=get_business_calendar_for_company,
	)


def _build_jalali_periods(analytics) -> list[BusinessPeriod]:
	return build_jalali_periods(
		analytics.filters.from_date,
		analytics.filters.to_date,
		analytics.filters.range,
		_primary_company(analytics.filters),
		snap=True,
		allow_half_yearly=False,
	)


def _ensure_jalali_period_index(analytics) -> list[BusinessPeriod]:
	"""Build/cached period list and end-date index on the Analytics instance."""
	cached = getattr(analytics, "_pc_sa_periods", None)
	if cached is not None:
		return cached
	periods = _build_jalali_periods(analytics)
	analytics._pc_sa_periods = periods
	analytics._pc_sa_jalali = True
	analytics._pc_sa_bounds = period_bounds_index(periods)
	return periods


def get_period_date_ranges(self):
	"""Drop-in for ``Analytics.get_period_date_ranges``."""
	if _original_get_period_date_ranges is None:
		frappe.throw(
			_(
				"Sales Analytics adapter is active but originals were not captured. "
				"Call apply_calendar_patches()."
			)
		)

	# Weekly always stock; Gregorian BC always stock
	if not _should_use_jalali_engine(self):
		self._pc_sa_jalali = False
		self._pc_sa_periods = None
		return _original_get_period_date_ranges(self)

	periods = _ensure_jalali_period_index(self)
	# Stock contract: list of period **end** dates only
	self.periodic_daterange = [bp.to_date for bp in periods]


def get_period(self, posting_date):
	"""Drop-in for ``Analytics.get_period`` — returns stable key for Jalali."""
	if _original_get_period is None:
		frappe.throw(_("Sales Analytics get_period original was not captured."))

	if not getattr(self, "_pc_sa_jalali", False):
		# Period ranges may not have run yet with jalali flag (defensive)
		if not _should_use_jalali_engine(self):
			return _original_get_period(self, posting_date)
		_ensure_jalali_period_index(self)

	if not getattr(self, "_pc_sa_jalali", False):
		return _original_get_period(self, posting_date)

	bounds = getattr(self, "_pc_sa_bounds", None)
	if not bounds:
		_ensure_jalali_period_index(self)
		bounds = self._pc_sa_bounds

	key = lookup_period_key(posting_date, bounds or [])
	if key is not None:
		return key

	# Outside generated range — fall back to stock label behaviour (rare edge)
	return _original_get_period(self, posting_date)


def get_columns(self):
	"""Drop-in for ``Analytics.get_columns`` — Jalali labels vs scrub(key) fieldnames."""
	if _original_get_columns is None:
		frappe.throw(_("Sales Analytics get_columns original was not captured."))

	if not getattr(self, "_pc_sa_jalali", False):
		return _original_get_columns(self)

	locale = report_locale()
	periods = getattr(self, "_pc_sa_periods", None) or []
	period_by_end = {bp.to_date: bp for bp in periods}

	# Rebuild columns mirroring stock structure but with key fieldnames + pretty labels
	self.columns = [
		{
			"label": _(self.filters.tree_type),
			"options": self.filters.tree_type if self.filters.tree_type != "Order Type" else "",
			"fieldname": "entity",
			"fieldtype": "Link" if self.filters.tree_type != "Order Type" else "Data",
			"width": 140 if self.filters.tree_type != "Order Type" else 200,
		}
	]
	if self.filters.tree_type in ["Customer", "Supplier", "Item"]:
		self.columns.append(
			{
				"label": _(self.filters.tree_type + " Name"),
				"fieldname": "entity_name",
				"fieldtype": "Data",
				"width": 140,
			}
		)
	if self.filters.tree_type == "Item":
		self.columns.append(
			{
				"label": _("UOM"),
				"fieldname": "stock_uom",
				"fieldtype": "Link",
				"options": "UOM",
				"width": 100,
			}
		)

	for end_date in self.periodic_daterange:
		bp = period_by_end.get(getdate(end_date))
		if bp is None:
			# Should not happen; fall back to key from get_period
			key = get_period(self, end_date)
			label = key
		else:
			key = bp.key
			label = format_period_label(bp, locale=locale)
		self.columns.append(
			{
				"label": label,
				"fieldname": frappe.scrub(key),
				"fieldtype": "Float",
				"width": 120,
			}
		)

	self.columns.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "width": 120})


def get_chart_data(self):
	"""Drop-in for ``Analytics.get_chart_data``.

	Stock looks up ``curve[scrub(label)]``. For Jalali, label ≠ key, so values
	must be read via column ``fieldname``.
	"""
	if _original_get_chart_data is None:
		frappe.throw(_("Sales Analytics get_chart_data original was not captured."))

	if not getattr(self, "_pc_sa_jalali", False):
		return _original_get_chart_data(self)

	length = len(self.columns)
	if self.filters.tree_type in ["Customer", "Supplier"]:
		period_cols = self.columns[2 : length - 1]
	elif self.filters.tree_type == "Item":
		period_cols = self.columns[3 : length - 1]
	else:
		period_cols = self.columns[1 : length - 1]

	labels = [d.get("label") for d in period_cols]
	fieldnames = [d.get("fieldname") for d in period_cols]

	datasets = []
	if self.filters.curves != "select":
		for curve in self.data:
			data = {
				"name": curve.get("entity_name", curve["entity"]),
				"values": [curve.get(fn, 0) for fn in fieldnames],
			}
			if self.filters.curves == "non-zeros" and not sum(data["values"]):
				continue
			elif self.filters.curves == "total" and "indent" in curve:
				if curve["indent"] == 0:
					datasets.append(data)
			elif self.filters.curves == "total":
				if datasets:
					a = [
						data["values"][idx] + datasets[0]["values"][idx] for idx in range(len(data["values"]))
					]
					datasets[0]["values"] = a
				else:
					datasets.append(data)
					datasets[0]["name"] = _("Total")
			else:
				datasets.append(data)

	self.chart = {"data": {"labels": labels, "datasets": datasets}, "type": "line"}
	if self.filters["value_quantity"] == "Value":
		self.chart["fieldtype"] = "Currency"
	else:
		self.chart["fieldtype"] = "Float"


def update_company_list_for_parent_company(self):
	"""Drop-in — validate subsidiary companies share one Business Calendar."""
	if _original_update_company_list is None:
		frappe.throw(_("Sales Analytics update_company_list original was not captured."))
	_original_update_company_list(self)
	companies = _companies_list(self.filters)
	if len(companies) > 1:
		validate_companies_business_calendar(companies)
