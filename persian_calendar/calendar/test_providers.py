"""Unit tests for Gregorian and Jalali calendar providers.

These tests do not require a Frappe site database.
"""

from __future__ import annotations

import unittest
from datetime import date

from dateutil.relativedelta import relativedelta

from persian_calendar.calendar.providers.gregorian import GregorianCalendarProvider
from persian_calendar.calendar.providers.jalali import JalaliCalendarProvider
from persian_calendar.calendar.types import Frequency, LastDayPolicy, PeriodGrain

import jdatetime


def _g(y: int, m: int, d: int) -> date:
	return date(y, m, d)


def _j_to_g(jy: int, jm: int, jd: int) -> date:
	return jdatetime.date(jy, jm, jd).togregorian()


class TestGregorianProvider(unittest.TestCase):
	def setUp(self):
		self.cal = GregorianCalendarProvider()

	def test_add_months_normal(self):
		self.assertEqual(self.cal.add_months(_g(2026, 1, 15), 1), _g(2026, 2, 15))

	def test_add_months_short_month_clamp(self):
		# Matches frappe / relativedelta
		expected = _g(2026, 1, 31) + relativedelta(months=1)
		self.assertEqual(self.cal.add_months(_g(2026, 1, 31), 1), expected)
		self.assertEqual(expected, _g(2026, 2, 28))

	def test_preserve_month_end(self):
		result = self.cal.add_months(
			_g(2026, 1, 31), 1, last_day_policy=LastDayPolicy.PRESERVE_MONTH_END
		)
		self.assertEqual(result, _g(2026, 2, 28))
		result2 = self.cal.add_months(
			_g(2026, 1, 31), 2, last_day_policy=LastDayPolicy.PRESERVE_MONTH_END
		)
		self.assertEqual(result2, _g(2026, 3, 31))

	def test_leap_year_feb(self):
		self.assertEqual(self.cal.month_length(_g(2024, 2, 1)), 29)
		self.assertEqual(self.cal.month_end(_g(2024, 2, 10)), _g(2024, 2, 29))
		self.assertEqual(self.cal.month_length(_g(2025, 2, 1)), 28)

	def test_negative_months(self):
		self.assertEqual(self.cal.add_months(_g(2026, 3, 15), -1), _g(2026, 2, 15))

	def test_add_years(self):
		self.assertEqual(self.cal.add_years(_g(2024, 2, 29), 1), _g(2025, 2, 28))
		self.assertEqual(
			self.cal.add_years(_g(2024, 2, 29), 1, last_day_policy=LastDayPolicy.PRESERVE_MONTH_END),
			_g(2025, 2, 28),
		)

	def test_period_boundaries(self):
		p = self.cal.period(_g(2026, 3, 15), PeriodGrain.MONTHLY)
		self.assertEqual(p.start, _g(2026, 3, 1))
		self.assertEqual(p.end, _g(2026, 3, 31))
		self.assertEqual(p.key, "2026-03")
		self.assertEqual(p.year, 2026)
		self.assertEqual(p.period_number, 3)

		q = self.cal.period(_g(2026, 3, 15), PeriodGrain.QUARTERLY)
		self.assertEqual(q.key, "2026-Q1")
		self.assertEqual(q.start, _g(2026, 1, 1))
		self.assertEqual(q.end, _g(2026, 3, 31))

	def test_month_diff_inclusive(self):
		# Frappe-compatible inclusive month_diff
		self.assertEqual(self.cal.month_diff(_g(2026, 1, 1), _g(2026, 1, 31)), 1)
		self.assertEqual(self.cal.month_diff(_g(2026, 1, 15), _g(2026, 3, 1)), 3)

	def test_is_month_end(self):
		self.assertTrue(self.cal.is_month_end(_g(2026, 1, 31)))
		self.assertFalse(self.cal.is_month_end(_g(2026, 1, 30)))

	def test_next_occurrence_preserves_month_end(self):
		start = _g(2026, 1, 31)
		nxt = self.cal.next_occurrence(start, Frequency.MONTHLY)
		self.assertEqual(nxt, _g(2026, 2, 28))

	def test_iso_string_input(self):
		self.assertEqual(self.cal.month_start("2026-03-15"), _g(2026, 3, 1))

	def test_matches_frappe_add_months(self):
		for months in (1, 2, 6, 12, -3):
			src = _g(2025, 1, 31)
			self.assertEqual(
				self.cal.add_months(src, months),
				src + relativedelta(months=months),
			)


