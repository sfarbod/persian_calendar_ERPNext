"""Business Period label formatter — presentation layer for period lists.

This module generates display labels for ``BusinessPeriod`` objects.
Labels are locale-aware and calendar-system-aware, but never modify
period boundaries or keys.

Supports server-side usage for XLSX/CSV export and chart labels.
"""

from __future__ import annotations

from datetime import date

from persian_calendar.calendar.period_engine import BusinessPeriod

_JALALI_MONTH_NAMES_FA = [
	"فروردین",
	"اردیبهشت",
	"خرداد",
	"تیر",
	"مرداد",
	"شهریور",
	"مهر",
	"آبان",
	"آذر",
	"دی",
	"بهمن",
	"اسفند",
]

_JALALI_MONTH_NAMES_EN = [
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
]


def format_period_label(
	period: BusinessPeriod,
	*,
	locale: str = "fa",
	accumulated: bool = False,
	accumulated_from: date | None = None,
) -> str:
	"""Generate a human-readable label for a business period.

	Args:
		period: The ``BusinessPeriod`` to label.
		locale: ``"fa"`` for Persian, ``"en"`` for English.
		accumulated: If True, label spans from *accumulated_from* to *to_date*.
		accumulated_from: Override the start date for accumulated labels.

	Returns:
		Display string suitable for report columns and chart axes.
	"""
	if period.calendar_system == "Jalali":
		return _jalali_label(period, locale, accumulated, accumulated_from)
	return _gregorian_label(period, locale, accumulated, accumulated_from)


def _gregorian_label(
	period: BusinessPeriod,
	locale: str,
	accumulated: bool,
	accumulated_from: date | None,
) -> str:
	from_d = accumulated_from or period.from_date
	to_d = period.to_date
	p = period.periodicity

	if p == "Monthly" and not accumulated:
		return to_d.strftime("%b %Y")

	if p == "Yearly":
		fy = from_d.strftime("%Y")
		ty = to_d.strftime("%Y")
		return fy if fy == ty else f"{fy}-{ty}"

	return f"{from_d.strftime('%b %y')}-{to_d.strftime('%b %y')}"


def _jalali_label(
	period: BusinessPeriod,
	locale: str,
	accumulated: bool,
	accumulated_from: date | None,
) -> str:
	import jdatetime

	from_d = accumulated_from or period.from_date
	to_d = period.to_date
	p = period.periodicity

	j_to = jdatetime.date.fromgregorian(date=to_d)
	j_from = jdatetime.date.fromgregorian(date=from_d)

	names = _JALALI_MONTH_NAMES_FA if locale == "fa" else _JALALI_MONTH_NAMES_EN

	if p == "Monthly" and not accumulated:
		return f"{names[j_to.month - 1]} {j_to.year}"

	if p == "Quarterly" and not accumulated:
		q = (j_to.month - 1) // 3 + 1
		if locale == "fa":
			return f"سه‌ماهه {q} - {j_to.year}"
		return f"Q{q} {j_to.year}"

	if p == "Half-Yearly" and not accumulated:
		h = 1 if j_to.month <= 6 else 2
		if locale == "fa":
			return f"نیمه {h} - {j_to.year}"
		return f"H{h} {j_to.year}"

	if p == "Yearly":
		fy = str(j_from.year)
		ty = str(j_to.year)
		return fy if fy == ty else f"{fy}-{ty}"

	# Accumulated / range label
	from_name = names[j_from.month - 1]
	to_name = names[j_to.month - 1]
	fy = str(j_from.year)[-2:]
	ty = str(j_to.year)[-2:]
	return f"{from_name} {fy}-{to_name} {ty}"
