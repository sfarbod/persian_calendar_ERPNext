"""Gregorian calendar provider.

Preserves Frappe / dateutil.relativedelta month semantics (day clamp) so that
Company Business Calendar = Gregorian matches stock ERPNext behaviour.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from persian_calendar.calendar.provider import CalendarProvider
from persian_calendar.calendar.types import (
	DEFAULT_LAST_DAY_POLICY,
	FREQUENCY_MONTHS,
	DateLike,
	Frequency,
	LastDayPolicy,
	Period,
	PeriodGrain,
)


def _parse_date(value: DateLike) -> date:
	if isinstance(value, date):
		return value
	if isinstance(value, str):
		# Accept YYYY-MM-DD (optionally with time — use date part only)
		return date.fromisoformat(value[:10])
	raise TypeError(f"Unsupported date value: {value!r}")


def _coerce_policy(policy: LastDayPolicy | str) -> LastDayPolicy:
	if isinstance(policy, LastDayPolicy):
		return policy
	return LastDayPolicy(policy)


def _coerce_grain(grain: PeriodGrain | str) -> PeriodGrain:
	if isinstance(grain, PeriodGrain):
		return grain
	return PeriodGrain(grain)


def _coerce_frequency(frequency: Frequency | str) -> Frequency:
	if isinstance(frequency, Frequency):
		return frequency
	return Frequency(frequency)


class GregorianCalendarProvider(CalendarProvider):
	"""Business calendar arithmetic using the Gregorian calendar."""

	name = "Gregorian"

	def to_date(self, value: DateLike) -> date:
		return _parse_date(value)

	def add_days(self, d: DateLike, days: int) -> date:
		return self.to_date(d) + timedelta(days=int(days))

	def add_months(
		self,
		d: DateLike,
		months: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	) -> date:
		src = self.to_date(d)
		policy = _coerce_policy(last_day_policy)
		preserve = policy == LastDayPolicy.PRESERVE_MONTH_END and self.is_month_end(src)
		result = src + relativedelta(months=int(months))
		if preserve:
			return self.month_end(result)
		return result

	def add_years(
		self,
		d: DateLike,
		years: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	) -> date:
		return self.add_months(d, int(years) * 12, last_day_policy=last_day_policy)

	def month_start(self, d: DateLike) -> date:
		src = self.to_date(d)
		return date(src.year, src.month, 1)

	def month_end(self, d: DateLike) -> date:
		src = self.to_date(d)
		last = calendar.monthrange(src.year, src.month)[1]
		return date(src.year, src.month, last)

	def year_start(self, d: DateLike) -> date:
		src = self.to_date(d)
		return date(src.year, 1, 1)

	def year_end(self, d: DateLike) -> date:
		src = self.to_date(d)
		return date(src.year, 12, 31)

	def month_length(self, d: DateLike) -> int:
		src = self.to_date(d)
		return calendar.monthrange(src.year, src.month)[1]

	def is_month_end(self, d: DateLike) -> bool:
		src = self.to_date(d)
		return src == self.month_end(src)

	def is_year_end(self, d: DateLike) -> bool:
		src = self.to_date(d)
		return src == self.year_end(src)

	def month_diff(self, start: DateLike, end: DateLike) -> int:
		# Inclusive, matching frappe.utils.month_diff
		st = self.to_date(start)
		ed = self.to_date(end)
		return (ed.year - st.year) * 12 + ed.month - st.month + 1

	def year_diff(self, start: DateLike, end: DateLike) -> int:
		return self.to_date(end).year - self.to_date(start).year

	def period(self, d: DateLike, grain: PeriodGrain | str) -> Period:
		src = self.to_date(d)
		grain = _coerce_grain(grain)

		if grain == PeriodGrain.MONTHLY:
			start = self.month_start(src)
			end = self.month_end(src)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=src.year,
				period_number=src.month,
				key=f"{src.year:04d}-{src.month:02d}",
				calendar_system="Gregorian",
			)

		if grain == PeriodGrain.QUARTERLY:
			q = (src.month - 1) // 3 + 1
			start_month = (q - 1) * 3 + 1
			start = date(src.year, start_month, 1)
			end = self.month_end(date(src.year, start_month + 2, 1))
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=src.year,
				period_number=q,
				key=f"{src.year:04d}-Q{q}",
				calendar_system="Gregorian",
			)

		if grain == PeriodGrain.HALF_YEARLY:
			h = 1 if src.month <= 6 else 2
			start_month = 1 if h == 1 else 7
			start = date(src.year, start_month, 1)
			end = self.month_end(date(src.year, start_month + 5, 1))
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=src.year,
				period_number=h,
				key=f"{src.year:04d}-H{h}",
				calendar_system="Gregorian",
			)

		if grain == PeriodGrain.YEARLY:
			start = self.year_start(src)
			end = self.year_end(src)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=src.year,
				period_number=1,
				key=f"{src.year:04d}",
				calendar_system="Gregorian",
			)

		raise ValueError(f"Unsupported period grain: {grain}")

	def _occurrence_policy(
		self, d: date, last_day_policy: LastDayPolicy | None
	) -> LastDayPolicy:
		if last_day_policy is not None:
			return _coerce_policy(last_day_policy)
		if self.is_month_end(d):
			return LastDayPolicy.PRESERVE_MONTH_END
		return LastDayPolicy.CLAMP_DAY

	def next_occurrence(
		self,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	) -> date:
		src = self.to_date(d)
		freq = _coerce_frequency(frequency)
		months = FREQUENCY_MONTHS[freq]
		policy = self._occurrence_policy(src, last_day_policy)
		return self.add_months(src, months, last_day_policy=policy)

	def previous_occurrence(
		self,
		d: DateLike,
		frequency: Frequency | str,
		*,
		last_day_policy: LastDayPolicy | None = None,
	) -> date:
		src = self.to_date(d)
		freq = _coerce_frequency(frequency)
		months = FREQUENCY_MONTHS[freq]
		policy = self._occurrence_policy(src, last_day_policy)
		return self.add_months(src, -months, last_day_policy=policy)
