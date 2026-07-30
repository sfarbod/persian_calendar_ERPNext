"""Phase 6A — HRMS Vehicle Expenses Business Calendar tests."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import frappe
import jdatetime
from frappe.tests.utils import FrappeTestCase

from persian_calendar.calendar.integrations import vehicle_expenses as ve
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)


def _j(y, m, d):
	"""Independently verified Jalali → Gregorian (not via adapter under test)."""
	return jdatetime.date(y, m, d).togregorian()


def _filters(**kwargs):
	base = {
		"filter_based_on": "Date Range",
		"from_date": date(2025, 3, 1),
		"to_date": date(2025, 4, 30),
		"fiscal_year": None,
		"company": "VE Test Co",
	}
	base.update(kwargs)
	return frappe._dict(base)


def _row(d, fuel=10.0, service=5.0):
	return frappe._dict(
		date=d,
		fuel_expense=fuel,
		service_expense=service,
	)


class TestVehicleExpensesPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_get_chart_data_replaced_on_module(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import hrms.hr.report.vehicle_expenses.vehicle_expenses as mod

		self.assertIs(mod.get_chart_data, ve.get_chart_data)
		state = get_patch_state()
		self.assertTrue(state.vehicle_expenses_patched)
		self.assertIsNotNone(state.original_vehicle_expenses_get_chart_data)
		self.assertIsNot(state.original_vehicle_expenses_get_chart_data, ve.get_chart_data)

	def test_idempotent_apply(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		import hrms.hr.report.vehicle_expenses.vehicle_expenses as mod

		self.assertIs(mod.get_chart_data, ve.get_chart_data)

	def test_soft_skip_without_hrms(self):
		from persian_calendar.calendar import patches as patches_mod

		reset_calendar_patches_for_tests()
		real_import = __import__

		def selective_import(name, globals=None, locals=None, fromlist=(), level=0):
			target = "hrms.hr.report.vehicle_expenses.vehicle_expenses"
			if name == target or (name == "hrms" and fromlist):
				# Only block the vehicle_expenses leaf import used by the applicator
				if name == target or (
					fromlist and any(str(x).startswith("hr") or str(x) == "vehicle_expenses" for x in fromlist)
				):
					# Still allow unrelated hrms imports during other patches
					pass
			if name == target:
				raise ImportError("simulated missing HRMS")
			return real_import(name, globals, locals, fromlist, level)

		with patch("builtins.__import__", side_effect=selective_import):
			status = patches_mod._apply_vehicle_expenses_patch()
		self.assertEqual(status, PatchStatus.APPLIED)
		self.assertFalse(get_patch_state().vehicle_expenses_patched)

		# Real path when HRMS is present
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		self.assertTrue(get_patch_state().vehicle_expenses_patched)


class TestVehicleExpensesGregorianDelegation(unittest.TestCase):
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
			patch.object(ve, "_original_get_chart_data", fake_chart),
			patch(
				"persian_calendar.calendar.integrations.vehicle_expenses.get_business_calendar_for_company",
				return_value="Gregorian",
			),
		):
			self.assertIs(ve.get_chart_data([], _filters()), sentinel)

	def test_missing_company_delegates_gregorian(self):
		sentinel = object()

		def fake_chart(data, filters):
			return sentinel

		with patch.object(ve, "_original_get_chart_data", fake_chart):
			filters = _filters()
			filters.company = None
			self.assertIs(ve.get_chart_data([], filters), sentinel)


class TestVehicleExpensesJalaliChart(FrappeTestCase):
	def setUp(self):
		super().setUp()
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()
		super().tearDown()

	@patch(
		"persian_calendar.calendar.integrations.vehicle_expenses.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch(
		"persian_calendar.calendar.integrations.financial_statements.get_business_calendar_for_company",
		return_value="Jalali",
	)
	def test_esfand_farvardin_boundary_allocation(self, _fs_bc, _ve_bc):
		"""2025-03-20 → Esfand 1403; 2025-03-21 → Farvardin 1404."""
		esfand_day = _j(1403, 12, 30)  # 2025-03-20 (leap Esfand)
		farvardin_day = _j(1404, 1, 1)  # 2025-03-21
		self.assertEqual(esfand_day, date(2025, 3, 20))
		self.assertEqual(farvardin_day, date(2025, 3, 21))

		data = [
			_row(esfand_day, fuel=100.0, service=0.0),
			_row(farvardin_day, fuel=50.0, service=25.0),
		]
		# Range covers full Esfand 1403 through Farvardin 1404 (same pattern as SPA tests)
		filters = _filters(
			from_date=_j(1403, 12, 1),
			to_date=_j(1404, 1, 31),
		)

		from erpnext.accounts.report.financial_statements import get_period_list

		period_list = get_period_list(
			None,
			None,
			filters.from_date,
			filters.to_date,
			"Date Range",
			"Monthly",
			company=filters.company,
		)
		keys = [p.key for p in period_list]
		self.assertIn("j12_1403", keys)
		self.assertIn("j01_1404", keys)

		chart = ve.get_chart_data(data, filters)
		fuel_values = chart["data"]["datasets"][0]["values"]
		service_values = chart["data"]["datasets"][1]["values"]

		esfand_idx = keys.index("j12_1403")
		far_idx = keys.index("j01_1404")
		self.assertEqual(fuel_values[esfand_idx], 100.0)
		self.assertEqual(fuel_values[far_idx], 50.0)
		self.assertEqual(service_values[far_idx], 25.0)
		self.assertEqual(service_values[esfand_idx], 0.0)

	@patch(
		"persian_calendar.calendar.integrations.vehicle_expenses.get_business_calendar_for_company",
		return_value="Jalali",
	)
	@patch(
		"persian_calendar.calendar.integrations.financial_statements.get_business_calendar_for_company",
		return_value="Jalali",
	)
	def test_chart_keys_are_period_keys_not_labels(self, _fs_bc, _ve_bc):
		from erpnext.accounts.report.financial_statements import get_period_list

		filters = _filters(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31))
		period_list = get_period_list(
			None,
			None,
			filters.from_date,
			filters.to_date,
			"Date Range",
			"Monthly",
			company=filters.company,
		)
		chart = ve.get_chart_data([], filters)
		self.assertEqual(chart["data"]["labels"], [p.label for p in period_list])
		self.assertTrue(chart["data"]["datasets"])
		for ds in chart["data"]["datasets"]:
			self.assertEqual(len(ds["values"]), len(period_list))
			self.assertTrue(all(v == 0 for v in ds["values"]))

	@patch(
		"persian_calendar.calendar.integrations.vehicle_expenses.get_business_calendar_for_company",
		return_value="Jalali",
	)
	def test_company_switching_changes_path(self, mock_bc):
		"""Jalali company uses adapter path; Gregorian uses original."""
		sentinel = {"stock": True}
		calls = {"orig": 0}

		def fake_orig(data, filters):
			calls["orig"] += 1
			return sentinel

		with patch.object(ve, "_original_get_chart_data", fake_orig):
			mock_bc.return_value = "Jalali"
			jalali_chart = ve.get_chart_data([], _filters(company="Jalali Co"))
			self.assertNotEqual(jalali_chart, sentinel)
			self.assertEqual(calls["orig"], 0)

			mock_bc.return_value = "Gregorian"
			self.assertIs(ve.get_chart_data([], _filters(company="Greg Co")), sentinel)
			self.assertEqual(calls["orig"], 1)


class TestVehicleExpensesContracts(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_contract_passes(self):
		from persian_calendar.calendar.contracts import CONTRACTS, check_callable_contract

		c = next(x for x in CONTRACTS if x.id == "hrms.vehicle_expenses.get_chart_data")
		self.assertTrue(c.optional)
		self.assertEqual(check_callable_contract(c), [])


class TestHRMSDisplayCalendarInventory(unittest.TestCase):
	"""HRMS forms/lists inherit global Display Calendar — no dedicated adapters."""

	def test_no_hrms_display_adapter_module(self):
		import importlib.util

		spec = importlib.util.find_spec(
			"persian_calendar.calendar.integrations.hrms_display"
		)
		self.assertIsNone(spec)

	def test_vehicle_expenses_js_in_bundle(self):
		from pathlib import Path

		bundle = Path(__file__).resolve().parents[2] / "public/js/jalali_support.bundle.js"
		text = bundle.read_text()
		self.assertIn("hrms_vehicle_expenses.js", text)

	def test_monthly_attendance_not_registered_as_bc(self):
		from persian_calendar.calendar.registry import INTEGRATED_MODULES

		ve = next(m for m in INTEGRATED_MODULES if m.name == "HRMS Vehicle Expenses")
		self.assertEqual(ve.status, "implemented")
		deferred = next(
			m for m in INTEGRATED_MODULES if m.name == "HRMS Payroll / Attendance period reports"
		)
		self.assertEqual(deferred.status, "deferred")
