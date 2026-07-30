"""Phase 3d-1 — Sales / Purchase Analytics Business Calendar tests."""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
import jdatetime
from frappe import scrub

from persian_calendar.calendar.integrations import sales_analytics as sa
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)
from persian_calendar.calendar.period_engine import BusinessPeriodEngine


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


def _filters(**kwargs):
	base = {
		"doc_type": "Sales Order",
		"range": "Monthly",
		"from_date": date(2026, 3, 21),
		"to_date": date(2027, 3, 20),
		"tree_type": "Customer",
		"company": "J Co",
		"value_quantity": "Value",
		"curves": "select",
	}
	base.update(kwargs)
	return frappe._dict(base)


def _analytics(filters=None, **kwargs):
	"""Minimal Analytics stand-in with stock-like attributes."""
	obj = SimpleNamespace()
	obj.filters = filters or _filters(**kwargs)
	obj.months = [
		"Jan",
		"Feb",
		"Mar",
		"Apr",
		"May",
		"Jun",
		"Jul",
		"Aug",
		"Sep",
		"Oct",
		"Nov",
		"Dec",
	]
	obj.periodic_daterange = []
	obj.columns = []
	obj.data = []
	obj.chart = None
	return obj


class TestSalesAnalyticsPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_methods_replaced_on_shared_class(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.buying.report.purchase_analytics.purchase_analytics as pa_mod
		import erpnext.selling.report.sales_analytics.sales_analytics as sa_mod

		self.assertIs(sa_mod.Analytics.get_period_date_ranges, sa.get_period_date_ranges)
		self.assertIs(sa_mod.Analytics.get_period, sa.get_period)
		# Purchase Analytics uses the same class object
		self.assertIs(pa_mod.Analytics, sa_mod.Analytics)
		self.assertIs(pa_mod.Analytics.get_period_date_ranges, sa.get_period_date_ranges)
		state = get_patch_state()
		self.assertTrue(state.sales_analytics_patched)
		self.assertIsNot(state.original_sa_get_period_date_ranges, sa.get_period_date_ranges)

	def test_idempotent_no_double_wrap(self):
		apply_calendar_patches()
		orig = get_patch_state().original_sa_get_period_date_ranges
		apply_calendar_patches()
		self.assertIs(get_patch_state().original_sa_get_period_date_ranges, orig)
		import erpnext.selling.report.sales_analytics.sales_analytics as sa_mod

		self.assertIs(sa_mod.Analytics.get_period_date_ranges, sa.get_period_date_ranges)

	def test_trends_and_stock_analytics_not_sales_adapter(self):
		apply_calendar_patches()
		import erpnext.controllers.trends as trends_mod
		import erpnext.stock.report.stock_analytics.stock_analytics as stock_mod

		from persian_calendar.calendar.integrations import stock_analytics as stk_adapter
		from persian_calendar.calendar.integrations import trends as trends_adapter

		# Trends module function is our trends adapter — not sales analytics
		self.assertIs(trends_mod.get_period_date_ranges, trends_adapter.get_period_date_ranges)
		# Stock Analytics has its own free-function adapter (Phase 3d-2), not Sales methods
		self.assertIs(stock_mod.get_period_date_ranges, stk_adapter.get_period_date_ranges)
		self.assertIsNot(stock_mod.get_period_date_ranges, sa.get_period_date_ranges)


class TestGregorianDelegation(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		self.calls = []
		calls = self.calls

		def fake_ranges(analytics_self):
			calls.append("ranges")
			analytics_self.periodic_daterange = [date(2026, 1, 31)]

		def fake_period(analytics_self, d):
			calls.append(("period", d))
			return "Jan 2026"

		sa._original_get_period_date_ranges = fake_ranges
		sa._original_get_period = fake_period

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_gregorian_monthly_delegates(self):
		obj = _analytics(company="G Co", range="Monthly")
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			sa.get_period_date_ranges(obj)
			label = sa.get_period(obj, date(2026, 1, 15))
		self.assertEqual(self.calls[0], "ranges")
		self.assertEqual(label, "Jan 2026")

	def test_weekly_delegates_even_for_jalali_company(self):
		obj = _analytics(company="J Co", range="Weekly")
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			sa.get_period_date_ranges(obj)
		self.assertEqual(self.calls, ["ranges"])
		self.assertFalse(getattr(obj, "_pc_sa_jalali", False))


class TestJalaliPeriods(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def _run_ranges(self, rang, start, end):
		obj = _analytics(
			company="J Co",
			range=rang,
			from_date=start,
			to_date=end,
		)
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			sa.get_period_date_ranges(obj)
		return obj

	def test_monthly_farvardin_esfand(self):
		obj = self._run_ranges("Monthly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertTrue(obj._pc_sa_jalali)
		self.assertEqual(len(obj.periodic_daterange), 12)
		self.assertEqual(obj.periodic_daterange[0], _j(1405, 1, 31))
		self.assertEqual(obj.periodic_daterange[11], _j(1405, 12, 29))
		# Keys via get_period
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			k0 = sa.get_period(obj, _j(1405, 1, 15))
			k11 = sa.get_period(obj, _j(1405, 12, 20))
		self.assertEqual(k0, "j01_1405")
		self.assertEqual(k11, "j12_1405")
		self.assertNotEqual(k0, k11)

	def test_quarterly(self):
		obj = self._run_ranges("Quarterly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertEqual(len(obj.periodic_daterange), 4)
		self.assertEqual(obj.periodic_daterange[0], _j(1405, 3, 31))
		self.assertEqual(obj.periodic_daterange[3], _j(1405, 12, 29))
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(sa.get_period(obj, _j(1405, 2, 1)), "jq1_1405")
			self.assertEqual(sa.get_period(obj, _j(1405, 5, 1)), "jq2_1405")
			self.assertEqual(sa.get_period(obj, _j(1405, 8, 1)), "jq3_1405")
			self.assertEqual(sa.get_period(obj, _j(1405, 11, 1)), "jq4_1405")

	def test_yearly(self):
		fy_start, fy_end = _j(1405, 1, 1), _j(1405, 12, 29)
		obj = _analytics(
			company="J Co",
			range="Yearly",
			from_date=fy_start,
			to_date=fy_end,
		)
		with (
			patch(
				"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"erpnext.accounts.utils.get_fiscal_year",
				return_value=("FY-1405", fy_start, fy_end),
			),
		):
			sa.get_period_date_ranges(obj)
		self.assertEqual(len(obj.periodic_daterange), 1)
		self.assertEqual(obj.periodic_daterange[0], fy_end)
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertTrue(sa.get_period(obj, _j(1405, 6, 1)).startswith("j"))

	def test_columns_use_stable_fieldnames_not_labels(self):
		obj = self._run_ranges("Monthly", _j(1405, 1, 1), _j(1405, 3, 31))
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			sa.get_columns(obj)
		period_cols = [
			c for c in obj.columns if c["fieldname"] not in ("entity", "entity_name", "stock_uom", "total")
		]
		fieldnames = [c["fieldname"] for c in period_cols]
		labels = [c["label"] for c in period_cols]
		self.assertEqual(fieldnames[0], scrub("j01_1405"))
		self.assertNotEqual(fieldnames[0], scrub(str(labels[0])))
		self.assertEqual(len(fieldnames), len(set(fieldnames)))

	def test_leap_esfand(self):
		obj = self._run_ranges("Monthly", _j(1403, 1, 1), _j(1403, 12, 30))
		self.assertEqual(obj.periodic_daterange[11], _j(1403, 12, 30))

	def test_partial_range_inside_year(self):
		obj = self._run_ranges("Monthly", _j(1405, 4, 1), _j(1405, 6, 15))
		self.assertGreaterEqual(len(obj.periodic_daterange), 2)
		self.assertEqual(obj.periodic_daterange[0], _j(1405, 4, 31))
		self.assertEqual(obj.periodic_daterange[-1], _j(1405, 6, 15))

	def test_storage_dates_are_gregorian(self):
		obj = self._run_ranges("Monthly", _j(1405, 1, 1), _j(1405, 1, 31))
		self.assertIsInstance(obj.periodic_daterange[0], date)
		self.assertEqual(obj.periodic_daterange[0].year, 2026)

	def test_display_calendar_independence(self):
		obj = self._run_ranges("Monthly", _j(1405, 1, 1), _j(1405, 12, 29))
		ends_a = list(obj.periodic_daterange)
		with (
			patch(
				"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch("frappe.local", MagicMock(lang="en")),
		):
			sa.get_period_date_ranges(obj)
			ends_b = list(obj.periodic_daterange)
			k = sa.get_period(obj, _j(1405, 1, 10))
		with (
			patch(
				"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch("frappe.local", MagicMock(lang="fa")),
		):
			sa.get_period_date_ranges(obj)
			ends_c = list(obj.periodic_daterange)
			k2 = sa.get_period(obj, _j(1405, 1, 10))
		self.assertEqual(ends_a, ends_b)
		self.assertEqual(ends_b, ends_c)
		self.assertEqual(k, k2)


class TestCompanyResolution(unittest.TestCase):
	def test_mixed_calendars_rejected(self):
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			side_effect=lambda c: "Jalali" if c == "A" else "Gregorian",
		):
			with self.assertRaises(Exception) as ctx:
				sa.validate_companies_business_calendar(["A", "B"])
			self.assertIn("mix", str(ctx.exception).lower())

	def test_same_calendar_ok(self):
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(sa.validate_companies_business_calendar(["A", "B"]), "Jalali")

	def test_update_company_list_validates(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

		def stock_update(self):
			self.filters.company = ["Parent", "Child"]

		sa._original_update_company_list = stock_update
		obj = _analytics(company="Parent")
		with patch(
			"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
			side_effect=lambda c: "Jalali" if c == "Parent" else "Gregorian",
		):
			with self.assertRaises(Exception):
				sa.update_company_list_for_parent_company(obj)
		reset_calendar_patches_for_tests()


class TestChartUsesFieldnames(unittest.TestCase):
	def test_jalali_chart_reads_fieldname_not_scrub_label(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		obj = _analytics(company="J Co", range="Monthly", tree_type="Customer", curves="all")
		obj._pc_sa_jalali = True
		key = "j01_1405"
		obj.columns = [
			{"label": "Customer", "fieldname": "entity"},
			{"label": "Customer Name", "fieldname": "entity_name"},
			{"label": "Farvardin 1405", "fieldname": scrub(key)},
			{"label": "Total", "fieldname": "total"},
		]
		obj.data = [
			{
				"entity": "C1",
				"entity_name": "C1",
				scrub(key): 100.0,
				"total": 100.0,
			}
		]
		sa.get_chart_data(obj)
		self.assertEqual(obj.chart["data"]["datasets"][0]["values"], [100.0])
		self.assertEqual(obj.chart["data"]["labels"], ["Farvardin 1405"])
		reset_calendar_patches_for_tests()


class TestEngineNotDuplicated(unittest.TestCase):
	def test_jalali_uses_business_period_engine(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		obj = _analytics(company="J Co", range="Monthly", from_date=_j(1405, 1, 1), to_date=_j(1405, 3, 31))
		with (
			patch(
				"persian_calendar.calendar.integrations.sales_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch.object(
				BusinessPeriodEngine,
				"generate",
				wraps=BusinessPeriodEngine.generate,
			) as gen,
		):
			sa.get_period_date_ranges(obj)
			gen.assert_called()
		reset_calendar_patches_for_tests()


class TestHalfYearlyNotInSalesUi(unittest.TestCase):
	def test_installed_sales_analytics_options_exclude_half_yearly(self):
		"""Audit confirmation: Sales Analytics JS has Weekly/Monthly/Quarterly/Yearly only."""
		from pathlib import Path

		js = (
			Path(__import__("erpnext").__file__).resolve().parent
			/ "selling/report/sales_analytics/sales_analytics.js"
		)
		text = js.read_text(encoding="utf-8")
		self.assertIn("Weekly", text)
		self.assertIn("Monthly", text)
		self.assertIn("Quarterly", text)
		self.assertIn("Yearly", text)
		# Half-Yearly must not appear as a range option in this report
		self.assertNotIn("Half-Yearly", text)


if __name__ == "__main__":
	unittest.main()
