"""Business Period Engine — canonical period-list generation.

Generates typed period lists for any supported periodicity and calendar system.
This is the single source of truth for business period boundaries; ERPNext report
adapters should consume this engine rather than reimplementing period arithmetic.

Providers are pure calendar arithmetic; this engine adds scheduling semantics
(fiscal year alignment, partial periods, accumulated-value labelling).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.provider import CalendarProvider
from persian_calendar.calendar.types import DateLike, PeriodGrain

Periodicity = Literal["Monthly", "Quarterly", "Half-Yearly", "Yearly"]

_MONTHS_MAP: dict[str, int] = {
	"Monthly": 1,
	"Quarterly": 3,
	"Half-Yearly": 6,
	"Yearly": 12,
}


def _to_date(value: DateLike) -> date:
	if isinstance(value, date):
		return value
	return date.fromisoformat(str(value)[:10])


@dataclass(frozen=True)
class BusinessPeriod:
	"""A single period in a business period list.

	All dates are Gregorian storage dates. ``key`` is a stable, locale-neutral
	identifier suitable for use as a dict key or column fieldname.
	"""

	from_date: date
	to_date: date
	key: str
	label: str
	periodicity: str
	calendar_system: str
	year: int
	period_number: int


@dataclass
class BusinessPeriodRequest:
	"""Input parameters for period generation."""

	start_date: DateLike
	end_date: DateLike
	periodicity: Periodicity
	company: str | None = None
	provider: CalendarProvider | None = None


class BusinessPeriodEngine:
	"""Canonical period-list generator for all ERPNext consumers.

	Usage::

		periods = BusinessPeriodEngine.generate(
		    start_date="2026-03-21",
		    end_date="2027-03-20",
		    periodicity="Monthly",
		    company="My Company",
		)
	"""

	@staticmethod
	def generate(
		start_date: DateLike,
		end_date: DateLike,
		periodicity: Periodicity,
		*,
		company: str | None = None,
		provider: CalendarProvider | None = None,
	) -> list[BusinessPeriod]:
		"""Generate a list of business periods.

		Args:
			start_date: First day of the overall range (Gregorian).
			end_date: Last day of the overall range (Gregorian).
			periodicity: One of Monthly, Quarterly, Half-Yearly, Yearly.
			company: Used to resolve Business Calendar (ignored when *provider* given).
			provider: Explicit ``CalendarProvider`` (bypasses company resolution).

		Returns:
			Ordered list of ``BusinessPeriod`` objects covering the range.
		"""
		cal = provider or CalendarEngine.for_company(company)
		sd = _to_date(start_date)
		ed = _to_date(end_date)

		if ed < sd:
			return []

		months_to_add = _MONTHS_MAP[periodicity]
		total_months = _month_span(cal, sd, ed)
		n_periods = max(1, math.ceil(total_months / months_to_add))

		periods: list[BusinessPeriod] = []
		cursor = sd
		for i in range(n_periods):
			period_end = cal.add_days(cal.add_months(cursor, months_to_add), -1)

			if period_end > ed:
				period_end = ed

			key = _make_key(cal, period_end, periodicity)
			year, period_number = _year_and_number(cal, period_end, periodicity)

			periods.append(
				BusinessPeriod(
					from_date=cursor,
					to_date=period_end,
					key=key,
					label="",  # labels are a presentation concern — see period_labels.py
					periodicity=periodicity,
					calendar_system=cal.name,
					year=year,
					period_number=period_number,
				)
			)

			cursor = cal.add_days(period_end, 1)
			if cursor > ed:
				break

		return periods

	@staticmethod
	def for_company(company: str | None = None) -> CalendarProvider:
		"""Convenience: resolve Business Calendar provider for *company*."""
		return CalendarEngine.for_company(company)


def _month_span(cal: CalendarProvider, start: date, end: date) -> int:
	"""Inclusive month count in the provider's calendar system."""
	return cal.month_diff(start, end)


def _make_key(cal: CalendarProvider, to_date: date, periodicity: str) -> str:
	"""Stable, locale-neutral period key."""
	if cal.name == "Jalali":
		return _jalali_key(to_date, periodicity)
	return _gregorian_key(to_date, periodicity)


def _gregorian_key(d: date, periodicity: str) -> str:
	if periodicity == "Monthly":
		return d.strftime("%b_%Y").lower()
	if periodicity == "Quarterly":
		q = (d.month - 1) // 3 + 1
		return f"q{q}_{d.year}"
	if periodicity == "Half-Yearly":
		h = 1 if d.month <= 6 else 2
		return f"h{h}_{d.year}"
	return f"{d.year}"


def _jalali_key(d: date, periodicity: str) -> str:
	import jdatetime

	j = jdatetime.date.fromgregorian(date=d)
	if periodicity == "Monthly":
		return f"j{j.month:02d}_{j.year}"
	if periodicity == "Quarterly":
		q = (j.month - 1) // 3 + 1
		return f"jq{q}_{j.year}"
	if periodicity == "Half-Yearly":
		h = 1 if j.month <= 6 else 2
		return f"jh{h}_{j.year}"
	return f"j{j.year}"


def _year_and_number(cal: CalendarProvider, d: date, periodicity: str) -> tuple[int, int]:
	"""Return (year, period_number) in the provider's calendar."""
	if cal.name == "Jalali":
		import jdatetime

		j = jdatetime.date.fromgregorian(date=d)
		y = j.year
		m = j.month
	else:
		y = d.year
		m = d.month

	if periodicity == "Monthly":
		return y, m
	if periodicity == "Quarterly":
		return y, (m - 1) // 3 + 1
	if periodicity == "Half-Yearly":
		return y, 1 if m <= 6 else 2
	return y, 1
