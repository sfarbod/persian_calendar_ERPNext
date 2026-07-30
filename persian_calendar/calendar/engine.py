"""Calendar Engine — resolve providers and expose business calendar APIs.

Business Calendar is never resolved from the current user's Display preference.
"""

from __future__ import annotations

from persian_calendar.calendar.provider import CalendarProvider
from persian_calendar.calendar.providers.gregorian import GregorianCalendarProvider
from persian_calendar.calendar.providers.jalali import JalaliCalendarProvider
from persian_calendar.calendar.types import (
	DEFAULT_LAST_DAY_POLICY,
	DateLike,
	Frequency,
	LastDayPolicy,
	Period,
	PeriodGrain,
)

_GREGORIAN = GregorianCalendarProvider()
_JALALI = JalaliCalendarProvider()

_PROVIDERS: dict[str, CalendarProvider] = {
	"Gregorian": _GREGORIAN,
	"Jalali": _JALALI,
}


class CalendarEngine:
	"""Façade over calendar providers for business period arithmetic."""

	@staticmethod
	def for_calendar(name: str) -> CalendarProvider:
		"""Return the provider for an explicit calendar system name."""
		if not name:
			return _GREGORIAN
		key = str(name).strip()
		provider = _PROVIDERS.get(key)
		if provider is None:
			raise ValueError(f"Unsupported business calendar: {name!r}")
		return provider

	@staticmethod
	def gregorian() -> CalendarProvider:
		"""Escape hatch: always use Gregorian (stock ERPNext semantics)."""
		return _GREGORIAN

	@staticmethod
	def jalali() -> CalendarProvider:
		return _JALALI

	@staticmethod
	def for_company(company: str | None = None) -> CalendarProvider:
		"""Resolve Business Calendar for a company.

		Delegates to ``persian_calendar.calendar.resolve.get_business_calendar_for_company``.
		Never uses the current user's Display Calendar preference.
		"""
		from persian_calendar.calendar.resolve import get_business_calendar_for_company

		return CalendarEngine.for_calendar(get_business_calendar_for_company(company))

	@staticmethod
	def add_days(provider: CalendarProvider, d: DateLike, days: int):
		return provider.add_days(d, days)

	@staticmethod
	def add_months(
		provider: CalendarProvider,
		d: DateLike,
		months: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	):
		return provider.add_months(d, months, last_day_policy=last_day_policy)

	@staticmethod
	def add_years(
		provider: CalendarProvider,
		d: DateLike,
		years: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	):
		return provider.add_years(d, years, last_day_policy=last_day_policy)

	@staticmethod
	def month_start(provider: CalendarProvider, d: DateLike):
		return provider.month_start(d)

	@staticmethod
	def month_end(provider: CalendarProvider, d: DateLike):
		return provider.month_end(d)

	@staticmethod
	def year_start(provider: CalendarProvider, d: DateLike):
		return provider.year_start(d)

	@staticmethod
	def year_end(provider: CalendarProvider, d: DateLike):
		return provider.year_end(d)

	@staticmethod
	def month_length(provider: CalendarProvider, d: DateLike) -> int:
		return provider.month_length(d)

	@staticmethod
	def is_month_end(provider: CalendarProvider, d: DateLike) -> bool:
		return provider.is_month_end(d)

	@staticmethod
	def is_year_end(provider: CalendarProvider, d: DateLike) -> bool:
		return provider.is_year_end(d)

	@staticmethod
	def month_diff(provider: CalendarProvider, start: DateLike, end: DateLike) -> int:
		return provider.month_diff(start, end)

	@staticmethod
	def year_diff(provider: CalendarProvider, start: DateLike, end: DateLike) -> int:
		return provider.year_diff(start, end)

	@staticmethod
	def period(provider: CalendarProvider, d: DateLike, grain: PeriodGrain | str) -> Period:
		return provider.period(d, grain)

	@staticmethod
	def next_occurrence(
		provider: CalendarProvider,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	):
		return provider.next_occurrence(d, frequency, last_day_policy=last_day_policy)

	@staticmethod
	def previous_occurrence(
		provider: CalendarProvider,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	):
		return provider.previous_occurrence(d, frequency, last_day_policy=last_day_policy)