class TestJalaliProvider(unittest.TestCase):
	def setUp(self):
		self.cal = JalaliCalendarProvider()

	def test_farvardin_31(self):
		# 1405-01-15
		g = _j_to_g(1405, 1, 15)
		self.assertEqual(self.cal.month_length(g), 31)
		self.assertEqual(self.cal.month_end(g), _j_to_g(1405, 1, 31))

	def test_shahrivar_31(self):
		g = _j_to_g(1405, 6, 1)
		self.assertEqual(self.cal.month_length(g), 31)
		self.assertEqual(self.cal.month_end(g), _j_to_g(1405, 6, 31))

	def test_mehr_30(self):
		g = _j_to_g(1405, 7, 1)
		self.assertEqual(self.cal.month_length(g), 30)
		self.assertEqual(self.cal.month_end(g), _j_to_g(1405, 7, 30))

	def test_bahman_30(self):
		g = _j_to_g(1405, 11, 1)
		self.assertEqual(self.cal.month_length(g), 30)

	def test_esfand_29_non_leap(self):
		# 1404 and 1405 are non-leap
		g = _j_to_g(1404, 12, 1)
		self.assertEqual(self.cal.month_length(g), 29)
		self.assertEqual(self.cal.month_end(g), _j_to_g(1404, 12, 29))

	def test_esfand_30_leap(self):
		# 1403 is leap
		g = _j_to_g(1403, 12, 1)
		self.assertEqual(self.cal.month_length(g), 30)
		self.assertEqual(self.cal.month_end(g), _j_to_g(1403, 12, 30))

	def test_same_day_monthly_sequence(self):
		# Example 1 from spec: 1405-01-01 monthly
		start = _j_to_g(1405, 1, 1)
		dates = [start]
		cur = start
		for _ in range(3):
			cur = self.cal.add_months(cur, 1)
			dates.append(cur)
		expected = [_j_to_g(1405, m, 1) for m in (1, 2, 3, 4)]
		self.assertEqual(dates, expected)

	def test_clamp_farvardin_31_plus_six(self):
		# 1405-01-31 + 6 months → 1405-07-30
		start = _j_to_g(1405, 1, 31)
		result = self.cal.add_months(start, 6, last_day_policy=LastDayPolicy.CLAMP_DAY)
		self.assertEqual(result, _j_to_g(1405, 7, 30))

	def test_preserve_month_end_sequence(self):
		# Example 2: 1404-12-29 + monthly PRESERVE_MONTH_END
		start = _j_to_g(1404, 12, 29)
		self.assertTrue(self.cal.is_month_end(start))
		expected_j = [
			(1404, 12, 29),
			(1405, 1, 31),
			(1405, 2, 31),
			(1405, 3, 31),
			(1405, 4, 31),
			(1405, 5, 31),
			(1405, 6, 31),
			(1405, 7, 30),
		]
		cur = start
		got = [cur]
		for _ in range(7):
			cur = self.cal.add_months(cur, 1, last_day_policy=LastDayPolicy.PRESERVE_MONTH_END)
			got.append(cur)
		expected = [_j_to_g(*t) for t in expected_j]
		self.assertEqual(got, expected)

	def test_negative_months(self):
		start = _j_to_g(1405, 2, 1)
		self.assertEqual(self.cal.add_months(start, -1), _j_to_g(1405, 1, 1))

	def test_year_boundary(self):
		start = _j_to_g(1404, 12, 15)
		self.assertEqual(self.cal.add_months(start, 1), _j_to_g(1405, 1, 15))
		self.assertEqual(self.cal.year_start(start), _j_to_g(1404, 1, 1))
		self.assertEqual(self.cal.year_end(start), _j_to_g(1404, 12, 29))

	def test_month_start_end(self):
		g = _j_to_g(1405, 3, 10)
		self.assertEqual(self.cal.month_start(g), _j_to_g(1405, 3, 1))
		self.assertEqual(self.cal.month_end(g), _j_to_g(1405, 3, 31))

	def test_year_start_end(self):
		g = _j_to_g(1405, 5, 10)
		self.assertEqual(self.cal.year_start(g), _j_to_g(1405, 1, 1))
		self.assertEqual(self.cal.year_end(g), _j_to_g(1405, 12, 29))

	def test_month_diff_year_diff(self):
		a = _j_to_g(1405, 1, 1)
		b = _j_to_g(1405, 3, 1)
		self.assertEqual(self.cal.month_diff(a, b), 3)
		self.assertEqual(self.cal.year_diff(a, _j_to_g(1406, 1, 1)), 1)

	def test_period_monthly_and_quarterly(self):
		g = _j_to_g(1405, 2, 10)
		p = self.cal.period(g, PeriodGrain.MONTHLY)
		self.assertEqual(p.key, "1405-02")
		self.assertEqual(p.year, 1405)
		self.assertEqual(p.period_number, 2)
		self.assertEqual(p.start, _j_to_g(1405, 2, 1))
		self.assertEqual(p.end, _j_to_g(1405, 2, 31))

		q = self.cal.period(g, PeriodGrain.QUARTERLY)
		self.assertEqual(q.key, "1405-Q1")
		self.assertEqual(q.start, _j_to_g(1405, 1, 1))
		self.assertEqual(q.end, _j_to_g(1405, 3, 31))

	def test_add_years(self):
		start = _j_to_g(1404, 12, 29)
		# non-leap → leap clamp: 1404-12-29 + 1 year → 1405-12-29 (1405 non-leap, day 29 ok)
		self.assertEqual(self.cal.add_years(start, 1), _j_to_g(1405, 12, 29))

	def test_returns_gregorian(self):
		result = self.cal.add_months(_j_to_g(1405, 1, 1), 1)
		self.assertIsInstance(result, date)
		# Must equal known Gregorian for 1405-02-01
		self.assertEqual(result, _j_to_g(1405, 2, 1))


