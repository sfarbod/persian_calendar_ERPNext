"""Unit tests for BusinessPeriodEngine and period labels.

These tests do not require a Frappe site database — they use explicit providers.
"""

from __future__ import annotations

import unittest
from datetime import date

import jdatetime

from persian_calendar.calendar.period_engine import BusinessPeriod, BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.providers.gregorian import GregorianCalendarProvider
from persian_calendar.calendar.providers.jalali import JalaliCalendarProvider


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


G = GregorianCalendarProvider()
J = JalaliCalendarProvider()


class TestGregorianPeriodEngine(unittest.TestCase):
	"""Gregorian period generation — must match stock ERPNext behavior."""

	def test_monthly_full_year(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Monthly", provider=G
		)
		self.assertEqual(len(periods), 12)
		self.assertEqual(periods[0].from_date, date(2026, 1, 1))
		self.assertEqual(periods[0].to_date, date(2026, 1, 31))
		self.assertEqual(periods[11].from_date, date(2026, 12, 1))
		self.assertEqual(periods[11].to_date, date(2026, 12, 31))

	def test_quarterly_full_year(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Quarterly", provider=G
		)
		self.assertEqual(len(periods), 4)
		self.assertEqual(periods[0].to_date, date(2026, 3, 31))
		self.assertEqual(periods[1].from_date, date(2026, 4, 1))
		self.assertEqual(periods[3].to_date, date(2026, 12, 31))

	def test_half_yearly(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Half-Yearly", provider=G
		)
		self.assertEqual(len(periods), 2)
		self.assertEqual(periods[0].to_date, date(2026, 6, 30))
		self.assertEqual(periods[1].to_date, date(2026, 12, 31))

	def test_yearly(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Yearly", provider=G
		)
		self.assertEqual(len(periods), 1)
		self.assertEqual(periods[0].from_date, date(2026, 1, 1))
		self.assertEqual(periods[0].to_date, date(2026, 12, 31))

	def test_fiscal_year_not_starting_january(self):
		# April-based fiscal year
		periods = BusinessPeriodEngine.generate(
			date(2026, 4, 1), date(2027, 3, 31), "Monthly", provider=G
		)
		self.assertEqual(len(periods), 12)
		self.assertEqual(periods[0].from_date, date(2026, 4, 1))
		self.assertEqual(periods[0].to_date, date(2026, 4, 30))
		self.assertEqual(periods[11].to_date, date(2027, 3, 31))

	def test_leap_february(self):
		periods = BusinessPeriodEngine.generate(
			date(2028, 1, 1), date(2028, 12, 31), "Monthly", provider=G
		)
		feb = periods[1]
		self.assertEqual(feb.to_date, date(2028, 2, 29))

	def test_partial_range(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 3, 15), date(2026, 5, 20), "Monthly", provider=G
		)
		self.assertGreaterEqual(len(periods), 2)
		self.assertEqual(periods[0].from_date, date(2026, 3, 15))
		self.assertEqual(periods[-1].to_date, date(2026, 5, 20))

	def test_empty_range(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 5, 1), date(2026, 4, 1), "Monthly", provider=G
		)
		self.assertEqual(len(periods), 0)

	def test_keys_are_unique(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Monthly", provider=G
		)
		keys = [p.key for p in periods]
		self.assertEqual(len(keys), len(set(keys)))

	def test_calendar_system(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 3, 31), "Monthly", provider=G
		)
		for p in periods:
			self.assertEqual(p.calendar_system, "Gregorian")

	def test_quarterly_keys(self):
		periods = BusinessPeriodEngine.generate(
			date(2026, 1, 1), date(2026, 12, 31), "Quarterly", provider=G
		)
		self.assertEqual(periods[0].key, "q1_2026")
		self.assertEqual(periods[3].key, "q4_2026")


