"""Phase 5A-3 — Sales Pipeline Analytics Business Calendar tests."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import frappe
import jdatetime
from frappe import scrub
from frappe.tests.utils import FrappeTestCase

from persian_calendar.calendar.integrations import sales_pipeline_analytics as spa
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label


def _j(y, m, d):
	"""Independently verified Jalali → Gregorian (not via adapter under test)."""
	return jdatetime.date(y, m, d).togregorian()


def _filters(**kwargs):
	base = {
		"pipeline_by": "Sales Stage",
		"range": "Monthly",
		"based_on": "Number",
		"company": "SPA Test Co",
		"from_date": date(2025, 3, 1),
		"to_date": date(2025, 4, 30),
		"status": None,
		"opportunity_type": None,
		"opportunity_source": None,
		"assigned_to": None,
	}
	base.update(kwargs)
	return frappe._dict(base)


class TestSalesPipelinePatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_execute_replaced_on_module(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics as mod

		self.assertIs(mod.execute, spa.execute)
		state = get_patch_state()
		self.assertTrue(state.sales_pipeline_patched)
		self.assertIsNotNone(state.original_sales_pipeline_execute)
		self.assertIsNot(state.original_sales_pipeline_execute, spa.execute)

	def test_idempotent_apply(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics as mod

		self.assertIs(mod.execute, spa.execute)

	def test_import_before_patch_then_apply(self):
		import erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics as mod

		before = mod.execute
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		self.assertIs(mod.execute, spa.execute)
		self.assertIsNot(before, spa.execute)


class TestSalesPipelineGregorianDelegation(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_gregorian_calls_captured_original(self):
		sentinel = object()

		def fake_execute(filters=None):
			return sentinel

		with (
			patch.object(spa, "_original_execute", fake_execute),
			patch(
				"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
				return_value="Gregorian",
			),
		):
			self.assertIs(spa.execute(_filters()), sentinel)

	def test_missing_company_delegates_gregorian(self):
		sentinel = object()

		def fake_execute(filters=None):
			return sentinel

		with patch.object(spa, "_original_execute", fake_execute):
			filters = _filters()
			filters.company = None
			self.assertIs(spa.execute(filters), sentinel)


class TestSalesPipelineJalaliAllocation(unittest.TestCase):
	"""Allocation unit tests — no DB Opportunities required."""

	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_esfand_farvardin_split_proves_sql_month_wrong(self):
		"""2025-03-20 (Esfand 30 1403) and 2025-03-21 (Farvardin 1 1404) are same Gregorian month."""
		esfand = _j(1403, 12, 30)
		farvardin = _j(1404, 1, 1)
		self.assertEqual(esfand, date(2025, 3, 20))
		self.assertEqual(farvardin, date(2025, 3, 21))
		self.assertEqual(esfand.month, farvardin.month)

		periods = BusinessPeriodEngine.generate(
			start_date=_j(1403, 12, 1),
			end_date=_j(1404, 1, 29),
			periodicity="Monthly",
			provider=__import__(
				"persian_calendar.calendar.engine", fromlist=["CalendarEngine"]
			).CalendarEngine.jalali(),
		)
		keys = {p.key for p in periods}
		self.assertIn("j12_1403", keys)
		self.assertIn("j01_1404", keys)

		from persian_calendar.calendar.adapter_helpers import lookup_period_key, period_bounds_index

		bounds = period_bounds_index(periods)
		self.assertEqual(lookup_period_key(esfand, bounds), "j12_1403")
		self.assertEqual(lookup_period_key(farvardin, bounds), "j01_1404")

	def test_jalali_quarter_boundary_proves_sql_quarter_wrong(self):
		"""Esfand (Jalali Q4) vs Farvardin (Jalali Q1) — both Gregorian Q1 2025."""
		esfand = _j(1403, 12, 30)
		farvardin = _j(1404, 1, 1)
		self.assertEqual((esfand.month - 1) // 3 + 1, 1)
		self.assertEqual((farvardin.month - 1) // 3 + 1, 1)

		from persian_calendar.calendar.engine import CalendarEngine

		periods = BusinessPeriodEngine.generate(
			start_date=_j(1403, 10, 1),
			end_date=_j(1404, 3, 31),
			periodicity="Quarterly",
			provider=CalendarEngine.jalali(),
		)
		from persian_calendar.calendar.adapter_helpers import lookup_period_key, period_bounds_index

		bounds = period_bounds_index(periods)
		self.assertEqual(lookup_period_key(esfand, bounds), "jq4_1403")
		self.assertEqual(lookup_period_key(farvardin, bounds), "jq1_1404")

	@patch(
		"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch("persian_calendar.calendar.integrations.sales_pipeline_analytics._fetch_opportunity_rows")
	def test_jalali_monthly_aggregation_and_keys(self, fetch, _bc):
		esfand = _j(1403, 12, 30)
		farvardin = _j(1404, 1, 1)
		fetch.return_value = [
			{"sales_stage": "Prospecting", "expected_closing": esfand},
			{"sales_stage": "Prospecting", "expected_closing": farvardin},
			{"sales_stage": "Qualification", "expected_closing": farvardin},
			{"sales_stage": "Prospecting", "expected_closing": None},
		]
		columns, data, _msg, chart = spa.execute(
			_filters(
				from_date=_j(1403, 12, 1),
				to_date=_j(1404, 1, 29),
				range="Monthly",
				based_on="Number",
				pipeline_by="Sales Stage",
			)
		)
		fieldnames = [c["fieldname"] for c in columns if c["fieldname"] != "sales_stage"]
		self.assertIn(scrub("j12_1403"), fieldnames)
		self.assertIn(scrub("j01_1404"), fieldnames)
		# Labels must not be used as fieldnames
		for c in columns:
			if c["fieldname"] in (scrub("j12_1403"), scrub("j01_1404")):
				self.assertNotEqual(c["fieldname"], scrub(c["label"]))

		by_stage = {r["sales_stage"]: r for r in data}
		self.assertEqual(by_stage["Prospecting"][scrub("j12_1403")], 1.0)
		self.assertEqual(by_stage["Prospecting"][scrub("j01_1404")], 1.0)
		self.assertEqual(by_stage["Qualification"][scrub("j01_1404")], 1.0)
		self.assertEqual(by_stage["Qualification"].get(scrub("j12_1403"), 0.0), 0.0)

		# Chart/table same period count and order
		self.assertEqual(len(chart["data"]["labels"]), len(fieldnames))
		self.assertEqual(len(chart["data"]["datasets"][0]["values"]), len(fieldnames))

	@patch(
		"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch("persian_calendar.calendar.integrations.sales_pipeline_analytics._fetch_opportunity_rows")
	def test_jalali_quarterly_aggregation(self, fetch, _bc):
		fetch.return_value = [
			{"sales_stage": "Prospecting", "expected_closing": _j(1403, 12, 15)},
			{"sales_stage": "Prospecting", "expected_closing": _j(1404, 1, 10)},
		]
		_columns, data, _msg, chart = spa.execute(
			_filters(
				from_date=_j(1403, 10, 1),
				to_date=_j(1404, 3, 31),
				range="Quarterly",
				based_on="Number",
				pipeline_by="Sales Stage",
			)
		)
		row = data[0]
		self.assertEqual(row[scrub("jq4_1403")], 1.0)
		self.assertEqual(row[scrub("jq1_1404")], 1.0)
		self.assertEqual(len(chart["data"]["labels"]), len(chart["data"]["datasets"][0]["values"]))

	@patch(
		"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch("persian_calendar.calendar.integrations.sales_pipeline_analytics._fetch_opportunity_rows")
	def test_amount_precision_uses_flt(self, fetch, _bc):
		fetch.return_value = [
			{
				"sales_stage": "Prospecting",
				"expected_closing": _j(1404, 1, 15),
				"amount": 100.55,
				"currency": "IRR",
			},
			{
				"sales_stage": "Prospecting",
				"expected_closing": _j(1404, 1, 16),
				"amount": 0.45,
				"currency": "IRR",
			},
		]
		with patch(
			"persian_calendar.calendar.integrations.sales_pipeline_analytics._convert_amounts_to_company_currency"
		):
			_columns, data, _msg, _chart = spa.execute(
				_filters(
					from_date=_j(1404, 1, 1),
					to_date=_j(1404, 1, 31),
					range="Monthly",
					based_on="Amount",
					pipeline_by="Sales Stage",
					company="SPA Test Co",
				)
			)
		self.assertAlmostEqual(data[0][scrub("j01_1404")], 101.0, places=6)

	@patch(
		"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch("persian_calendar.calendar.integrations.sales_pipeline_analytics._fetch_opportunity_rows")
	def test_display_calendar_does_not_change_business_labels(self, fetch, _bc):
		fetch.return_value = [
			{"sales_stage": "Prospecting", "expected_closing": _j(1404, 1, 10)},
		]
		filters = _filters(
			from_date=_j(1404, 1, 1),
			to_date=_j(1404, 1, 31),
			range="Monthly",
		)
		with patch(
			"persian_calendar.jalali_support.formatters.get_effective_display_calendar",
			return_value="Gregorian",
		):
			_c1, _d1, _m1, chart1 = spa.execute(filters)
		with patch(
			"persian_calendar.jalali_support.formatters.get_effective_display_calendar",
			return_value="Jalali",
		):
			_c2, _d2, _m2, chart2 = spa.execute(filters)
		self.assertEqual(chart1["data"]["labels"], chart2["data"]["labels"])

	@patch(
		"persian_calendar.calendar.integrations.sales_pipeline_analytics.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch("persian_calendar.calendar.integrations.sales_pipeline_analytics._fetch_opportunity_rows")
	def test_empty_periods_zero_filled_for_pipeline_with_data(self, fetch, _bc):
		fetch.return_value = [
			{"sales_stage": "Prospecting", "expected_closing": _j(1404, 2, 10)},
		]
		_columns, data, _msg, _chart = spa.execute(
			_filters(
				from_date=_j(1404, 1, 1),
				to_date=_j(1404, 3, 31),
				range="Monthly",
			)
		)
		row = data[0]
		self.assertEqual(row[scrub("j02_1404")], 1.0)
		self.assertEqual(row[scrub("j01_1404")], 0.0)
		self.assertEqual(row[scrub("j03_1404")], 0.0)

	def test_period_label_uses_framework_formatter(self):
		from persian_calendar.calendar.engine import CalendarEngine

		periods = BusinessPeriodEngine.generate(
			start_date=_j(1404, 1, 1),
			end_date=_j(1404, 1, 31),
			periodicity="Monthly",
			provider=CalendarEngine.jalali(),
		)
		label_fa = format_period_label(periods[0], locale="fa")
		label_en = format_period_label(periods[0], locale="en")
		self.assertIn("فروردین", label_fa)
		self.assertIn("Farvardin", label_en)


class TestSalesPipelineContracts(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	@classmethod
	def tearDownClass(cls):
		reset_calendar_patches_for_tests()

	def test_spa_contract_passes(self):
		from persian_calendar.calendar.contracts import CONTRACTS, check_callable_contract

		contract = next(c for c in CONTRACTS if c.id == "spa.execute")
		errors = check_callable_contract(contract)
		self.assertEqual(errors, [], msg="\n".join(errors))


if __name__ == "__main__":
	unittest.main()
