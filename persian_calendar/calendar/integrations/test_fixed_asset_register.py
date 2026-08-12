"""Fixed Asset Register chart adapter — Business Calendar tests (2.0.0)."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import frappe
import jdatetime
from frappe.tests.utils import FrappeTestCase
from frappe.utils import formatdate

from persian_calendar.calendar.adapter_helpers import (
	aggregate_by_period_bounds,
	find_period_for_date,
	find_period_index_for_date,
)
from persian_calendar.calendar.integrations import fixed_asset_register as far
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


class TestPeriodAllocationHelpers(unittest.TestCase):
	def test_find_period_for_date_inclusive_bounds(self):
		periods = [
			frappe._dict(
				from_date=date(2026, 3, 21),
				to_date=date(2026, 4, 20),
				label="Farvardin 1405",
				key="j01_1405",
			),
			frappe._dict(
				from_date=date(2026, 4, 21),
				to_date=date(2026, 5, 21),
				label="Ordibehesht 1405",
				key="j02_1405",
			),
		]
		# 2026-04-05 is Farvardin 1405 (not Apr Gregorian label)
		p = find_period_for_date(periods, date(2026, 4, 5))
		self.assertEqual(p.label, "Farvardin 1405")
		self.assertEqual(find_period_index_for_date(periods, date(2026, 4, 5)), 0)
		self.assertEqual(find_period_for_date(periods, date(2026, 4, 21)).label, "Ordibehesht 1405")
		self.assertIsNone(find_period_for_date(periods, date(2026, 3, 20)))
		self.assertIsNone(find_period_for_date([], date(2026, 4, 5)))

	def test_aggregate_by_period_bounds_not_by_label(self):
		periods = [
			frappe._dict(
				from_date=date(2026, 3, 21),
				to_date=date(2026, 4, 20),
				label="Farvardin 1405",
			),
		]
		rows = [
			{"purchase_date": date(2026, 4, 5), "asset_value": 100.0, "depreciated_amount": 10.0},
		]
		# Gregorian display label would be Apr 2026 — must not be used as key
		self.assertEqual(formatdate(date(2026, 4, 5), "MMM YYYY"), "Apr 2026")

		def accumulate(bucket, row):
			bucket["asset_value"] += row["asset_value"]

		pairs = aggregate_by_period_bounds(
			periods,
			rows,
			date_of=lambda r: r["purchase_date"],
			accumulate=accumulate,
			empty_bucket=lambda: {"asset_value": 0.0},
		)
		self.assertEqual(len(pairs), 1)
		self.assertEqual(pairs[0][0].label, "Farvardin 1405")
		self.assertEqual(pairs[0][1]["asset_value"], 100.0)

	def test_boundary_dates(self):
		periods = [
			frappe._dict(from_date=date(2026, 3, 21), to_date=date(2027, 3, 20), label="FY1405"),
		]
		self.assertIsNotNone(find_period_for_date(periods, date(2026, 3, 21)))
		self.assertIsNotNone(find_period_for_date(periods, date(2027, 3, 20)))
		self.assertIsNone(find_period_for_date(periods, date(2026, 3, 20)))
		self.assertIsNone(find_period_for_date(periods, date(2027, 3, 21)))


class TestFixedAssetRegisterPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_prepare_chart_data_replaced_on_module(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.assets.report.fixed_asset_register.fixed_asset_register as mod

		self.assertIs(mod.prepare_chart_data, far.prepare_chart_data)
		state = get_patch_state()
		self.assertTrue(state.fixed_asset_register_patched)
		self.assertIsNotNone(state.original_far_prepare_chart_data)
		self.assertIsNot(state.original_far_prepare_chart_data, far.prepare_chart_data)

	def test_idempotent_apply(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import erpnext.assets.report.fixed_asset_register.fixed_asset_register as mod

		self.assertIs(mod.prepare_chart_data, far.prepare_chart_data)


class TestFixedAssetRegisterGregorianDelegation(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_gregorian_calls_captured_original(self):
		sentinel = object()

		def fake_chart(data, filters):
			return sentinel

		with (
			patch.object(far, "_original_prepare_chart_data", fake_chart),
			patch(
				"persian_calendar.calendar.integrations.fixed_asset_register.get_business_calendar_for_company",
				return_value="Gregorian",
			),
		):
			out = far.prepare_chart_data([], frappe._dict(company="G Co"))
		self.assertIs(out, sentinel)


class TestFixedAssetRegisterJalaliChart(FrappeTestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_apr_2026_asset_allocates_to_farvardin_without_keyerror(self):
		"""Confirmed 2.0.0 regression: purchase_date 2026-04-05 under FY 1405."""
		# Farvardin 1405 ≈ 2026-03-21 .. 2026-04-20
		self.assertEqual(_j(1405, 1, 1), date(2026, 3, 21))
		purchase = date(2026, 4, 5)
		self.assertEqual(formatdate(purchase, "MMM YYYY"), "Apr 2026")

		period_list = [
			frappe._dict(
				from_date=date(2026, 3, 21),
				to_date=date(2026, 4, 20),
				label="Farvardin 1405",
				key="j01_1405",
			),
			frappe._dict(
				from_date=date(2026, 4, 21),
				to_date=date(2026, 5, 21),
				label="Ordibehesht 1405",
				key="j02_1405",
			),
		]
		data = [
			{
				"purchase_date": purchase,
				"asset_value": 1500.0,
				"depreciated_amount": 50.0,
			}
		]
		filters = frappe._dict(
			company="Jalali Co",
			filter_based_on="Fiscal Year",
			date_based_on="Purchase Date",
			from_fiscal_year="1405",
			to_fiscal_year="1405",
			from_date=date(2025, 8, 12),
			to_date=date(2026, 8, 12),
		)

		with (
			patch(
				"persian_calendar.calendar.integrations.fixed_asset_register.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"erpnext.accounts.report.financial_statements.get_period_list",
				return_value=period_list,
			),
		):
			chart = far.prepare_chart_data(data, filters)

		self.assertIsNotNone(chart)
		labels = list(chart["data"]["labels"])
		self.assertEqual(labels[0], "Farvardin 1405")
		self.assertNotIn("Apr 2026", labels)
		self.assertEqual(chart["data"]["datasets"][0]["values"][0], 1500.0)
		self.assertEqual(chart["data"]["datasets"][1]["values"][0], 50.0)
		# Ordibehesht empty
		self.assertEqual(chart["data"]["datasets"][0]["values"][1], 0.0)

	def test_date_range_mode_jalali(self):
		period_list = [
			frappe._dict(
				from_date=date(2026, 3, 21),
				to_date=date(2026, 4, 20),
				label="Farvardin 1405",
				key="j01_1405",
			),
		]
		data = [{"purchase_date": date(2026, 4, 5), "asset_value": 10.0, "depreciated_amount": 1.0}]
		filters = frappe._dict(
			company="Jalali Co",
			filter_based_on="Date Range",
			date_based_on="Purchase Date",
			from_date=date(2026, 3, 21),
			to_date=date(2026, 4, 20),
		)
		with (
			patch(
				"persian_calendar.calendar.integrations.fixed_asset_register.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"erpnext.accounts.report.financial_statements.get_period_list",
				return_value=period_list,
			),
		):
			chart = far.prepare_chart_data(data, filters)
		self.assertEqual(list(chart["data"]["labels"]), ["Farvardin 1405"])
		self.assertEqual(chart["data"]["datasets"][0]["values"][0], 10.0)

	def test_contract_present(self):
		from persian_calendar.calendar.contracts import CONTRACTS

		c = next(x for x in CONTRACTS if x.id == "far.prepare_chart_data")
		self.assertEqual(c.attr, "prepare_chart_data")
