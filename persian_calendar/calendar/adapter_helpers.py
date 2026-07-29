"""Shared adapter helpers for Business Calendar integrations (Phase 4b).

These helpers extract duplicated Gregorian/Jalali gating, snapping, and
period-index logic. They do **not** change BusinessPeriodEngine behaviour.

Adapters should pass ``get_bc=get_business_calendar_for_company`` from their
own module namespace so unit tests can still patch the adapter's import.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from frappe.utils import getdate

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.period_engine import BusinessPeriod, BusinessPeriodEngine
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
)
from persian_calendar.calendar.resolve import (
	get_business_calendar_for_company as _default_get_bc,
)

GetBc = Callable[[str | None], str]


def company_from_filters(filters) -> str | None:
	"""Extract primary company from a filters mapping / object.

	If company is a list/tuple, return the first entry (Sales Analytics primary).
	"""
	if not filters:
		return None
	if hasattr(filters, "get"):
		company = filters.get("company")
	else:
		company = getattr(filters, "company", None)
	if isinstance(company, list | tuple):
		return company[0] if company else None
	return company


def companies_from_filters(filters) -> list[str]:
	"""Normalize filters.company to a list of company names."""
	if not filters:
		return []
	if hasattr(filters, "get"):
		company = filters.get("company")
	else:
		company = getattr(filters, "company", None)
	if not company:
		return []
	if isinstance(company, list | tuple):
		return [c for c in company if c]
	return [company]


def range_from_filters(filters) -> str | None:
	if not filters:
		return None
	if hasattr(filters, "get"):
		return filters.get("range")
	return getattr(filters, "range", None)


def resolve_business_calendar(
	company: str | None,
	*,
	get_bc: GetBc | None = None,
	default: str = BUSINESS_CALENDAR_GREGORIAN,
) -> str:
	"""Resolve Business Calendar for *company*; never uses Display Calendar."""
	resolver = get_bc or _default_get_bc
	if not company:
		return default
	return resolver(company)


def should_use_jalali_engine(
	*,
	company: str | None,
	rang: str | None,
	allowed_ranges: frozenset[str],
	get_bc: GetBc | None = None,
	weekly_always_stock: bool = True,
) -> bool:
	"""True when Jalali BC and *rang* is in *allowed_ranges* (Weekly → False)."""
	if weekly_always_stock and rang == "Weekly":
		return False
	if rang not in allowed_ranges:
		return False
	if not company:
		return False
	return resolve_business_calendar(company, get_bc=get_bc) == BUSINESS_CALENDAR_JALALI


def report_locale() -> str:
	"""Presentation locale for period labels (not used for business math)."""
	import frappe

	lang = getattr(frappe.local, "lang", None) or "en"
	return "fa" if lang in ("fa", "ar") else "en"


def snap_jalali_range_start(
	from_date: date,
	rang: str,
	company: str | None = None,
	*,
	allow_half_yearly: bool = False,
) -> date:
	"""Floor *from_date* to the Jalali business period start (Gregorian storage).

	Mirrors Sales (no Half-Yearly) and Stock (Half-Yearly when enabled) snap
	semantics before ``BusinessPeriodEngine.generate``.
	"""
	cal = CalendarEngine.jalali()
	from_date = getdate(from_date)
	if rang == "Monthly":
		return cal.month_start(from_date)
	if rang == "Quarterly" or (allow_half_yearly and rang == "Half-Yearly"):
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


def build_jalali_periods(
	from_date,
	to_date,
	periodicity: str,
	company: str | None = None,
	*,
	snap: bool = True,
	allow_half_yearly: bool = False,
) -> list[BusinessPeriod]:
	"""Generate Jalali business periods via BusinessPeriodEngine."""
	start = getdate(from_date)
	end = getdate(to_date)
	if snap:
		start = snap_jalali_range_start(start, periodicity, company, allow_half_yearly=allow_half_yearly)
	if end < start:
		return []
	return BusinessPeriodEngine.generate(
		start_date=start,
		end_date=end,
		periodicity=periodicity,
		provider=CalendarEngine.jalali(),
	)


def period_bounds_index(periods: list[BusinessPeriod]) -> list[tuple[date, date, str]]:
	"""Ordered (from_date, to_date, key) tuples for inclusive date lookup."""
	return [(bp.from_date, bp.to_date, bp.key) for bp in periods]


def period_by_end_index(periods: list[BusinessPeriod]) -> dict[date, BusinessPeriod]:
	return {bp.to_date: bp for bp in periods}


def lookup_period_key(posting_date, bounds: list[tuple[date, date, str]]) -> str | None:
	"""Return BusinessPeriod.key for *posting_date*, or None if outside bounds."""
	posting = getdate(posting_date)
	for start, end, key in bounds:
		if start <= posting <= end:
			return key
	return None


def set_attr_or_item(obj: Any, key: str, value: Any) -> None:
	"""Set on mapping-like filters or plain objects."""
	try:
		obj[key] = value
	except Exception:
		setattr(obj, key, value)


def capture_once(holder: Any, attr: str, value: Any) -> Any:
	"""Set ``holder.attr = value`` only when currently None; return stored value."""
	current = getattr(holder, attr, None)
	if current is None:
		setattr(holder, attr, value)
		return value
	return current
