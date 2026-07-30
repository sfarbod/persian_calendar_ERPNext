"""Phase 3c — Budget Variance Business Calendar alignment tests."""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jdatetime

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.integrations import budget_variance as bvr
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


def _dist(start, end, amount):
	return SimpleNamespace(start_date=start, end_date=end, amount=amount, percent=None)


def _period(from_date, to_date, key="p", fy="FY"):
	return {
		"fiscal_year": fy,
		"from_date": from_date,
		"to_date": to_date,
		"label_suffix": "x",
		"key": key,
	}


class TestBudgetVariancePatch(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_execute_replaced(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.accounts.report.budget_variance_report.budget_variance_report as mod

		self.assertIs(mod.execute, bvr.execute)
		self.assertIsNot(get_patch_state().original_budget_variance_execute, bvr.execute)

	def test_gregorian_delegates_to_stock(self):
		apply_calendar_patches()
		sentinel = (["col"], [{"a": 1}], None, None)

		def fake_execute(filters):
			return sentinel

		prev = bvr._original_execute
		bvr._original_execute = fake_execute
		try:
			with patch(
				"persian_calendar.calendar.integrations.budget_variance.get_business_calendar_for_company",
				return_value="Gregorian",
			):
				result = bvr.execute({"company": "G", "period": "Monthly"})
			self.assertIs(result, sentinel)
		finally:
			bvr._original_execute = prev


class TestDistributionMatching(unittest.TestCase):
	def setUp(self):
		self.cal = CalendarEngine.jalali()

	def test_monthly_stored_aligns_to_report_period(self):
		dists = [_dist(_j(1405, 1, 1), _j(1405, 1, 31), 10000)]
		period = _period(_j(1405, 1, 1), _j(1405, 1, 31), "j01")
		self.assertEqual(bvr.budget_amount_for_period(dists, period, self.cal), 10000)

	def test_monthly_aggregates_into_quarterly(self):
		dists = [
			_dist(_j(1405, 1, 1), _j(1405, 1, 31), 1000),
			_dist(_j(1405, 2, 1), _j(1405, 2, 31), 2000),
			_dist(_j(1405, 3, 1), _j(1405, 3, 31), 3000),
		]
		q1 = _period(_j(1405, 1, 1), _j(1405, 3, 31), "jq1")
		self.assertEqual(bvr.budget_amount_for_period(dists, q1, self.cal), 6000)

	def test_quarterly_stored_splits_to_monthly(self):
		"""Coarser stored → finer report: equal split across business months."""
		dists = [_dist(_j(1405, 1, 1), _j(1405, 3, 31), 9000)]
		m1 = _period(_j(1405, 1, 1), _j(1405, 1, 31), "j01")
		m2 = _period(_j(1405, 2, 1), _j(1405, 2, 31), "j02")
		m3 = _period(_j(1405, 3, 1), _j(1405, 3, 31), "j03")
		self.assertEqual(bvr.budget_amount_for_period(dists, m1, self.cal), 3000)
		self.assertEqual(bvr.budget_amount_for_period(dists, m2, self.cal), 3000)
		self.assertEqual(bvr.budget_amount_for_period(dists, m3, self.cal), 3000)

	def test_missing_period_is_zero(self):
		dists = [_dist(_j(1405, 1, 1), _j(1405, 1, 31), 1000)]
		m2 = _period(_j(1405, 2, 1), _j(1405, 2, 31), "j02")
		self.assertEqual(bvr.budget_amount_for_period(dists, m2, self.cal), 0)

	def test_duplicate_period_detected(self):
		dists = [
			_dist(_j(1405, 1, 1), _j(1405, 1, 31), 1000),
			_dist(_j(1405, 1, 1), _j(1405, 1, 31), 500),
		]
		with self.assertRaises(Exception) as ctx:
			bvr.validate_distribution_integrity("BUD-1", dists)
		self.assertIn("duplicated", str(ctx.exception).lower())

	def test_overlap_detected(self):
		dists = [
			_dist(_j(1405, 1, 1), _j(1405, 2, 15), 1000),
			_dist(_j(1405, 2, 1), _j(1405, 2, 31), 500),
		]
		with self.assertRaises(Exception) as ctx:
			bvr.validate_distribution_integrity("BUD-1", dists)
		self.assertIn("overlap", str(ctx.exception).lower())

	def test_labels_never_used_as_keys(self):
		"""Matching uses dates only — English/Persian labels must not matter."""
		dists = [_dist(_j(1405, 1, 1), _j(1405, 1, 31), 42)]
		# Fake label fields that would mislead name-based matching
		dists[0].month = "January"
		dists[0].label = "فروردین"
		period = _period(_j(1405, 1, 1), _j(1405, 1, 31), "j01")
		self.assertEqual(bvr.budget_amount_for_period(dists, period, self.cal), 42)


class TestActualBoundaries(unittest.TestCase):
	"""Classify GL postings by inclusive period boundaries (no DB)."""

	def test_inclusive_first_last_and_outside(self):
		periods = [
			_period(_j(1405, 1, 1), _j(1405, 1, 31), "j01"),
			_period(_j(1405, 2, 1), _j(1405, 2, 31), "j02"),
		]
		first = _j(1405, 1, 1)
		last = _j(1405, 1, 31)
		before = first - timedelta(days=1)
		after = last + timedelta(days=1)

		def classify(posting):
			for p in periods:
				if p["from_date"] <= posting <= p["to_date"]:
					return p["key"]
			return None

		self.assertEqual(classify(first), "j01")
		self.assertEqual(classify(last), "j01")
		self.assertIsNone(classify(before))
		self.assertEqual(classify(after), "j02")  # first day of next period
		self.assertIsNone(classify(_j(1405, 3, 1)))


class TestAccumulatedMode(unittest.TestCase):
	def test_monthly_cumulative_budget(self):
		cal = CalendarEngine.jalali()
		dists = [
			_dist(_j(1405, 1, 1), _j(1405, 1, 31), 100),
			_dist(_j(1405, 2, 1), _j(1405, 2, 31), 200),
			_dist(_j(1405, 3, 1), _j(1405, 3, 31), 300),
		]
		periods = [
			_period(_j(1405, 1, 1), _j(1405, 1, 31), "j01"),
			_period(_j(1405, 2, 1), _j(1405, 2, 31), "j02"),
			_period(_j(1405, 3, 1), _j(1405, 3, 31), "j03"),
		]
		running = 0.0
		expected = [100, 300, 600]
		for i, period in enumerate(periods):
			running += bvr.budget_amount_for_period(dists, period, cal)
			self.assertEqual(running, expected[i])

	def test_zero_activity_period_keeps_cumulative(self):
		cal = CalendarEngine.jalali()
		dists = [
			_dist(_j(1405, 1, 1), _j(1405, 1, 31), 100),
			_dist(_j(1405, 3, 1), _j(1405, 3, 31), 50),
		]
		periods = [
			_period(_j(1405, 1, 1), _j(1405, 1, 31), "j01"),
			_period(_j(1405, 2, 1), _j(1405, 2, 31), "j02"),
			_period(_j(1405, 3, 1), _j(1405, 3, 31), "j03"),
		]
		running = 0.0
		vals = []
		for period in periods:
			running += bvr.budget_amount_for_period(dists, period, cal)
			vals.append(running)
		self.assertEqual(vals, [100, 100, 150])

	def test_fiscal_year_crosses_gregorian_new_year(self):
		"""Jalali FY spans Dec→Jan Gregorian; accumulation must not reset at 1 Jan."""
		cal = CalendarEngine.jalali()
		# Dey (month 10) starts ~21 Dec, Bahman ~20 Jan
		dey = (_j(1405, 10, 1), _j(1405, 10, 30))
		bahman = (_j(1405, 11, 1), _j(1405, 11, 30))
		self.assertLess(dey[0].year, bahman[0].year)  # crosses Gregorian year
		dists = [_dist(*dey, 10), _dist(*bahman, 20)]
		periods = [_period(*dey, "j10"), _period(*bahman, "j11")]
		running = 0.0
		for period in periods:
			running += bvr.budget_amount_for_period(dists, period, cal)
		self.assertEqual(running, 30)


class TestHistoricalAndDisplayPolicy(unittest.TestCase):
	def test_submitted_historical_keeps_stored_dates(self):
		"""Report uses stored BD dates — not reinterpreted by current month position."""
		cal = CalendarEngine.jalali()
		# Stale Gregorian Jan row under Jalali company — still matched by dates
		dists = [_dist(date(2026, 1, 1), date(2026, 1, 31), 777)]
		period = _period(date(2026, 1, 1), date(2026, 1, 31), "g01")
		self.assertEqual(bvr.budget_amount_for_period(dists, period, cal), 777)

	def test_display_jalali_business_gregorian_uses_stock_path(self):
		apply_calendar_patches()
		called = {"n": 0}

		def fake_execute(filters):
			called["n"] += 1
			return ([], [], None, None)

		prev = bvr._original_execute
		bvr._original_execute = fake_execute
		try:
			with patch(
				"persian_calendar.calendar.integrations.budget_variance.get_business_calendar_for_company",
				return_value="Gregorian",
			):
				bvr.execute({"company": "G", "period": "Monthly"})
			self.assertEqual(called["n"], 1)
		finally:
			bvr._original_execute = prev
			reset_calendar_patches_for_tests()

	def test_display_gregorian_business_jalali_uses_engine(self):
		with (
			patch(
				"persian_calendar.calendar.integrations.budget_variance.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.budget_variance._jalali_execute",
				return_value=(["c"], [], None, None),
			) as jalali_path,
		):
			bvr.execute({"company": "J", "period": "Monthly"})
			jalali_path.assert_called_once()

	def test_no_session_user_dependency_for_matching(self):
		cal = CalendarEngine.jalali()
		dists = [_dist(_j(1405, 4, 1), _j(1405, 4, 31), 5)]
		period = _period(_j(1405, 4, 1), _j(1405, 4, 31), "j04")
		with patch("frappe.session", MagicMock(user="Guest")):
			self.assertEqual(bvr.budget_amount_for_period(dists, period, cal), 5)


class TestStaleBoundaryWarning(unittest.TestCase):
	def test_stale_message_for_non_jalali_month_start(self):
		with (
			patch(
				"persian_calendar.calendar.integrations.budget_variance.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.budget_variance.frappe.get_all",
				return_value=[SimpleNamespace(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))],
			),
			patch("persian_calendar.calendar.integrations.budget_variance.frappe.msgprint") as msg,
		):
			bvr.validate_stale_budget_calendar("BUD-X", "J Co")
			msg.assert_called_once()


if __name__ == "__main__":
	unittest.main()
