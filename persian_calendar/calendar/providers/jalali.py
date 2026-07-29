"""Jalali (Persian) calendar provider.

Internally converts Gregorian dates to Jalali parts via jdatetime.
All public return values are Gregorian ``datetime.date`` objects.
"""

from __future__ import annotations

from datetime import date, timedelta

import jdatetime

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


def _g_to_j(g: date) -> jdatetime.date:
	return jdatetime.date.fromgregorian(date=g)


def _j_to_g(j: jdatetime.date) -> date:
	return j.togregorian()


def _is_jalali_leap(year: int) -> bool:
	"""Return True if Jalali ``year`` has a 30-day Esfand."""
	return jdatetime.date(year, 1, 1).isleap()


def _jalali_month_length(year: int, month: int) -> int:
	if month <= 6:
		return 31
	if month <= 11:
		return 30
	return 30 if _is_jalali_leap(year) else 29


def _jalali_add_months(j: jdatetime.date, months: int) -> jdatetime.date:
	"""Add months in Jalali space and clamp day to destination month length."""
	total = (j.year * 12 + (j.month - 1)) + int(months)
	year, month0 = divmod(total, 12)
	month = month0 + 1
	day = min(j.day, _jalali_month_length(year, month))
	return jdatetime.date(year, month, day)


class JalaliCalendarProvider(CalendarProvider):
	"""Business calendar arithmetic using the Jalali calendar."""

	name = "Jalali"

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
		j = _g_to_j(src)
		preserve = policy == LastDayPolicy.PRESERVE_MONTH_END and self.is_month_end(src)
		j2 = _jalali_add_months(j, months)
		if preserve:
			last = _jalali_month_length(j2.year, j2.month)
			j2 = jdatetime.date(j2.year, j2.month, last)
		return _j_to_g(j2)

	def add_years(
		self,
		d: DateLike,
		years: int,
		last_day_policy: LastDayPolicy = DEFAULT_LAST_DAY_POLICY,
	) -> date:
		return self.add_months(d, int(years) * 12, last_day_policy=last_day_policy)

	def month_start(self, d: DateLike) -> date:
		j = _g_to_j(self.to_date(d))
		return _j_to_g(jdatetime.date(j.year, j.month, 1))

	def month_end(self, d: DateLike) -> date:
		j = _g_to_j(self.to_date(d))
		last = _jalali_month_length(j.year, j.month)
		return _j_to_g(jdatetime.date(j.year, j.month, last))

	def year_start(self, d: DateLike) -> date:
		j = _g_to_j(self.to_date(d))
		return _j_to_g(jdatetime.date(j.year, 1, 1))

	def year_end(self, d: DateLike) -> date:
		j = _g_to_j(self.to_date(d))
		last = _jalali_month_length(j.year, 12)
		return _j_to_g(jdatetime.date(j.year, 12, last))

	def month_length(self, d: DateLike) -> int:
		j = _g_to_j(self.to_date(d))
		return _jalali_month_length(j.year, j.month)

	def is_month_end(self, d: DateLike) -> bool:
		src = self.to_date(d)
		return src == self.month_end(src)

	def is_year_end(self, d: DateLike) -> bool:
		src = self.to_date(d)
		return src == self.year_end(src)

	def month_diff(self, start: DateLike, end: DateLike) -> int:
		# Inclusive month count in Jalali space (same shape as frappe.utils.month_diff)
		js = _g_to_j(self.to_date(start))
		je = _g_to_j(self.to_date(end))
		return (je.year - js.year) * 12 + je.month - js.month + 1

	def year_diff(self, start: DateLike, end: DateLike) -> int:
		return _g_to_j(self.to_date(end)).year - _g_to_j(self.to_date(start)).year

	def period(self, d: DateLike, grain: PeriodGrain | str) -> Period:
		src = self.to_date(d)
		j = _g_to_j(src)
		grain = _coerce_grain(grain)

		if grain == PeriodGrain.MONTHLY:
			start = self.month_start(src)
			end = self.month_end(src)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=j.year,
				period_number=j.month,
				key=f"{j.year:04d}-{j.month:02d}",
			)

		if grain == PeriodGrain.QUARTERLY:
			q = (j.month - 1) // 3 + 1
			start_month = (q - 1) * 3 + 1
			start = _j_to_g(jdatetime.date(j.year, start_month, 1))
			end_month = start_month + 2
			end = _j_to_g(
				jdatetime.date(j.year, end_month, _jalali_month_length(j.year, end_month))
			)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=j.year,
				period_number=q,
				key=f"{j.year:04d}-Q{q}",
			)

		if grain == PeriodGrain.HALF_YEARLY:
			h = 1 if j.month <= 6 else 2
			start_month = 1 if h == 1 else 7
			start = _j_to_g(jdatetime.date(j.year, start_month, 1))
			end_month = start_month + 5
			end = _j_to_g(
				jdatetime.date(j.year, end_month, _jalali_month_length(j.year, end_month))
			)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=j.year,
				period_number=h,
				key=f"{j.year:04d}-H{h}",
			)

		if grain == PeriodGrain.YEARLY:
			start = self.year_start(src)
			end = self.year_end(src)
			return Period(
				start=start,
				end=end,
				grain=grain,
				year=j.year,
				period_number=1,
				key=f"{j.year:04d}",
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
