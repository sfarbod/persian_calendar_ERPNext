"""Phase 3c — Trends get_period_date_ranges Business Calendar adapter tests."""

from __future__ import annotations

import sys
import types
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import jdatetime

from persian_calendar.calendar.integrations import trends as trends_adapter
from persian_calendar.calendar.patches import (
	TRENDS_PERIOD_RANGES_CONSUMERS,
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


def _stock_ranges(period, year_start, year_end):
	"""Mirror ERPNext trends.get_period_date_ranges Gregorian math."""
	from dateutil.relativedelta import relativedelta
	from frappe.utils import getdate

	increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}[period]
	year_start_date = getdate(year_start)
	year_end_date = getdate(year_end)
	out = []
	for _i in range(1, 13, increment):
		period_end_date = year_start_date + relativedelta(months=increment, days=-1)
		if period_end_date > year_end_date:
			period_end_date = year_end_date
		out.append([year_start_date, period_end_date])
		year_start_date = period_end_date + relativedelta(days=1)
		if period_end_date == year_end_date:
			break
	return out


class TestTrendsPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_source_function_replaced(self):
		status = apply_calendar_patches()
		self.assertEqual(status, PatchStatus.APPLIED)
		import erpnext.controllers.trends as trends_mod

		self.assertIs(trends_mod.get_period_date_ranges, trends_adapter.get_period_date_ranges)
		self.assertIsNot(
			get_patch_state().original_get_period_date_ranges,
			trends_adapter.get_period_date_ranges,
		)

	def test_bvr_imported_before_patch_is_rebound(self):
		reset_calendar_patches_for_tests()
		import erpnext.controllers.trends as trends_mod

		stock = trends_mod.get_period_date_ranges
		mod_name = TRENDS_PERIOD_RANGES_CONSUMERS[0]
		sys.modules.pop(mod_name, None)
		import erpnext.accounts.report.budget_variance_report.budget_variance_report as bvr

		self.assertIs(bvr.get_period_date_ranges, stock)
		apply_calendar_patches()
		self.assertIs(bvr.get_period_date_ranges, trends_adapter.get_period_date_ranges)
		self.assertIn(mod_name, get_patch_state().trends_rebound_modules)

	def test_consumer_imported_after_patch_receives_adapter(self):
		apply_calendar_patches()
		mod_name = TRENDS_PERIOD_RANGES_CONSUMERS[0]
		sys.modules.pop(mod_name, None)
		import erpnext.accounts.report.budget_variance_report.budget_variance_report as bvr

		self.assertIs(bvr.get_period_date_ranges, trends_adapter.get_period_date_ranges)

	def test_unrelated_same_name_untouched(self):
		def unrelated(filters):
			return []

		fake = types.ModuleType("erpnext.stock.report._fake_stock_analytics")
		fake.get_period_date_ranges = unrelated
		sys.modules[fake.__name__] = fake
		try:
			apply_calendar_patches()
			self.assertIs(fake.get_period_date_ranges, unrelated)
		finally:
			sys.modules.pop(fake.__name__, None)

	def test_fs_and_md_patches_remain_active(self):
		apply_calendar_patches()
		state = get_patch_state()
		self.assertIsNotNone(state.original_get_period_list)
		self.assertIsNotNone(state.original_get_periodwise_distribution_data)
		self.assertIsNotNone(state.original_get_period_date_ranges)
		self.assertIsNotNone(state.original_budget_variance_execute)
		import erpnext.accounts.doctype.monthly_distribution.monthly_distribution as md_mod
		import erpnext.accounts.report.budget_variance_report.budget_variance_report as bvr_mod
		import erpnext.accounts.report.financial_statements as fs_mod

		self.assertIs(fs_mod.get_period_list, state.adapter_get_period_list)
		self.assertIs(md_mod.get_periodwise_distribution_data, state.adapter_get_periodwise_distribution_data)
		self.assertIs(bvr_mod.execute, state.adapter_budget_variance_execute)

	def test_no_recursion_on_original(self):
		apply_calendar_patches()
		original = get_patch_state().original_get_period_date_ranges
		adapter = get_patch_state().adapter_get_period_date_ranges
		self.assertIs(trends_adapter.get_original_get_period_date_ranges(), original)
		for _ in range(5):
			apply_calendar_patches()
		self.assertIs(get_patch_state().original_get_period_date_ranges, original)
		self.assertIsNot(original, adapter)

	def test_known_consumer_inventory(self):
		import ast
		from pathlib import Path

		erpnext_root = Path(__import__("erpnext").__file__).resolve().parent
		found: set[str] = set()
		for path in erpnext_root.rglob("*.py"):
			try:
				tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
			except SyntaxError:
				continue
			for node in ast.walk(tree):
				if not isinstance(node, ast.ImportFrom):
					continue
				if node.module != "erpnext.controllers.trends":
					continue
				names = {a.name for a in node.names}
				if "get_period_date_ranges" not in names:
					continue
				rel = path.relative_to(erpnext_root.parent)
				found.add(".".join(rel.with_suffix("").parts))
		missing = found - set(TRENDS_PERIOD_RANGES_CONSUMERS)
		self.assertFalse(
			missing,
			f"New get_period_date_ranges importers not registered: {sorted(missing)}",
		)


