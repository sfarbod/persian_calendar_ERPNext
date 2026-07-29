"""Tests for Budget Business Calendar period generation.

Uses a lightweight stub Budget document — does not require full ERPNext Budget fixtures.
"""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import jdatetime
from frappe.utils import add_months, get_first_day, get_last_day, getdate

from persian_calendar.calendar.integrations.budget import PersianCalendarBudget
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.providers.gregorian import GregorianCalendarProvider


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


def _stock_get_budget_periods(start, end, frequency):
	"""Mirror ERPNext Budget.get_budget_periods for Gregorian parity checks."""
	increments = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}
	inc = increments[frequency]
	periods = []
	start_date = getdate(start)
	end_date = getdate(end)
	while start_date <= end_date:
		period_start = get_first_day(start_date)
		if frequency == "Monthly":
			period_end = get_last_day(period_start)
		elif frequency == "Quarterly":
			period_end = get_last_day(add_months(period_start, 2))
		elif frequency == "Half-Yearly":
			period_end = get_last_day(add_months(period_start, 5))
		else:
			period_end = get_last_day(add_months(period_start, 11))
		period_end = min(period_end, end_date)
		periods.append((period_start, period_end))
		start_date = add_months(period_start, inc)
	return periods


def _make_budget(company, start, end, frequency="Monthly"):
	"""Build a lightweight stand-in that can call PersianCalendarBudget.get_budget_periods."""
	doc = object.__new__(PersianCalendarBudget)
	doc.company = company
	doc.budget_start_date = start
	doc.budget_end_date = end
	doc.distribution_frequency = frequency
	doc.budget_amount = 120000
	doc.distribute_equally = 1
	doc.budget_distribution = []
	return doc


class TestBudgetGregorianParity(unittest.TestCase):
	def test_monthly_matches_stock(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			doc = _make_budget("G Co", date(2026, 1, 1), date(2026, 12, 31), "Monthly")
			# super() path — stub via patching Budget.get_budget_periods on parent
			with patch.object(
				PersianCalendarBudget.__bases__[0],
				"get_budget_periods",
				lambda self: _stock_get_budget_periods(
					self.budget_start_date, self.budget_end_date, self.distribution_frequency
				),
			):
				got = doc.get_budget_periods()
		expected = _stock_get_budget_periods(date(2026, 1, 1), date(2026, 12, 31), "Monthly")
		self.assertEqual(got, expected)
		self.assertEqual(len(got), 12)

	def test_quarterly_half_yearly_yearly(self):
		for freq, n in (("Quarterly", 4), ("Half-Yearly", 2), ("Yearly", 1)):
			with patch(
				"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
				return_value="Gregorian",
			):
				doc = _make_budget("G Co", date(2026, 1, 1), date(2026, 12, 31), freq)
				with patch.object(
					PersianCalendarBudget.__bases__[0],
					"get_budget_periods",
					lambda self, f=freq: _stock_get_budget_periods(
						self.budget_start_date, self.budget_end_date, f
					),
				):
					got = doc.get_budget_periods()
			self.assertEqual(len(got), n, freq)
			self.assertEqual(
				got,
				_stock_get_budget_periods(date(2026, 1, 1), date(2026, 12, 31), freq),
				freq,
			)


class TestBudgetJalaliPeriods(unittest.TestCase):
	def test_monthly_boundaries(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			doc = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 12, 29), "Monthly")
			periods = doc.get_budget_periods()

		self.assertEqual(len(periods), 12)
		# First six: 31-day months
		for i in range(6):
			self.assertEqual(periods[i][0], _j(1405, i + 1, 1))
			self.assertEqual(periods[i][1], _j(1405, i + 1, 31))
		# 7–11: 30-day
		for i in range(6, 11):
			self.assertEqual(periods[i][0], _j(1405, i + 1, 1))
			self.assertEqual(periods[i][1], _j(1405, i + 1, 30))
		# Esfand non-leap
		self.assertEqual(periods[11][1], _j(1405, 12, 29))

	def test_leap_esfand(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			doc = _make_budget("J Co", _j(1403, 1, 1), _j(1403, 12, 30), "Monthly")
			periods = doc.get_budget_periods()
		self.assertEqual(periods[11][1], _j(1403, 12, 30))

	def test_quarterly(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			doc = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 12, 29), "Quarterly")
			periods = doc.get_budget_periods()
		self.assertEqual(len(periods), 4)
		self.assertEqual(periods[0], (_j(1405, 1, 1), _j(1405, 3, 31)))
		self.assertEqual(periods[1], (_j(1405, 4, 1), _j(1405, 6, 31)))
		self.assertEqual(periods[2], (_j(1405, 7, 1), _j(1405, 9, 30)))
		self.assertEqual(periods[3], (_j(1405, 10, 1), _j(1405, 12, 29)))

	def test_half_yearly_and_yearly(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			h = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 12, 29), "Half-Yearly")
			y = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 12, 29), "Yearly")
			half = h.get_budget_periods()
			year = y.get_budget_periods()
		self.assertEqual(len(half), 2)
		self.assertEqual(half[0][1], _j(1405, 6, 31))
		self.assertEqual(half[1][1], _j(1405, 12, 29))
		self.assertEqual(len(year), 1)
		self.assertEqual(year[0], (_j(1405, 1, 1), _j(1405, 12, 29)))

	def test_storage_dates_are_gregorian(self):
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			doc = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 12, 29), "Monthly")
			periods = doc.get_budget_periods()
		for start, end in periods:
			self.assertIsInstance(start, date)
			self.assertIsInstance(end, date)
			self.assertGreater(start.year, 2000)

	def test_display_preference_ignored(self):
		"""Business Calendar alone controls periods — not Display."""
		with patch(
			"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
			return_value="Jalali",
		):
			doc = _make_budget("J Co", _j(1405, 1, 1), _j(1405, 3, 31), "Monthly")
			periods = doc.get_budget_periods()
		self.assertEqual(len(periods), 3)
		self.assertEqual(periods[0][0], _j(1405, 1, 1))


class TestBudgetAllocationPrecision(unittest.TestCase):
	def test_equal_split_sums_to_budget_amount(self):
		from persian_calendar.calendar.providers.jalali import JalaliCalendarProvider

		amount = 120000.0
		periods = BusinessPeriodEngine.generate(
			_j(1405, 1, 1),
			_j(1405, 12, 29),
			"Monthly",
			provider=JalaliCalendarProvider(),
		)
		n = len(periods)
		row_percent = 100.0 / n
		# Mirror Budget.add_allocated_amount rounding to 3 decimals
		allocations = [round(amount * row_percent / 100.0, 3) for _ in periods]
		self.assertEqual(n, 12)
		self.assertEqual(round(allocations[0], 3), round(amount / 12, 3))
		# Sum of rounded rows matches ERPNext-style equal split within 1 currency unit
		self.assertAlmostEqual(sum(allocations), amount, delta=1.0)


class TestBudgetUsesEngineNotLocalMath(unittest.TestCase):
	def test_jalali_delegates_to_business_period_engine(self):
		fake = [SimpleNamespace(from_date=date(2026, 3, 21), to_date=date(2026, 4, 20))]
		with (
			patch(
				"persian_calendar.calendar.integrations.budget.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.budget.BusinessPeriodEngine.generate",
				return_value=fake,
			) as gen,
		):
			doc = _make_budget("J Co", date(2026, 3, 21), date(2027, 3, 20), "Monthly")
			result = doc.get_budget_periods()
			gen.assert_called_once()
			self.assertEqual(result, [(date(2026, 3, 21), date(2026, 4, 20))])


if __name__ == "__main__":
	unittest.main()
