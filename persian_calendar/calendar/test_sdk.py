"""Phase 4b — SDK / public API self-validation (no business behaviour asserts)."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from persian_calendar import api
from persian_calendar.calendar.adapter_template import ADAPTER_REQUIRED_PIECES, TEMPLATE_STEPS
from persian_calendar.calendar.registry import INTEGRATED_MODULES, implemented_modules


class TestPublicApiExports(unittest.TestCase):
	def test_required_exports_present(self):
		for name in (
			"CalendarEngine",
			"BusinessPeriod",
			"BusinessPeriodEngine",
			"get_business_calendar_for_company",
			"apply_calendar_patches",
			"PatchStatus",
			"detect_compatibility",
			"release_check",
			"run_diagnostics",
			"INTEGRATED_MODULES",
			"build_jalali_periods",
			"should_use_jalali_engine",
			"capture_original",
			"rebind_consumers",
			"toshamshi",
			"toshamsi",
		):
			self.assertTrue(hasattr(api, name), f"missing public export: {name}")
			self.assertIn(name, api.__all__)

	def test_toshamshi_alias_identity(self):
		from persian_calendar.utils.jalali import toshamshi as legacy

		self.assertIs(api.toshamshi, legacy)
		self.assertIs(api.toshamsi, api.toshamshi)

	def test_api_imports_cleanly(self):
		mod = importlib.import_module("persian_calendar.api")
		self.assertIs(mod.BusinessPeriodEngine, api.BusinessPeriodEngine)


class TestRegistry(unittest.TestCase):
	def test_registry_non_empty(self):
		self.assertGreater(len(INTEGRATED_MODULES), 5)

	def test_implemented_includes_stock_and_sales(self):
		names = {m.name for m in implemented_modules()}
		self.assertIn("Stock Analytics", names)
		self.assertIn("Sales Analytics", names)
		self.assertIn("Financial Statements", names)

	def test_deferred_marked(self):
		deferred = {m.name for m in INTEGRATED_MODULES if m.status == "deferred"}
		self.assertIn("CRM Pipeline Analytics", deferred)
		self.assertIn("MRP / MPS", deferred)

	def test_conversion_utility_registered(self):
		util = [m for m in INTEGRATED_MODULES if m.status == "public_utility"]
		self.assertTrue(util)
		names = {m.name for m in util}
		self.assertTrue(any("toshamshi" in n for n in names))
		# Not treated as a patched ERPNext module
		for m in util:
			self.assertEqual(m.patch_targets, ())
			self.assertNotIn(m, implemented_modules())


class TestAdaptersUseSharedHelpers(unittest.TestCase):
	"""Sales and Stock must import adapter_helpers (Phase 4b consolidation)."""

	def test_sales_source_uses_helpers(self):
		path = Path(
			importlib.import_module("persian_calendar.calendar.integrations.sales_analytics").__file__
		)
		text = path.read_text(encoding="utf-8")
		self.assertIn("persian_calendar.calendar.adapter_helpers", text)
		self.assertIn("build_jalali_periods", text)
		self.assertIn("should_use_jalali_engine", text)

	def test_stock_source_uses_helpers(self):
		path = Path(
			importlib.import_module("persian_calendar.calendar.integrations.stock_analytics").__file__
		)
		text = path.read_text(encoding="utf-8")
		self.assertIn("persian_calendar.calendar.adapter_helpers", text)
		self.assertIn("lookup_period_key", text)
		self.assertIn("build_jalali_periods", text)


class TestAdapterTemplate(unittest.TestCase):
	def test_template_documents_required_pieces(self):
		self.assertIn("Gregorian delegate (captured original)", ADAPTER_REQUIRED_PIECES)
		self.assertIn("BusinessPeriodEngine call for Jalali supported periods", ADAPTER_REQUIRED_PIECES)
		self.assertGreaterEqual(len(TEMPLATE_STEPS), 6)


if __name__ == "__main__":
	unittest.main()
