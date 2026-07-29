"""Phase 3d-2 — Stock Analytics Business Calendar tests."""

from __future__ import annotations

import inspect
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import frappe
import jdatetime
from frappe import scrub
from frappe.utils import getdate

from persian_calendar.calendar.integrations import sales_analytics as sa
from persian_calendar.calendar.integrations import stock_analytics as stk
from persian_calendar.calendar.integrations import trends as trends_adapter
from persian_calendar.calendar.patches import (
	STOCK_ANALYTICS_PERIOD_CONSUMERS,
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
		"range": "Monthly",
		"from_date": date(2026, 3, 21),
		"to_date": date(2027, 3, 20),
		"company": "J Co",
		"value_quantity": "Quantity",
	}
	base.update(kwargs)
	return frappe._dict(base)


class TestStockAnalyticsSourceContract(unittest.TestCase):
	"""Fail clearly if upstream Stock Analytics signatures change."""

	def test_signatures(self):
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		self.assertEqual(
			list(inspect.signature(mod.get_period_date_ranges).parameters),
			["filters"],
		)
		self.assertEqual(
			list(inspect.signature(mod.get_period).parameters),
			["posting_date", "filters"],
		)
		self.assertEqual(
			list(inspect.signature(mod.round_down_to_nearest_frequency).parameters),
			["date", "frequency"],
		)
		self.assertEqual(
			list(inspect.signature(mod.get_period_columns).parameters),
			["filters"],
		)
		# Adapter wrappers must match stock arity
		self.assertEqual(
			list(inspect.signature(stk.get_period_date_ranges).parameters),
			["filters"],
		)
		self.assertEqual(list(inspect.signature(stk.get_period).parameters), ["posting_date", "filters"])

	def test_stock_js_ranges_exclude_half_yearly(self):
		from pathlib import Path

		js = (
			Path(__import__("erpnext").__file__).resolve().parent
			/ "stock/report/stock_analytics/stock_analytics.js"
		)
		text = js.read_text(encoding="utf-8")
		self.assertIn("Weekly", text)
		self.assertIn("Monthly", text)
		self.assertIn("Quarterly", text)
		self.assertIn("Yearly", text)
		self.assertNotIn("Half-Yearly", text)

	def test_python_increment_map_includes_half_yearly(self):
		from pathlib import Path

		py = (
			Path(__import__("erpnext").__file__).resolve().parent
			/ "stock/report/stock_analytics/stock_analytics.py"
		)
		text = py.read_text(encoding="utf-8")
		self.assertIn('"Half-Yearly": 6', text)


class TestStockAnalyticsPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_functions_replaced_and_round_down_untouched(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		state = get_patch_state()
		self.assertTrue(state.stock_analytics_patched)
		self.assertIs(mod.get_period_date_ranges, stk.get_period_date_ranges)
		self.assertIs(mod.get_period, stk.get_period)
		self.assertIs(mod.get_period_columns, stk.get_period_columns)
		# round_down must remain the captured stock original (module-global safety)
		self.assertIs(mod.round_down_to_nearest_frequency, state.original_stk_round_down)
		self.assertIsNot(state.original_stk_get_period_date_ranges, stk.get_period_date_ranges)

	def test_idempotent_no_double_capture(self):
		apply_calendar_patches()
		orig = get_patch_state().original_stk_get_period_date_ranges
		apply_calendar_patches()
		self.assertIs(get_patch_state().original_stk_get_period_date_ranges, orig)

	def test_trends_and_sales_untouched(self):
		apply_calendar_patches()
		import erpnext.controllers.trends as trends_mod
		import erpnext.selling.report.sales_analytics.sales_analytics as sa_mod

		self.assertIs(trends_mod.get_period_date_ranges, trends_adapter.get_period_date_ranges)
		self.assertIs(sa_mod.Analytics.get_period_date_ranges, sa.get_period_date_ranges)
		self.assertIsNot(sa_mod.Analytics.get_period_date_ranges, stk.get_period_date_ranges)

	def test_identity_rebind_known_consumers(self):
		# Import consumers before patch to simulate import-before-patch
		import erpnext.manufacturing.report.job_card_summary.job_card_summary as jc
		import erpnext.manufacturing.report.production_analytics.production_analytics as pa
		import erpnext.manufacturing.report.work_order_summary.work_order_summary as wo

		apply_calendar_patches()
		state = get_patch_state()
		for mod_name in STOCK_ANALYTICS_PERIOD_CONSUMERS:
			self.assertIn(mod_name, state.stk_rebound_modules)

		self.assertIs(pa.get_period_date_ranges, stk.get_period_date_ranges)
		self.assertIs(pa.get_period, stk.get_period)
		self.assertIs(pa.get_period_columns, stk.get_period_columns)
		self.assertIs(wo.get_period_date_ranges, stk.get_period_date_ranges)
		self.assertIs(wo.get_period, stk.get_period)
		self.assertIs(jc.get_period_date_ranges, stk.get_period_date_ranges)
		self.assertIs(jc.get_period, stk.get_period)
		# WO / JC do not import get_period_columns
		self.assertFalse(
			hasattr(wo, "get_period_columns") and wo.get_period_columns is stk.get_period_columns
		)

	def test_unrelated_same_name_not_replaced(self):
		apply_calendar_patches()
		import erpnext.controllers.trends as trends_mod

		# Trends get_period_date_ranges is a different function object / contract
		self.assertIsNot(trends_mod.get_period_date_ranges, stk.get_period_date_ranges)


class TestGregorianParity(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		self.calls = []
		calls = self.calls

		def fake_ranges(filters):
			calls.append("ranges")
			return [[date(2026, 1, 1), date(2026, 1, 31)]]

		def fake_period(posting_date, filters):
			calls.append(("period", posting_date))
			return "Jan 2026"

		def fake_columns(filters):
			calls.append("columns")
			return [{"label": "Jan 2026", "fieldname": "jan_2026", "fieldtype": "Float", "width": 120}]

		stk._original_get_period_date_ranges = fake_ranges
		stk._original_get_period = fake_period
		stk._original_get_period_columns = fake_columns

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_gregorian_delegates(self):
		filters = _filters(company="G Co", range="Monthly")
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			ranges = stk.get_period_date_ranges(filters)
			label = stk.get_period(date(2026, 1, 15), filters)
			cols = stk.get_period_columns(filters)
		self.assertEqual(self.calls[0], "ranges")
		self.assertEqual(ranges, [[date(2026, 1, 1), date(2026, 1, 31)]])
		self.assertEqual(label, "Jan 2026")
		self.assertEqual(cols[0]["fieldname"], "jan_2026")

	def test_weekly_delegates_for_jalali_company(self):
		filters = _filters(company="J Co", range="Weekly")
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			stk.get_period_date_ranges(filters)
		self.assertEqual(self.calls, ["ranges"])
		self.assertFalse(getattr(filters, "_pc_stk_jalali", False))


class TestJalaliStockPeriods(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def _ranges(self, rang, start, end, **extra):
		filters = _filters(company="J Co", range=rang, from_date=start, to_date=end, **extra)
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			ranges = stk.get_period_date_ranges(filters)
		return filters, ranges

	def test_monthly_farvardin_esfand(self):
		filters, ranges = self._ranges("Monthly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertTrue(filters._pc_stk_jalali)
		self.assertEqual(len(ranges), 12)
		self.assertEqual(ranges[0], [_j(1405, 1, 1), _j(1405, 1, 31)])
		self.assertEqual(ranges[11], [_j(1405, 12, 1), _j(1405, 12, 29)])
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(stk.get_period(_j(1405, 1, 15), filters), "j01_1405")
			self.assertEqual(stk.get_period(_j(1405, 12, 20), filters), "j12_1405")

	def test_quarterly(self):
		filters, ranges = self._ranges("Quarterly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertEqual(len(ranges), 4)
		self.assertEqual(ranges[0][1], _j(1405, 3, 31))
		self.assertEqual(ranges[1][0], _j(1405, 4, 1))
		self.assertEqual(ranges[2][0], _j(1405, 7, 1))
		self.assertEqual(ranges[3][0], _j(1405, 10, 1))
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(stk.get_period(_j(1405, 2, 1), filters), "jq1_1405")
			self.assertEqual(stk.get_period(_j(1405, 5, 1), filters), "jq2_1405")
			self.assertEqual(stk.get_period(_j(1405, 8, 1), filters), "jq3_1405")
			self.assertEqual(stk.get_period(_j(1405, 11, 1), filters), "jq4_1405")

	def test_half_yearly(self):
		filters, ranges = self._ranges("Half-Yearly", _j(1405, 1, 1), _j(1405, 12, 29))
		self.assertEqual(len(ranges), 2)
		self.assertEqual(ranges[0], [_j(1405, 1, 1), _j(1405, 6, 31)])
		self.assertEqual(ranges[1], [_j(1405, 7, 1), _j(1405, 12, 29)])
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(stk.get_period(_j(1405, 3, 1), filters), "jh1_1405")
			self.assertEqual(stk.get_period(_j(1405, 9, 1), filters), "jh2_1405")

	def test_yearly(self):
		fy_start, fy_end = _j(1405, 1, 1), _j(1405, 12, 29)
		filters = _filters(company="J Co", range="Yearly", from_date=fy_start, to_date=fy_end)
		with (
			patch(
				"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"erpnext.accounts.utils.get_fiscal_year",
				return_value=("FY-1405", fy_start, fy_end),
			),
		):
			ranges = stk.get_period_date_ranges(filters)
			key = stk.get_period(_j(1405, 6, 1), filters)
		self.assertEqual(len(ranges), 1)
		self.assertEqual(ranges[0], [fy_start, fy_end])
		self.assertTrue(key.startswith("j"))

	def test_leap_esfand(self):
		_filters_obj, ranges = self._ranges("Monthly", _j(1403, 1, 1), _j(1403, 12, 30))
		self.assertEqual(ranges[11][1], _j(1403, 12, 30))

	def test_partial_range(self):
		_f, ranges = self._ranges("Monthly", _j(1405, 4, 10), _j(1405, 6, 15))
		self.assertEqual(ranges[0][0], _j(1405, 4, 1))
		self.assertEqual(ranges[-1][1], _j(1405, 6, 15))

	def test_columns_stable_fieldnames(self):
		filters, _ranges = self._ranges("Monthly", _j(1405, 1, 1), _j(1405, 3, 31))
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			cols = stk.get_period_columns(filters)
		fieldnames = [c["fieldname"] for c in cols]
		labels = [c["label"] for c in cols]
		self.assertEqual(fieldnames[0], scrub("j01_1405"))
		self.assertNotEqual(fieldnames[0], scrub(str(labels[0])))
		self.assertEqual(len(fieldnames), len(set(fieldnames)))

	def test_display_calendar_independence(self):
		filters, ranges_a = self._ranges("Monthly", _j(1405, 1, 1), _j(1405, 12, 29))
		with (
			patch(
				"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch("frappe.local", MagicMock(lang="fa")),
		):
			ranges_b = stk.get_period_date_ranges(filters)
			k = stk.get_period(_j(1405, 1, 10), filters)
		self.assertEqual(ranges_a, ranges_b)
		self.assertEqual(k, "j01_1405")

	def test_bc_resolved_once(self):
		filters = _filters(company="J Co", range="Monthly", from_date=_j(1405, 1, 1), to_date=_j(1405, 3, 31))
		calls = []

		def tracking(company):
			calls.append(company)
			return "Jalali"

		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			side_effect=tracking,
		):
			stk.get_period_date_ranges(filters)
			for d in (_j(1405, 1, 5), _j(1405, 2, 5), _j(1405, 3, 5)):
				stk.get_period(d, filters)
		self.assertEqual(calls, ["J Co"])

	def test_engine_used(self):
		filters = _filters(company="J Co", range="Monthly", from_date=_j(1405, 1, 1), to_date=_j(1405, 2, 29))
		with (
			patch(
				"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch.object(BusinessPeriodEngine, "generate", wraps=BusinessPeriodEngine.generate) as gen,
		):
			stk.get_period_date_ranges(filters)
			gen.assert_called()


class TestCarryForward(unittest.TestCase):
	"""Carry-forward via unpatched get_periodic_data + patched get_period keys."""

	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_esfand_farvardin_and_empty_period(self):
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		# Esfand → Farvardin → (empty Ordibehesht) → Khordad SLE triggers fill
		from_date = _j(1404, 12, 1)
		to_date = _j(1405, 3, 31)
		filters = _filters(
			company="J Co",
			range="Monthly",
			from_date=from_date,
			to_date=to_date,
			value_quantity="Quantity",
		)

		entries = [
			frappe._dict(
				item_code="ITEM-A",
				warehouse="WH-1",
				posting_date=_j(1404, 12, 10),
				actual_qty=10,
				stock_value_difference=100,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=10,
			),
			frappe._dict(
				item_code="ITEM-A",
				warehouse="WH-1",
				posting_date=_j(1405, 1, 15),
				actual_qty=5,
				stock_value_difference=50,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=15,
			),
			# No SLE in Ordibehesht — fill_intermediate runs when Khordad SLE arrives
			frappe._dict(
				item_code="ITEM-A",
				warehouse="WH-1",
				posting_date=_j(1405, 3, 5),
				actual_qty=0,
				stock_value_difference=0,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=15,
			),
		]

		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			ranges = stk.get_period_date_ranges(filters)
			periodic = mod.get_periodic_data(entries, filters)

		keys = [stk.get_period(end, filters) for _s, end in ranges]
		self.assertEqual(keys[0], "j12_1404")
		self.assertEqual(keys[1], "j01_1405")
		self.assertEqual(keys[2], "j02_1405")
		self.assertEqual(keys[3], "j03_1405")

		self.assertEqual(periodic["ITEM-A"]["j12_1404"]["WH-1"], 10)
		self.assertEqual(periodic["ITEM-A"]["j01_1405"]["WH-1"], 15)
		# Empty Ordibehesht filled by fill_intermediate_periods from balance
		self.assertEqual(periodic["ITEM-A"]["j02_1405"]["WH-1"], 15)
		self.assertEqual(periodic["ITEM-A"]["j03_1405"]["WH-1"], 15)
		self.assertEqual(periodic["ITEM-A"]["balance"]["WH-1"], 15)

	def test_shahrivar_mehr_quarter_transition(self):
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		filters = _filters(
			company="J Co",
			range="Quarterly",
			from_date=_j(1405, 4, 1),
			to_date=_j(1405, 9, 30),
			value_quantity="Quantity",
		)
		entries = [
			frappe._dict(
				item_code="ITEM-Q",
				warehouse="WH-1",
				posting_date=_j(1405, 6, 20),  # Q2 Tir-Shahrivar
				actual_qty=3,
				stock_value_difference=30,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=3,
			),
			frappe._dict(
				item_code="ITEM-Q",
				warehouse="WH-1",
				posting_date=_j(1405, 7, 5),  # Q3 Mehr-Azar
				actual_qty=-1,
				stock_value_difference=-10,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=2,
			),
		]
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			stk.get_period_date_ranges(filters)
			periodic = mod.get_periodic_data(entries, filters)

		self.assertEqual(periodic["ITEM-Q"]["jq2_1405"]["WH-1"], 3)
		self.assertEqual(periodic["ITEM-Q"]["jq3_1405"]["WH-1"], 2)

	def test_value_carry_forward(self):
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		filters = _filters(
			company="J Co",
			range="Monthly",
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 3, 31),
			value_quantity="Value",
		)
		entries = [
			frappe._dict(
				item_code="ITEM-V",
				warehouse="WH-1",
				posting_date=_j(1405, 1, 10),
				actual_qty=1,
				stock_value_difference=200,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=1,
			),
			# Later SLE so fill_intermediate copies value into empty Ordibehesht
			frappe._dict(
				item_code="ITEM-V",
				warehouse="WH-1",
				posting_date=_j(1405, 3, 5),
				actual_qty=0,
				stock_value_difference=0,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=1,
			),
		]
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			stk.get_period_date_ranges(filters)
			periodic = mod.get_periodic_data(entries, filters)
		self.assertEqual(periodic["ITEM-V"]["j01_1405"]["WH-1"], 200)
		self.assertEqual(periodic["ITEM-V"]["j02_1405"]["WH-1"], 200)
		self.assertEqual(periodic["ITEM-V"]["j03_1405"]["WH-1"], 200)

	def test_opening_before_from_date_updates_balance(self):
		import erpnext.stock.report.stock_analytics.stock_analytics as mod

		filters = _filters(
			company="J Co",
			range="Monthly",
			from_date=_j(1405, 2, 1),
			to_date=_j(1405, 2, 29),
			value_quantity="Quantity",
		)
		entries = [
			frappe._dict(
				item_code="ITEM-O",
				warehouse="WH-1",
				posting_date=_j(1405, 1, 10),  # before from_date
				actual_qty=7,
				stock_value_difference=70,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=7,
			),
			frappe._dict(
				item_code="ITEM-O",
				warehouse="WH-1",
				posting_date=_j(1405, 2, 10),
				actual_qty=1,
				stock_value_difference=10,
				voucher_type="Stock Entry",
				batch_no=None,
				qty_after_transaction=8,
			),
		]
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			stk.get_period_date_ranges(filters)
			periodic = mod.get_periodic_data(entries, filters)
		self.assertEqual(periodic["ITEM-O"]["balance"]["WH-1"], 8)
		self.assertEqual(periodic["ITEM-O"]["j02_1405"]["WH-1"], 8)


class TestDependentReportsSmoke(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		# Import before patch
		import erpnext.manufacturing.report.job_card_summary.job_card_summary as jc
		import erpnext.manufacturing.report.production_analytics.production_analytics as pa
		import erpnext.manufacturing.report.work_order_summary.work_order_summary as wo

		self.pa = pa
		self.wo = wo
		self.jc = jc
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_production_analytics_build_ranges_jalali(self):
		filters = _filters(
			company="J Co",
			range="Monthly",
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 3, 31),
		)
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			ranges = self.pa.build_ranges(filters)
			cols = self.pa.get_period_columns(filters)
		self.assertEqual(len(ranges), 3)
		self.assertEqual(ranges[0][2], "j01_1405")
		fieldnames = [c["fieldname"] for c in cols]
		self.assertEqual(fieldnames[0], scrub("j01_1405"))
		# No KeyError path: scrub(period) matches column fieldnames
		for _fd, _td, period in ranges:
			self.assertIn(scrub(period), fieldnames)

	def test_work_order_prepare_chart_uses_rebound_helpers(self):
		filters = _filters(
			company="J Co",
			range="Weekly",  # will be forced to Monthly inside prepare_chart_data
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 2, 29),
			charts_based_on="Quantity",
		)
		data = [
			frappe._dict(
				planned_start_date=_j(1405, 1, 15),
				qty=10,
				produced_qty=4,
				status="Not Started",
				age=0,
			)
		]
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			labels, periodic = self.wo.prepare_chart_data(data, filters)
		self.assertIn("j01_1405", labels)
		self.assertEqual(periodic["Pending"]["j01_1405"], 6)
		self.assertEqual(periodic["Completed"]["j01_1405"], 4)

	def test_job_card_prepare_chart_uses_rebound_helpers(self):
		filters = _filters(
			company="J Co",
			from_date=_j(1405, 1, 1),
			to_date=_j(1405, 2, 29),
		)
		details = [
			frappe._dict(posting_date=_j(1405, 1, 20), status="Completed"),
			frappe._dict(posting_date=_j(1405, 1, 25), status="Open"),
		]
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			labels, periodic = self.jc.prepare_chart_data(details, filters)
		self.assertIn("j01_1405", labels)
		self.assertEqual(periodic["Completed"]["j01_1405"], 1)
		self.assertEqual(periodic["Open"]["j01_1405"], 1)


class TestPerformanceNote(unittest.TestCase):
	def test_large_synthetic_mapping_is_linear_in_periods(self):
		"""Map many posting dates against a cached period index (no per-row BC resolve)."""
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		filters = _filters(
			company="J Co",
			range="Monthly",
			from_date=_j(1400, 1, 1),
			to_date=_j(1405, 12, 29),
		)
		resolve_calls = []

		def tracking(company):
			resolve_calls.append(company)
			return "Jalali"

		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			side_effect=tracking,
		):
			ranges = stk.get_period_date_ranges(filters)
			# Simulate dense SLE posting dates across the year span
			for i in range(5000):
				# Cycle through generated period midpoints
				_s, end = ranges[i % len(ranges)]
				stk.get_period(end, filters)
		self.assertEqual(len(resolve_calls), 1)
		self.assertGreater(len(ranges), 12)
		reset_calendar_patches_for_tests()


class TestGregorianStockParityAgainstOriginal(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_monthly_ranges_match_captured_original(self):
		filters = _filters(
			company="G Co",
			range="Monthly",
			from_date=date(2026, 2, 15),
			to_date=date(2026, 5, 10),
		)
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			adapted = stk.get_period_date_ranges(filters)
			original = get_patch_state().original_stk_get_period_date_ranges(filters)
		self.assertEqual(
			[[getdate(a), getdate(b)] for a, b in adapted],
			[[getdate(a), getdate(b)] for a, b in original],
		)

	def test_weekly_matches_original(self):
		filters = _filters(
			company="J Co",
			range="Weekly",
			from_date=date(2026, 3, 10),
			to_date=date(2026, 4, 5),
		)
		with patch(
			"persian_calendar.calendar.integrations.stock_analytics.get_business_calendar_for_company",
			return_value="Jalali",
		):
			adapted = stk.get_period_date_ranges(filters)
			original = get_patch_state().original_stk_get_period_date_ranges(filters)
		self.assertEqual(
			[[getdate(a), getdate(b)] for a, b in adapted],
			[[getdate(a), getdate(b)] for a, b in original],
		)


if __name__ == "__main__":
	unittest.main()
