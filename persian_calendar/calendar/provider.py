"""Calendar provider interface.

Providers are pure calendar arithmetic. They must not read user preferences,
write to the database, import ERPNext DocTypes, or mutate Frappe globals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from persian_calendar.calendar.types import (
	DEFAULT_LAST_DAY_POLICY,
	DateLike,
	Frequency,
	LastDayPolicy,
	Period,
	PeriodGrain,
)


class CalendarProvider(ABC):
	"""Abstract calendar system used for business period arithmetic."""

	name: str

	@abstractmethod
	def to_date(self, value: DateLike) -> date:
		"""Normalize Gregorian date or ISO string to ``datetime.date``."""

	@abstractmethod
	def add_days(self, d: DateLike, days: int) -> date: ...

	@abstractmethod
	def add_months(
		self,
		d: DateLike,
		months: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	) -> date: ...

	@abstractmethod
	def add_years(
		self,
		d: DateLike,
		years: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	) -> date: ...

	@abstractmethod
	def month_start(self, d: DateLike) -> date: ...

	@abstractmethod
	def month_end(self, d: DateLike) -> date: ...

	@abstractmethod
	def year_start(self, d: DateLike) -> date: ...

	@abstractmethod
	def year_end(self, d: DateLike) -> date: ...

	@abstractmethod
	def month_length(self, d: DateLike) -> int: ...

	@abstractmethod
	def is_month_end(self, d: DateLike) -> bool: ...

	@abstractmethod
	def is_year_end(self, d: DateLike) -> bool: ...

	@abstractmethod
	def month_diff(self, start: DateLike, end: DateLike) -> int:
		"""Inclusive month difference in this calendar (Frappe-compatible for Gregorian)."""

	@abstractmethod
	def year_diff(self, start: DateLike, end: DateLike) -> int:
		"""Calendar-year component difference: year(end) - year(start)."""

	@abstractmethod
	def period(self, d: DateLike, grain: PeriodGrain | str) -> Period: ...

	@abstractmethod
	def next_occurrence(
		self,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	) -> date:
		"""Advance ``d`` by one frequency step.

		When ``last_day_policy`` is omitted, uses ``PRESERVE_MONTH_END`` if ``d``
		is a month-end, otherwise ``CLAMP_DAY``.
		"""

	@abstractmethod
	def previous_occurrence(
		self,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	) -> date: ...
