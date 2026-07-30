"""Monthly Distribution adapter — calendar-neutral month-position mapping.

ERPNext v16 Monthly Distribution is **not** used by Budget anymore. It remains
the percentage template for Sales Person / Territory / Sales Partner targets.

Storage model (unchanged):
- Child rows keep English month labels (January–December) for Gregorian parity.
- Child ``idx`` (1–12) is the canonical **business month position**.

Matching policy:
- Gregorian Business Calendar → stock ``strftime("%B")`` English-name matching.
- Jalali Business Calendar → match by business month position (``Period.period_number``
  ↔ child ``idx``), never by localized Farvardin/Esfand labels.

Calendar ownership:
- Monthly Distribution documents are company-neutral templates.
- The consuming report's company (via Business Calendar on period keys / company
  argument) determines which matching mode applies.
- The same January–December document may be reused by Gregorian and Jalali
  companies: position 1 is January for Gregorian math and Farvardin for Jalali math.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate

from erpnext.accounts.doctype.monthly_distribution.monthly_distribution import (
	MonthlyDistribution,
)

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	get_business_calendar_for_company,
)

# English labels remain the stock storage keys (Gregorian matching + UI seeds).
GREGORIAN_MONTH_LABELS = (
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
)

JALALI_MONTH_LABELS_EN = (
	"Farvardin",
	"Ordibehesht",
	"Khordad",
	"Tir",
	"Mordad",
	"Shahrivar",
	"Mehr",
	"Aban",
	"Azar",
	"Dey",
	"Bahman",
	"Esfand",
)

_original_get_periodwise_distribution_data = None
_original_get_percentage = None


def set_original_md_functions(periodwise_fn, percentage_fn) -> None:
	global _original_get_periodwise_distribution_data, _original_get_percentage
	if _original_get_periodwise_distribution_data is None:
		_original_get_periodwise_distribution_data = periodwise_fn
	if _original_get_percentage is None:
		_original_get_percentage = percentage_fn


def get_original_md_functions():
	return _original_get_periodwise_distribution_data, _original_get_percentage


class PersianCalendarMonthlyDistribution(MonthlyDistribution):
	"""Seed 12 English month slots (calendar-neutral positions via idx)."""

	@frappe.whitelist()
	def get_months(self):
		# Keep stock English labels so legacy documents and Gregorian matching work.
		# idx 1..12 is the business month position for both calendars.
		return super().get_months()


def business_month_position(d, calendar_system: str) -> int:
	"""Return business month number 1–12 for a Gregorian storage date."""
	cal = CalendarEngine.for_calendar(calendar_system)
	return cal.period(getdate(d), "Monthly").period_number


def resolve_distribution_percentage(
	doc,
	start_date,
	months_in_period: int,
	*,
	calendar_system: str = BUSINESS_CALENDAR_GREGORIAN,
) -> float:
	"""Sum percentage allocations for the business months covered by a period.

	Args:
		doc: Monthly Distribution document (or compatible with ``.percentages``).
		start_date: Period start (Gregorian storage date).
		months_in_period: Number of business months in the grain (1/3/6/12).
		calendar_system: ``Gregorian`` or ``Jalali``.
	"""
	if calendar_system == BUSINESS_CALENDAR_GREGORIAN:
		if _original_get_percentage is not None:
			return _original_get_percentage(doc, start_date, months_in_period)
		# Fallback stock-equivalent path
		percentage = 0.0
		months = [getdate(start_date).strftime("%B").title()]
		for r in range(1, months_in_period):
			months.append(add_months(getdate(start_date), r).strftime("%B").title())
		for d in doc.percentages:
			if d.month in months:
				percentage += flt(d.percentage_allocation)
		return percentage

	# Non-Gregorian: match by business month position ↔ child idx
	positions = _business_month_positions(start_date, months_in_period, calendar_system)
	index_map = _percentage_by_position(doc)
	percentage = 0.0
	for pos in positions:
		percentage += flt(index_map.get(pos, 0.0))
	return percentage


def _business_month_positions(start_date, months_in_period: int, calendar_system: str) -> list[int]:
	cal = CalendarEngine.for_calendar(calendar_system)
	cursor = getdate(start_date)
	positions: list[int] = []
	for _ in range(int(months_in_period)):
		positions.append(cal.period(cursor, "Monthly").period_number)
		cursor = cal.add_months(cal.month_start(cursor), 1)
	return positions


def _percentage_by_position(doc) -> dict[int, float]:
	"""Map business month position → percentage using child idx (1–12)."""
	rows = list(doc.get("percentages") or [])
	if not rows:
		return {}

	# Prefer explicit idx; fall back to enumeration order.
	by_pos: dict[int, float] = {}
	seen_idx: set[int] = set()
	for i, row in enumerate(rows, start=1):
		pos = int(row.idx) if getattr(row, "idx", None) else i
		if pos in seen_idx:
			_validation_error(
				_("Monthly Distribution {0} has duplicate month position {1}").format(
					getattr(doc, "name", ""), pos
				)
			)
		seen_idx.add(pos)
		by_pos[pos] = flt(row.percentage_allocation)
	return by_pos


def validate_distribution_positions(doc) -> None:
	"""Ensure unique positions and 100% total (stock-compatible)."""
	rows = list(doc.get("percentages") or [])
	if not rows:
		return
	positions = []
	for i, row in enumerate(rows, start=1):
		pos = int(row.idx) if getattr(row, "idx", None) else i
		positions.append(pos)
	if len(positions) != len(set(positions)):
		_validation_error(_("Monthly Distribution month positions must be unique (1–12)"))
	total = sum(flt(d.percentage_allocation) for d in rows)
	if flt(total, 2) != 100.0:
		_validation_error(
			_("Percentage Allocation should be equal to 100%") + f" ({flt(total, 2)!s}%)"
		)


def _validation_error(msg) -> None:
	"""Raise frappe.ValidationError when a site is bound; else ValueError for unit tests."""
	try:
		frappe.throw(msg)
	except RuntimeError:
		raise ValueError(str(msg)) from None


def infer_calendar_system_from_period_list(period_list, company: str | None = None) -> str:
	"""Detect Business Calendar for MD matching.

	Preference order:
	1. Explicit company Business Calendar
	2. Period key from BusinessPeriodEngine / FS adapter
	   (Jalali keys: ``j01_1405``, ``jq1_1405``, ``jh1_1405``, ``j1405``)
	3. Gregorian safe default

	Note: Gregorian keys like ``jan_2026`` also start with ``j`` — do not use a
	naive ``startswith("j")`` check.
	"""
	import re

	if company:
		return get_business_calendar_for_company(company)

	if period_list:
		first = period_list[0]
		key = str(first.get("key") if hasattr(first, "get") else getattr(first, "key", "") or "")
		if re.match(r"^j(\d{2}_\d{4}|[qh]\d_\d{4}|\d{4})$", key):
			return BUSINESS_CALENDAR_JALALI
	return BUSINESS_CALENDAR_GREGORIAN


def get_periodwise_distribution_data(
	distribution_id,
	period_list,
	periodicity,
	company: str | None = None,
):
	"""Drop-in replacement for stock ``get_periodwise_distribution_data``.

	Optional ``company`` selects Business Calendar. When omitted, calendar is
	inferred from period keys (Jalali engine keys, not ``jan_…``).
	"""
	doc = frappe.get_doc("Monthly Distribution", distribution_id)
	months_to_add = {"Yearly": 12, "Half-Yearly": 6, "Quarterly": 3, "Monthly": 1}[periodicity]
	calendar_system = infer_calendar_system_from_period_list(period_list, company)

	period_dict: dict[Any, float] = {}
	for d in period_list:
		period_dict[d.key] = resolve_distribution_percentage(
			doc,
			d.from_date,
			months_to_add,
			calendar_system=calendar_system,
		)
	return period_dict


def get_percentage(doc, start_date, period, company: str | None = None):
	"""Drop-in replacement for stock ``get_percentage``."""
	calendar_system = (
		get_business_calendar_for_company(company) if company else BUSINESS_CALENDAR_GREGORIAN
	)
	return resolve_distribution_percentage(
		doc, start_date, period, calendar_system=calendar_system
	)


def month_label_for_position(position: int, calendar_system: str, locale: str = "en") -> str:
	"""Presentation label for a business month position (not a storage key)."""
	idx = int(position) - 1
	if idx < 0 or idx > 11:
		raise ValueError(f"Invalid month position: {position}")
	if calendar_system == BUSINESS_CALENDAR_JALALI:
		if locale == "fa":
			from persian_calendar.calendar.period_labels import _JALALI_MONTH_NAMES_FA

			return _JALALI_MONTH_NAMES_FA[idx]
		return JALALI_MONTH_LABELS_EN[idx]
	return GREGORIAN_MONTH_LABELS[idx]