class TestTrendsGregorianParity(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def _call(self, period, start, end):
		with (
			patch(
				"persian_calendar.calendar.integrations.trends.get_business_calendar_for_company",
				return_value="Gregorian",
			),
			patch(
				"persian_calendar.calendar.integrations.trends.frappe.get_cached_value",
				return_value=(start, end),
			),
		):
			# Call original path via adapter with company that resolves Gregorian
			return trends_adapter.get_period_date_ranges(period, fiscal_year="FY-TEST", company="G Co")

	def test_monthly_equals_stock(self):
		start, end = date(2026, 1, 1), date(2026, 12, 31)
		# Patch captured original to use our stock mirror with fixed bounds
		prev = trends_adapter._original_get_period_date_ranges

		def stock_fn(period, fiscal_year=None, year_start_date=None):
			return _stock_ranges(period, start, end)

		trends_adapter._original_get_period_date_ranges = stock_fn
		try:
			got = self._call("Monthly", start, end)
			self.assertEqual(got, _stock_ranges("Monthly", start, end))
			self.assertEqual(len(got), 12)
		finally:
			trends_adapter._original_get_period_date_ranges = prev

	def test_quarterly_half_yearly_yearly(self):
		start, end = date(2026, 1, 1), date(2026, 12, 31)
		prev = trends_adapter._original_get_period_date_ranges

		def stock_fn(period, fiscal_year=None, year_start_date=None):
			return _stock_ranges(period, start, end)

		trends_adapter._original_get_period_date_ranges = stock_fn
		try:
			for period, n in (("Quarterly", 4), ("Half-Yearly", 2), ("Yearly", 1)):
				got = self._call(period, start, end)
				self.assertEqual(got, _stock_ranges(period, start, end), period)
				self.assertEqual(len(got), n, period)
		finally:
			trends_adapter._original_get_period_date_ranges = prev

	def test_non_january_fiscal_year(self):
		start, end = date(2026, 4, 1), date(2027, 3, 31)
		prev = trends_adapter._original_get_period_date_ranges

		def stock_fn(period, fiscal_year=None, year_start_date=None):
			return _stock_ranges(period, start, end)

		trends_adapter._original_get_period_date_ranges = stock_fn
		try:
			got = self._call("Monthly", start, end)
			self.assertEqual(got, _stock_ranges("Monthly", start, end))
			self.assertEqual(got[0][0], date(2026, 4, 1))
			self.assertEqual(got[-1][1], date(2027, 3, 31))
		finally:
			trends_adapter._original_get_period_date_ranges = prev

	def test_gregorian_delegates_to_captured_original(self):
		sentinel = object()

		def fake_original(*a, **k):
			return sentinel

		prev = trends_adapter._original_get_period_date_ranges
		trends_adapter._original_get_period_date_ranges = fake_original
		try:
			with patch(
				"persian_calendar.calendar.integrations.trends.get_business_calendar_for_company",
				return_value="Gregorian",
			):
				result = trends_adapter.get_period_date_ranges("Monthly", fiscal_year="X", company="G")
			self.assertIs(result, sentinel)
		finally:
			trends_adapter._original_get_period_date_ranges = prev


class TestTrendsJalali(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def _ranges(self, period, start, end):
		with (
			patch(
				"persian_calendar.calendar.integrations.trends.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.trends.frappe.get_cached_value",
				return_value=(start, end),
			),
		):
			return trends_adapter.get_period_date_ranges(period, fiscal_year="FY-J", company="J Co")

	def test_monthly_farvardin_esfand(self):
		start, end = _j(1405, 1, 1), _j(1405, 12, 29)
		ranges = self._ranges("Monthly", start, end)
		self.assertEqual(len(ranges), 12)
		self.assertEqual(ranges[0], [_j(1405, 1, 1), _j(1405, 1, 31)])
		self.assertEqual(ranges[11], [_j(1405, 12, 1), _j(1405, 12, 29)])
		# Storage dates are Gregorian
		self.assertIsInstance(ranges[0][0], date)
		self.assertEqual(ranges[0][0].year, 2026)

	def test_quarterly(self):
		ranges = self._ranges("Quarterly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertEqual(len(ranges), 4)
		self.assertEqual(ranges[0], [_j(1405, 1, 1), _j(1405, 3, 31)])
		self.assertEqual(ranges[1], [_j(1405, 4, 1), _j(1405, 6, 31)])
		self.assertEqual(ranges[2], [_j(1405, 7, 1), _j(1405, 9, 30)])
		self.assertEqual(ranges[3], [_j(1405, 10, 1), _j(1405, 12, 29)])

	def test_half_yearly_and_yearly(self):
		start, end = _j(1405, 1, 1), _j(1405, 12, 29)
		h = self._ranges("Half-Yearly", start, end)
		self.assertEqual(len(h), 2)
		self.assertEqual(h[0], [_j(1405, 1, 1), _j(1405, 6, 31)])
		self.assertEqual(h[1], [_j(1405, 7, 1), _j(1405, 12, 29)])
		y = self._ranges("Yearly", start, end)
		self.assertEqual(len(y), 1)
		self.assertEqual(y[0], [start, end])

	def test_leap_esfand(self):
		ranges = self._ranges("Monthly", _j(1403, 1, 1), _j(1403, 12, 30))
		self.assertEqual(ranges[11][1], _j(1403, 12, 30))

	def test_order_independent_of_labels(self):
		from persian_calendar.calendar.engine import CalendarEngine

		start, end = _j(1405, 1, 1), _j(1405, 12, 29)
		ranges = self._ranges("Monthly", start, end)
		bps = BusinessPeriodEngine.generate(start, end, "Monthly", provider=CalendarEngine.jalali())
		for i, bp in enumerate(bps):
			self.assertEqual(ranges[i][0], bp.from_date)
			self.assertEqual(ranges[i][1], bp.to_date)
			# Labels must not affect ordering / keys
			_ = format_period_label(bp, locale="en")
			_ = format_period_label(bp, locale="fa")

	def test_display_calendar_independence(self):
		"""User Display Calendar must not change Business period boundaries."""
		start, end = _j(1405, 1, 1), _j(1405, 12, 29)
		with (
			patch(
				"persian_calendar.calendar.integrations.trends.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.trends.frappe.get_cached_value",
				return_value=(start, end),
			),
		):
			a = trends_adapter.get_period_date_ranges("Monthly", fiscal_year="FY", company="J")
			# Simulate display calendar change via frappe.local — adapter must ignore it
			local = MagicMock()
			local.lang = "en"
			with patch("frappe.local", local):
				b = trends_adapter.get_period_date_ranges("Monthly", fiscal_year="FY", company="J")
		self.assertEqual(a, b)

	def test_mixed_fiscal_year_companies_rejected(self):
		import frappe

		form = getattr(frappe.local, "form_dict", None)
		try:
			frappe.local.form_dict = {}
			with (
				patch(
					"persian_calendar.calendar.integrations.trends.frappe.get_all",
					return_value=["CoA", "CoB"],
				),
				patch(
					"persian_calendar.calendar.integrations.trends.get_business_calendar_for_company",
					side_effect=lambda c: "Jalali" if c == "CoA" else "Gregorian",
				),
			):
				with self.assertRaises(frappe.ValidationError) as ctx:
					trends_adapter._resolve_company("FY-MIXED")
			self.assertIn("different Business", str(ctx.exception))
		finally:
			if form is not None:
				frappe.local.form_dict = form
			else:
				frappe.local.form_dict = frappe._dict()


class TestNoGlobalUtilsPatch(unittest.TestCase):
	def test_formatdate_not_replaced(self):
		import frappe.utils as fu

		apply_calendar_patches()
		# Identity check — apply must not swap frappe.utils.formatdate
		from frappe.utils import formatdate as fd

		self.assertIs(fd, fu.formatdate)


if __name__ == "__main__":
	unittest.main()