class TestJalaliPeriodEngine(unittest.TestCase):
	"""Jalali period generation — stored dates are Gregorian."""

	def _fy_start(self, jy):
		return _j(jy, 1, 1)

	def _fy_end(self, jy):
		return _j(jy, 12, 30 if jdatetime.date(jy, 1, 1).isleap() else 29)

	def test_monthly_full_jalali_year(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Monthly", provider=J
		)
		self.assertEqual(len(periods), 12)
		# First 6 months: 31 days
		for i in range(6):
			self.assertEqual(periods[i].from_date, _j(1405, i + 1, 1))
			self.assertEqual(periods[i].to_date, _j(1405, i + 1, 31))
		# Months 7-11: 30 days
		for i in range(6, 11):
			self.assertEqual(periods[i].from_date, _j(1405, i + 1, 1))
			self.assertEqual(periods[i].to_date, _j(1405, i + 1, 30))
		# Esfand non-leap: 29 days
		self.assertEqual(periods[11].to_date, _j(1405, 12, 29))

	def test_monthly_leap_year(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1403), self._fy_end(1403), "Monthly", provider=J
		)
		self.assertEqual(len(periods), 12)
		self.assertEqual(periods[11].to_date, _j(1403, 12, 30))

	def test_quarterly(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Quarterly", provider=J
		)
		self.assertEqual(len(periods), 4)
		self.assertEqual(periods[0].from_date, _j(1405, 1, 1))
		self.assertEqual(periods[0].to_date, _j(1405, 3, 31))
		self.assertEqual(periods[1].from_date, _j(1405, 4, 1))
		self.assertEqual(periods[1].to_date, _j(1405, 6, 31))
		self.assertEqual(periods[3].to_date, _j(1405, 12, 29))

	def test_half_yearly(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Half-Yearly", provider=J
		)
		self.assertEqual(len(periods), 2)
		self.assertEqual(periods[0].to_date, _j(1405, 6, 31))
		self.assertEqual(periods[1].to_date, _j(1405, 12, 29))

	def test_yearly(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Yearly", provider=J
		)
		self.assertEqual(len(periods), 1)
		self.assertEqual(periods[0].from_date, _j(1405, 1, 1))
		self.assertEqual(periods[0].to_date, _j(1405, 12, 29))

	def test_keys_jalali(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Monthly", provider=J
		)
		self.assertEqual(periods[0].key, "j01_1405")
		self.assertEqual(periods[11].key, "j12_1405")

	def test_quarterly_keys_jalali(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Quarterly", provider=J
		)
		self.assertEqual(periods[0].key, "jq1_1405")
		self.assertEqual(periods[3].key, "jq4_1405")

	def test_cross_jalali_year(self):
		periods = BusinessPeriodEngine.generate(
			_j(1404, 10, 1), _j(1405, 3, 31), "Monthly", provider=J
		)
		self.assertEqual(len(periods), 6)
		self.assertEqual(periods[0].from_date, _j(1404, 10, 1))
		self.assertEqual(periods[2].to_date, _j(1404, 12, 29))
		self.assertEqual(periods[3].from_date, _j(1405, 1, 1))
		self.assertEqual(periods[5].to_date, _j(1405, 3, 31))

	def test_storage_dates_are_gregorian(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Monthly", provider=J
		)
		for p in periods:
			self.assertIsInstance(p.from_date, date)
			self.assertIsInstance(p.to_date, date)
			# Must be valid Gregorian dates
			self.assertGreater(p.from_date.year, 2000)

	def test_calendar_system_jalali(self):
		periods = BusinessPeriodEngine.generate(
			self._fy_start(1405), self._fy_end(1405), "Monthly", provider=J
		)
		for p in periods:
			self.assertEqual(p.calendar_system, "Jalali")

	def test_partial_jalali_range(self):
		periods = BusinessPeriodEngine.generate(
			_j(1405, 3, 15), _j(1405, 6, 10), "Monthly", provider=J
		)
		self.assertGreaterEqual(len(periods), 2)
		self.assertEqual(periods[0].from_date, _j(1405, 3, 15))
		self.assertEqual(periods[-1].to_date, _j(1405, 6, 10))


class TestPeriodLabels(unittest.TestCase):
	"""Test label formatting for both calendars."""

	def test_gregorian_monthly_label(self):
		p = BusinessPeriod(
			from_date=date(2026, 1, 1),
			to_date=date(2026, 1, 31),
			key="jan_2026",
			label="",
			periodicity="Monthly",
			calendar_system="Gregorian",
			year=2026,
			period_number=1,
		)
		label = format_period_label(p, locale="en")
		self.assertEqual(label, "Jan 2026")

	def test_gregorian_yearly_label(self):
		p = BusinessPeriod(
			from_date=date(2026, 1, 1),
			to_date=date(2026, 12, 31),
			key="2026",
			label="",
			periodicity="Yearly",
			calendar_system="Gregorian",
			year=2026,
			period_number=1,
		)
		label = format_period_label(p, locale="en")
		self.assertEqual(label, "2026")

	def test_jalali_monthly_fa(self):
		p = BusinessPeriod(
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 1, 31),
			key="j01_1405",
			label="",
			periodicity="Monthly",
			calendar_system="Jalali",
			year=1405,
			period_number=1,
		)
		label = format_period_label(p, locale="fa")
		self.assertEqual(label, "فروردین 1405")

	def test_jalali_monthly_en(self):
		p = BusinessPeriod(
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 1, 31),
			key="j01_1405",
			label="",
			periodicity="Monthly",
			calendar_system="Jalali",
			year=1405,
			period_number=1,
		)
		label = format_period_label(p, locale="en")
		self.assertEqual(label, "Farvardin 1405")

	def test_jalali_quarterly_fa(self):
		p = BusinessPeriod(
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 3, 31),
			key="jq1_1405",
			label="",
			periodicity="Quarterly",
			calendar_system="Jalali",
			year=1405,
			period_number=1,
		)
		label = format_period_label(p, locale="fa")
		self.assertIn("سه‌ماهه", label)
		self.assertIn("1405", label)

	def test_jalali_quarterly_en(self):
		p = BusinessPeriod(
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 3, 31),
			key="jq1_1405",
			label="",
			periodicity="Quarterly",
			calendar_system="Jalali",
			year=1405,
			period_number=1,
		)
		label = format_period_label(p, locale="en")
		self.assertEqual(label, "Q1 1405")

	def test_jalali_esfand_label(self):
		p = BusinessPeriod(
			from_date=_j(1405, 12, 1),
			to_date=_j(1405, 12, 29),
			key="j12_1405",
			label="",
			periodicity="Monthly",
			calendar_system="Jalali",
			year=1405,
			period_number=12,
		)
		label = format_period_label(p, locale="fa")
		self.assertEqual(label, "اسفند 1405")


class TestConsolidatedValidation(unittest.TestCase):
	"""Test consolidated calendar validation (no DB needed for logic test)."""

	def test_empty_companies(self):
		from persian_calendar.calendar.integrations.financial_statements import (
			validate_consolidated_calendars,
		)

		result = validate_consolidated_calendars([])
		self.assertEqual(result, "Gregorian")


if __name__ == "__main__":
	unittest.main()
