"""Stock Analytics adapter — Company Business Calendar periods.

ERPNext v16.29 call graph (verified)::

    stock_analytics.execute(filters)
      → get_period_columns(filters)
           → get_period_date_ranges(filters)   # list[[start, end], ...]
           → get_period(end_date, filters)
      → get_data(filters)
           → get_periodic_data(sle, filters)   # carry-forward by period key
                → get_period_date_ranges / get_period
           → get_period again for row fieldnames
      → get_chart_data(period_columns)         # labels only; empty datasets

Direct importers (identity-rebind required)::

    production_analytics  → get_period, get_period_columns, get_period_date_ranges
    work_order_summary    → get_period, get_period_date_ranges
    job_card_summary      → get_period, get_period_date_ranges

``round_down_to_nearest_frequency`` is NOT patched: it is only called from stock
``get_period_date_ranges``. Patching it would poison Gregorian delegation because
the captured original looks up ``round_down`` via module globals at call time.

Stable-key strategy (Jalali M/Q/H/Y)
------------------------------------
- Bucket id returned by ``get_period``: ``BusinessPeriod.key``
- Column fieldname: ``frappe.scrub(key)`` (stock contract)
- Display label: ``format_period_label`` via patched ``get_period_columns``
- Carry-forward in unpatched ``get_periodic_data`` keys off ``get_period`` —
  stable keys preserve sequential balance semantics.

Weekly + Gregorian BC → captured originals.
Half-Yearly: in Python increment map (not in Stock Analytics JS UI); engine-supported.

Independent of Trends and Sales Analytics patch targets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.adapter_helpers import (
	build_jalali_periods,
	company_from_filters,
	lookup_period_key,
	period_bounds_index,
	period_by_end_index,
	range_from_filters,
	report_locale,
	resolve_business_calendar,
	set_attr_or_item,
	should_use_jalali_engine,
)
from persian_calendar.calendar.period_engine import BusinessPeriod
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	get_business_calendar_for_company,
)

_original_get_period_date_ranges: Callable[..., Any] | None = None
_original_get_period: Callable[..., Any] | None = None
_original_get_period_columns: Callable[..., Any] | None = None
# Captured for diagnostics / contract tests only — not installed as a module patch.
_original_round_down: Callable[..., Any] | None = None

_JALALI_ENGINE_RANGES = frozenset({"Monthly", "Quarterly", "Half-Yearly", "Yearly"})

_CTX_JALALI = "_pc_stk_jalali"
_CTX_PERIODS = "_pc_stk_periods"
_CTX_BOUNDS = "_pc_stk_bounds"
_CTX_BY_END = "_pc_stk_by_end"
_CTX_BC_RESOLVED = "_pc_stk_bc_resolved"


def set_original_stock_analytics_functions(
	get_period_date_ranges_fn,
	get_period_fn,
	get_period_columns_fn,
	round_down_fn=None,
) -> None:
	"""Capture stock free functions exactly once."""
	global \
		_original_get_period_date_ranges, \
		_original_get_period, \
		_original_get_period_columns, \
		_original_round_down
	if _original_get_period_date_ranges is None:
		_original_get_period_date_ranges = get_period_date_ranges_fn
	if _original_get_period is None:
		_original_get_period = get_period_fn
	if _original_get_period_columns is None:
		_original_get_period_columns = get_period_columns_fn
	if _original_round_down is None and round_down_fn is not None:
		_original_round_down = round_down_fn


def get_original_stock_analytics_functions():
	return (
		_original_get_period_date_ranges,
		_original_get_period,
		_original_get_period_columns,
		_original_round_down,
	)


def _company(filters) -> str | None:
	return company_from_filters(filters)


def _range(filters) -> str | None:
	return range_from_filters(filters)


def _resolve_bc_once(filters) -> str:
	"""Resolve Business Calendar once per filters object (not per SLE row)."""
	cached = getattr(filters, _CTX_BC_RESOLVED, None)
	if cached is not None:
		return cached
	bc = resolve_business_calendar(
		_company(filters),
		get_bc=get_business_calendar_for_company,
		default=BUSINESS_CALENDAR_GREGORIAN,
	)
	set_attr_or_item(filters, _CTX_BC_RESOLVED, bc)
	return bc


def _should_use_jalali_engine(filters) -> bool:
	rang = _range(filters)
	if rang == "Weekly" or rang not in _JALALI_ENGINE_RANGES:
		return False
	return _resolve_bc_once(filters) == BUSINESS_CALENDAR_JALALI


def _build_jalali_periods(filters) -> list[BusinessPeriod]:
	return build_jalali_periods(
		filters.from_date,
		filters.to_date,
		_range(filters),
		_company(filters),
		snap=True,
		allow_half_yearly=True,
	)


def _ensure_context(filters) -> list[BusinessPeriod]:
	cached = getattr(filters, _CTX_PERIODS, None)
	if cached is not None and getattr(filters, _CTX_JALALI, False):
		return cached
	periods = _build_jalali_periods(filters)
	set_attr_or_item(filters, _CTX_JALALI, True)
	set_attr_or_item(filters, _CTX_PERIODS, periods)
	set_attr_or_item(filters, _CTX_BOUNDS, period_bounds_index(periods))
	set_attr_or_item(filters, _CTX_BY_END, period_by_end_index(periods))
	return periods


def _clear_jalali_flag(filters) -> None:
	set_attr_or_item(filters, _CTX_JALALI, False)
	set_attr_or_item(filters, _CTX_PERIODS, None)


def get_period_date_ranges(filters):
	"""Drop-in for stock_analytics.get_period_date_ranges → list[[start, end], ...]."""
	if _original_get_period_date_ranges is None:
		frappe.throw(
			_(
				"Stock Analytics adapter is active but originals were not captured. "
				"Call apply_calendar_patches()."
			)
		)

	if not _should_use_jalali_engine(filters):
		_clear_jalali_flag(filters)
		return _original_get_period_date_ranges(filters)

	periods = _ensure_context(filters)
	return [[bp.from_date, bp.to_date] for bp in periods]


def get_period(posting_date, filters):
	"""Drop-in — returns stable ``BusinessPeriod.key`` for Jalali engine ranges.

	Dates outside the generated report range fall back to the stock original so
	pre-range SLE rows keep stock off-range bucket behaviour while ``balance``
	carry-forward remains intact.
	"""
	if _original_get_period is None:
		frappe.throw(_("Stock Analytics get_period original was not captured."))

	if not _should_use_jalali_engine(filters):
		return _original_get_period(posting_date, filters)

	if not getattr(filters, _CTX_JALALI, False):
		_ensure_context(filters)

	key = lookup_period_key(posting_date, getattr(filters, _CTX_BOUNDS, None) or [])
	if key is not None:
		return key
	return _original_get_period(posting_date, filters)


def get_period_columns(filters):
	"""Drop-in — Jalali uses ``format_period_label``; fieldnames are ``scrub(key)``."""
	if _original_get_period_columns is None:
		frappe.throw(_("Stock Analytics get_period_columns original was not captured."))

	if not _should_use_jalali_engine(filters):
		return _original_get_period_columns(filters)

	locale = report_locale()
	ranges = get_period_date_ranges(filters)
	by_end = getattr(filters, _CTX_BY_END, {}) or {}
	period_columns = []
	for _start, end_date in ranges:
		end = getdate(end_date)
		bp = by_end.get(end)
		if bp is None:
			key = get_period(end, filters)
			label = key
		else:
			key = bp.key
			label = format_period_label(bp, locale=locale)
		period_columns.append(
			{
				"label": label,
				"fieldname": frappe.scrub(key),
				"fieldtype": "Float",
				"width": 120,
			}
		)
	return period_columns
