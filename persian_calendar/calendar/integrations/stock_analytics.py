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
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriod, BusinessPeriodEngine
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
	if not filters:
		return None
	if hasattr(filters, "get"):
		return filters.get("company")
	return getattr(filters, "company", None)


def _range(filters) -> str | None:
	if hasattr(filters, "get"):
		return filters.get("range")
	return getattr(filters, "range", None)


def _set_cache(filters, key: str, value) -> None:
	try:
		filters[key] = value
	except Exception:
		setattr(filters, key, value)


def _resolve_bc_once(filters) -> str:
	"""Resolve Business Calendar once per filters object (not per SLE row)."""
	cached = getattr(filters, _CTX_BC_RESOLVED, None)
	if cached is not None:
		return cached
	company = _company(filters)
	bc = get_business_calendar_for_company(company) if company else BUSINESS_CALENDAR_GREGORIAN
	_set_cache(filters, _CTX_BC_RESOLVED, bc)
	return bc


def _should_use_jalali_engine(filters) -> bool:
	rang = _range(filters)
	if rang == "Weekly" or rang not in _JALALI_ENGINE_RANGES:
		return False
	return _resolve_bc_once(filters) == BUSINESS_CALENDAR_JALALI


def _snap_jalali_start(from_date: date, rang: str, company: str | None) -> date:
	"""Mirror stock floor using Jalali months / Fiscal Year (Gregorian storage).

	Quarter / half-year first-day snap mirrors sales_analytics (jdatetime month
	index only — period generation still goes through BusinessPeriodEngine).
	"""
	cal = CalendarEngine.jalali()
	from_date = getdate(from_date)
	if rang == "Monthly":
		return cal.month_start(from_date)
	if rang in ("Quarterly", "Half-Yearly"):
		import jdatetime

		j = jdatetime.date.fromgregorian(date=from_date)
		if rang == "Quarterly":
			q_month = ((j.month - 1) // 3) * 3 + 1
			return jdatetime.date(j.year, q_month, 1).togregorian()
		h_month = 1 if j.month <= 6 else 7
		return jdatetime.date(j.year, h_month, 1).togregorian()
	# Yearly — Fiscal Year start (Gregorian storage on FY DocType)
	from erpnext.accounts.utils import get_fiscal_year

	if company:
		return getdate(get_fiscal_year(from_date, company=company)[1])
	return getdate(get_fiscal_year(from_date)[1])


def _build_jalali_periods(filters) -> list[BusinessPeriod]:
	rang = _range(filters)
	company = _company(filters)
	from_date = _snap_jalali_start(filters.from_date, rang, company)
	to_date = getdate(filters.to_date)
	if to_date < from_date:
		return []
	return BusinessPeriodEngine.generate(
		start_date=from_date,
		end_date=to_date,
		periodicity=rang,
		provider=CalendarEngine.jalali(),
	)


def _ensure_context(filters) -> list[BusinessPeriod]:
	cached = getattr(filters, _CTX_PERIODS, None)
	if cached is not None and getattr(filters, _CTX_JALALI, False):
		return cached
	periods = _build_jalali_periods(filters)
	_set_cache(filters, _CTX_JALALI, True)
	_set_cache(filters, _CTX_PERIODS, periods)
	_set_cache(filters, _CTX_BOUNDS, [(bp.from_date, bp.to_date, bp.key) for bp in periods])
	_set_cache(filters, _CTX_BY_END, {bp.to_date: bp for bp in periods})
	return periods


def _clear_jalali_flag(filters) -> None:
	_set_cache(filters, _CTX_JALALI, False)
	_set_cache(filters, _CTX_PERIODS, None)


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

	posting = getdate(posting_date)
	bounds = getattr(filters, _CTX_BOUNDS, None) or []
	for start, end, key in bounds:
		if start <= posting <= end:
			return key
	return _original_get_period(posting_date, filters)


def get_period_columns(filters):
	"""Drop-in — Jalali uses ``format_period_label``; fieldnames are ``scrub(key)``."""
	if _original_get_period_columns is None:
		frappe.throw(_("Stock Analytics get_period_columns original was not captured."))

	if not _should_use_jalali_engine(filters):
		return _original_get_period_columns(filters)

	lang = getattr(frappe.local, "lang", None) or "en"
	locale = "fa" if lang in ("fa", "ar") else "en"
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
