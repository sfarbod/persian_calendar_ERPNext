"""Lifecycle tests for the multi-context calendar patch applicator.

Controls import order explicitly. Does not rely on accidental module load order.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from persian_calendar.calendar import patches as patch_mod
from persian_calendar.calendar.integrations import financial_statements as fs_adapter
from persian_calendar.calendar.patches import (
	FS_MODULE_PATH,
	GET_PERIOD_LIST_CONSUMERS,
	PatchStatus,
	apply_calendar_patches,
	before_job_calendar_bootstrap,
	before_request_calendar_bootstrap,
	before_tests_calendar_bootstrap,
	get_patch_state,
	reset_calendar_patches_for_tests,
)


class TestCalendarPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_idempotency_keeps_same_original_and_adapter(self):
		status1 = apply_calendar_patches()
		self.assertEqual(status1, PatchStatus.APPLIED)
		state1 = get_patch_state()
		original = state1.original_get_period_list
		adapter = state1.adapter_get_period_list

		status2 = apply_calendar_patches()
		self.assertEqual(status2, PatchStatus.APPLIED)
		state2 = get_patch_state()
		self.assertIs(state2.original_get_period_list, original)
		self.assertIs(state2.adapter_get_period_list, adapter)
		self.assertIsNot(original, adapter)

		import erpnext.accounts.report.financial_statements as fs_mod

		self.assertIs(fs_mod.get_period_list, adapter)

	def test_consumer_imported_after_patch_receives_adapter(self):
		apply_calendar_patches()
		adapter = get_patch_state().adapter_get_period_list

		# Force re-import of a consumer after patch (simulate first load)
		mod_name = "erpnext.accounts.report.financial_ratios.financial_ratios"
		sys.modules.pop(mod_name, None)
		import erpnext.accounts.report.financial_ratios.financial_ratios as fr

		self.assertIs(fr.get_period_list, adapter)

	def test_consumer_imported_before_patch_is_rebound(self):
		# Ensure stock is restored, then import consumer BEFORE patch
		reset_calendar_patches_for_tests()
		import erpnext.accounts.report.financial_statements as fs_mod

		stock = fs_mod.get_period_list
		mod_name = "erpnext.accounts.report.cash_flow.cash_flow"
		sys.modules.pop(mod_name, None)
		import erpnext.accounts.report.cash_flow.cash_flow as cf

		self.assertIs(cf.get_period_list, stock)

		apply_calendar_patches()
		adapter = get_patch_state().adapter_get_period_list
		self.assertIs(cf.get_period_list, adapter)
		self.assertIsNot(cf.get_period_list, stock)
		self.assertIn(mod_name, get_patch_state().rebound_modules)

	def test_unrelated_same_name_not_modified(self):
		def unrelated_fn():
			return "unrelated"

		fake = types.ModuleType("erpnext.accounts.report._fake_unrelated_period_module")
		fake.get_period_list = unrelated_fn
		sys.modules[fake.__name__] = fake
		try:
			apply_calendar_patches()
			self.assertIs(fake.get_period_list, unrelated_fn)
		finally:
			sys.modules.pop(fake.__name__, None)

	def test_multiple_known_consumers_rebound(self):
		reset_calendar_patches_for_tests()
		import erpnext.accounts.report.financial_statements as fs_mod

		stock = fs_mod.get_period_list
		consumers = [
			"erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement",
			"erpnext.accounts.report.balance_sheet.balance_sheet",
			"erpnext.accounts.report.cash_flow.cash_flow",
			"erpnext.accounts.report.gross_and_net_profit_report.gross_and_net_profit_report",
		]
		mods = []
		for name in consumers:
			sys.modules.pop(name, None)
		import erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement as pl
		import erpnext.accounts.report.balance_sheet.balance_sheet as bs
		import erpnext.accounts.report.cash_flow.cash_flow as cf
		import erpnext.accounts.report.gross_and_net_profit_report.gross_and_net_profit_report as gn

		mods = [pl, bs, cf, gn]
		for mod in mods:
			self.assertIs(mod.get_period_list, stock)

		apply_calendar_patches()
		adapter = get_patch_state().adapter_get_period_list
		for mod in mods:
			self.assertIs(mod.get_period_list, adapter)

	def test_before_request_wrapper_invokes_applicator(self):
		with patch.object(patch_mod, "apply_calendar_patches", return_value=PatchStatus.APPLIED) as m:
			before_request_calendar_bootstrap()
			m.assert_called_once_with()

	def test_before_job_wrapper_invokes_applicator(self):
		with patch.object(patch_mod, "apply_calendar_patches", return_value=PatchStatus.APPLIED) as m:
			before_job_calendar_bootstrap(method="x", kwargs={}, transaction_type="job")
			m.assert_called_once_with()

	def test_before_tests_wrapper_invokes_applicator(self):
		with patch.object(patch_mod, "apply_calendar_patches", return_value=PatchStatus.APPLIED) as m:
			before_tests_calendar_bootstrap()
			m.assert_called_once_with()

	def test_early_import_failure_allows_retry(self):
		reset_calendar_patches_for_tests()
		saved = sys.modules.pop(FS_MODULE_PATH, None)
		real_import = __import__

		def boom(name, globals=None, locals=None, fromlist=(), level=0):
			if name == FS_MODULE_PATH or (
				fromlist and name == "erpnext.accounts.report" and "financial_statements" in fromlist
			):
				raise ImportError("simulated early boot")
			return real_import(name, globals, locals, fromlist, level)

		try:
			with patch("builtins.__import__", side_effect=boom):
				status = apply_calendar_patches()
			self.assertEqual(status, PatchStatus.SOURCE_UNAVAILABLE)
			self.assertEqual(get_patch_state().status, PatchStatus.SOURCE_UNAVAILABLE)
		finally:
			if saved is not None:
				sys.modules[FS_MODULE_PATH] = saved

		# Later retry with ERPNext available
		status2 = apply_calendar_patches()
		self.assertEqual(status2, PatchStatus.APPLIED)
		self.assertIsNotNone(get_patch_state().original_get_period_list)

	def test_no_recursion_on_repeated_bootstrap(self):
		apply_calendar_patches()
		original = get_patch_state().original_get_period_list
		adapter = get_patch_state().adapter_get_period_list
		self.assertIs(fs_adapter.get_original_get_period_list(), original)

		for _ in range(5):
			apply_calendar_patches()

		self.assertIs(get_patch_state().original_get_period_list, original)
		self.assertIs(get_patch_state().adapter_get_period_list, adapter)
		self.assertIs(fs_adapter.get_original_get_period_list(), original)
		# Original must never become the adapter
		self.assertIsNot(get_patch_state().original_get_period_list, adapter)

	def test_known_consumer_inventory_covers_direct_importers(self):
		"""Detect newly added direct importers of get_period_list from FS module."""
		import ast
		from pathlib import Path

		erpnext_root = Path(
			__import__("erpnext").__file__
		).resolve().parent
		found: set[str] = set()
		for path in erpnext_root.rglob("*.py"):
			try:
				tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
			except SyntaxError:
				continue
			for node in ast.walk(tree):
				if not isinstance(node, ast.ImportFrom):
					continue
				if node.module != "erpnext.accounts.report.financial_statements":
					continue
				names = {a.name for a in node.names}
				if "get_period_list" not in names:
					continue
				rel = path.relative_to(erpnext_root.parent)
				# erpnext/accounts/... → erpnext.accounts...
				mod = ".".join(rel.with_suffix("").parts)
				found.add(mod)

		missing = found - set(GET_PERIOD_LIST_CONSUMERS)
		extra_note = (
			f"New get_period_list importers not in GET_PERIOD_LIST_CONSUMERS: {sorted(missing)}"
		)
		self.assertFalse(missing, extra_note)


class TestGregorianDelegatesToOriginal(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_gregorian_calls_captured_original(self):
		original = get_patch_state().original_get_period_list
		self.assertIsNotNone(original)
		sentinel = object()

		def fake_original(*args, **kwargs):
			return sentinel

		# Temporarily point captured original to a sentinel
		fs_adapter.set_original_get_period_list  # ensure API exists
		# Replace via module global for this test
		prev = fs_adapter._original_get_period_list
		fs_adapter._original_get_period_list = fake_original
		try:
			with patch(
				"persian_calendar.calendar.integrations.financial_statements.get_business_calendar_for_company",
				return_value="Gregorian",
			):
				result = fs_adapter.get_period_list(
					"2024", "2024", None, None, "Fiscal Year", "Monthly", company="X"
				)
			self.assertIs(result, sentinel)
		finally:
			fs_adapter._original_get_period_list = prev

	def test_jalali_uses_business_period_engine(self):
		from datetime import date

		from persian_calendar.calendar.period_engine import BusinessPeriod

		fake_periods = [
			BusinessPeriod(
				from_date=date(2026, 3, 21),
				to_date=date(2026, 4, 20),
				key="j01_1405",
				label="",
				periodicity="Monthly",
				calendar_system="Jalali",
				year=1405,
				period_number=1,
			)
		]

		with (
			patch(
				"persian_calendar.calendar.integrations.financial_statements.get_business_calendar_for_company",
				return_value="Jalali",
			),
			patch(
				"persian_calendar.calendar.integrations.financial_statements.BusinessPeriodEngine.generate",
				return_value=fake_periods,
			) as gen,
			patch(
				"erpnext.accounts.report.financial_statements.validate_dates",
			),
		):
			# Date Range path avoids fiscal year DB
			result = fs_adapter.get_period_list(
				None,
				None,
				"2026-03-21",
				"2026-04-20",
				"Date Range",
				"Monthly",
				company="Jalali Co",
				ignore_fiscal_year=True,
			)
			gen.assert_called_once()
			self.assertEqual(len(result), 1)
			self.assertEqual(result[0]["key"], "j01_1405")


class TestHooksRegistration(unittest.TestCase):
	def test_hooks_reference_bootstrap_wrappers(self):
		from persian_calendar import hooks

		self.assertIn(
			"persian_calendar.calendar.patches.before_request_calendar_bootstrap",
			hooks.before_request,
		)
		self.assertNotIn("apply_period_list_patch", str(hooks.before_request))
		self.assertIn(
			"persian_calendar.calendar.patches.before_job_calendar_bootstrap",
			hooks.before_job,
		)
		self.assertEqual(
			hooks.before_tests,
			"persian_calendar.calendar.patches.before_tests_calendar_bootstrap",
		)


if __name__ == "__main__":
	unittest.main()