class TestJalaliProviderLeapAndEdge(unittest.TestCase):
	"""Additional edge cases for hardening."""

	def setUp(self):
		self.cal = JalaliCalendarProvider()

	def test_leap_esfand_add_years_to_non_leap(self):
		# 1403-12-30 (leap Esfand) + 1 year → 1404-12-29 (non-leap clamp)
		start = _j_to_g(1403, 12, 30)
		result = self.cal.add_years(start, 1)
		self.assertEqual(result, _j_to_g(1404, 12, 29))

	def test_leap_esfand_preserve_month_end_across_years(self):
		# 1403-12-30 (last day, leap) + 1 year PRESERVE → 1404-12-29 (last day, non-leap)
		start = _j_to_g(1403, 12, 30)
		self.assertTrue(self.cal.is_month_end(start))
		result = self.cal.add_years(start, 1, last_day_policy=LastDayPolicy.PRESERVE_MONTH_END)
		self.assertEqual(result, _j_to_g(1404, 12, 29))
		self.assertTrue(self.cal.is_month_end(result))

	def test_negative_months_across_year(self):
		# 1405-01-01 - 1 month → 1404-12-01
		start = _j_to_g(1405, 1, 1)
		self.assertEqual(self.cal.add_months(start, -1), _j_to_g(1404, 12, 1))

	def test_negative_months_large(self):
		# 1405-03-15 - 15 months → 1403-12-15
		start = _j_to_g(1405, 3, 15)
		self.assertEqual(self.cal.add_months(start, -15), _j_to_g(1403, 12, 15))

	def test_period_calendar_system(self):
		g = _j_to_g(1405, 1, 15)
		p = self.cal.period(g, PeriodGrain.MONTHLY)
		self.assertEqual(p.calendar_system, "Jalali")

	def test_gregorian_period_calendar_system(self):
		g = GregorianCalendarProvider()
		p = g.period(date(2026, 3, 15), PeriodGrain.MONTHLY)
		self.assertEqual(p.calendar_system, "Gregorian")

	def test_is_year_end_leap(self):
		# 1403-12-30 is last day of leap year
		self.assertTrue(self.cal.is_year_end(_j_to_g(1403, 12, 30)))
		self.assertFalse(self.cal.is_year_end(_j_to_g(1403, 12, 29)))

	def test_is_year_end_non_leap(self):
		# 1404-12-29 is last day of non-leap year
		self.assertTrue(self.cal.is_year_end(_j_to_g(1404, 12, 29)))

	def test_next_occurrence_quarterly(self):
		start = _j_to_g(1405, 1, 1)
		nxt = self.cal.next_occurrence(start, Frequency.QUARTERLY)
		self.assertEqual(nxt, _j_to_g(1405, 4, 1))

	def test_previous_occurrence_monthly(self):
		start = _j_to_g(1405, 3, 1)
		prev = self.cal.previous_occurrence(start, Frequency.MONTHLY)
		self.assertEqual(prev, _j_to_g(1405, 2, 1))


class TestCalendarEngineForCalendar(unittest.TestCase):
	def test_for_calendar_names(self):
		from persian_calendar.calendar.engine import CalendarEngine

		self.assertEqual(CalendarEngine.for_calendar("Gregorian").name, "Gregorian")
		self.assertEqual(CalendarEngine.for_calendar("Jalali").name, "Jalali")
		self.assertEqual(CalendarEngine.gregorian().name, "Gregorian")

	def test_unsupported(self):
		from persian_calendar.calendar.engine import CalendarEngine

		with self.assertRaises(ValueError):
			CalendarEngine.for_calendar("Hijri")


if __name__ == "__main__":
	unittest.main()
