"""Phase 4a — ERPNext contract / upgrade-safety tests."""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from persian_calendar.calendar.compatibility import (
	VALIDATED_ERPNEXT,
	VALIDATED_FRAPPE,
	CompatibilityStatus,
	detect_compatibility,
)
from persian_calendar.calendar.contracts import (
	CONTRACTS,
	check_callable_contract,
	resolve_callable,
	validate_all_contracts,
)
from persian_calendar.calendar.diagnostics import (
	ReleaseLevel,
	build_report,
	release_check,
	report_as_dict,
	run,
	validate_import_graph,
	validate_patch_registry,
)
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	reset_calendar_patches_for_tests,
)


class TestErpnextContracts(unittest.TestCase):
	"""Fail fast with a clear message if upstream signatures change."""

	@classmethod
	def setUpClass(cls):
		reset_calendar_patches_for_tests()
		apply_calendar_patches()

	@classmethod
	def tearDownClass(cls):
		reset_calendar_patches_for_tests()

	def test_catalog_covers_required_targets(self):
		ids = {c.id for c in CONTRACTS}
		required = {
			"fs.get_period_list",
			"trends.get_period_date_ranges",
			"md.get_periodwise_distribution_data",
			"md.get_percentage",
			"bvr.execute",
			"sa.Analytics.get_period_date_ranges",
			"sa.Analytics.get_period",
			"sa.Analytics.get_columns",
			"sa.Analytics.get_chart_data",
			"stk.get_period_date_ranges",
			"stk.get_period",
			"stk.get_period_columns",
			"stk.round_down_to_nearest_frequency",
			"budget.Budget.get_budget_periods",
			"api.toshamshi",
			"api.toshamsi",
			"utils.jalali.toshamshi",
			"spa.execute",
			"hrms.vehicle_expenses.get_chart_data",
		}
		missing = required - ids
		self.assertFalse(
			missing,
			f"Contract catalog missing required targets: {sorted(missing)}",
		)

	def test_all_contracts_pass_on_validated_erpnext(self):
		result = validate_all_contracts()
		self.assertTrue(
			result.ok,
			"ERPNext API contract drift detected:\n" + "\n".join(f.message for f in result.failures),
		)

	def test_each_contract_resolves_callable(self):
		for contract in CONTRACTS:
			with self.subTest(contract=contract.id):
				fn = resolve_callable(contract)
				self.assertTrue(callable(fn), contract.id)
				errors = check_callable_contract(contract, fn)
				self.assertEqual(errors, [], msg="\n".join(errors))

	def test_signature_mismatch_message_is_human_readable(self):
		"""Guardrail: failure text must mention contract id and guidance."""
		contract = CONTRACTS[0]

		def fake(*args, **kwargs):
			pass

		errors = check_callable_contract(contract, fake)
		self.assertTrue(errors)
		self.assertIn(contract.id, errors[0])
		self.assertIn("parameter", errors[0].lower())


class TestPatchRegistryValidation(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_registry_healthy_after_apply(self):
		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		issues = validate_patch_registry()
		self.assertEqual(issues, [], msg="\n".join(issues))

	def test_import_graph_healthy_after_apply(self):
		# Import consumers before apply (import-before-patch)
		for mod in (
			"erpnext.buying.report.purchase_analytics.purchase_analytics",
			"erpnext.manufacturing.report.job_card_summary.job_card_summary",
			"erpnext.manufacturing.report.production_analytics.production_analytics",
			"erpnext.manufacturing.report.work_order_summary.work_order_summary",
		):
			importlib.import_module(mod)

		self.assertEqual(apply_calendar_patches(), PatchStatus.APPLIED)
		issues = validate_import_graph()
		self.assertEqual(issues, [], msg="\n".join(issues))


class TestCompatibilityDetector(unittest.TestCase):
	def test_exact_validated_versions_are_supported(self):
		with (
			patch("persian_calendar.calendar.compatibility._pkg_version") as ver,
		):

			def side(name):
				return {"frappe": VALIDATED_FRAPPE, "erpnext": VALIDATED_ERPNEXT}[name]

			ver.side_effect = side
			report = detect_compatibility()
		self.assertEqual(report.status, CompatibilityStatus.SUPPORTED)

	def test_same_major_is_partially_verified(self):
		with patch("persian_calendar.calendar.compatibility._pkg_version") as ver:

			def side(name):
				return {"frappe": "16.99.0", "erpnext": "16.99.0"}[name]

			ver.side_effect = side
			report = detect_compatibility()
		self.assertEqual(report.status, CompatibilityStatus.PARTIALLY_VERIFIED)
		self.assertTrue(report.messages)

	def test_unknown_major_emits_unknown(self):
		with patch("persian_calendar.calendar.compatibility._pkg_version") as ver:

			def side(name):
				return {"frappe": "15.0.0", "erpnext": "15.0.0"}[name]

			ver.side_effect = side
			report = detect_compatibility()
		self.assertEqual(report.status, CompatibilityStatus.UNKNOWN_VERSION)

	def test_live_install_is_not_unavailable(self):
		report = detect_compatibility()
		self.assertNotEqual(report.status, CompatibilityStatus.UNAVAILABLE)
		self.assertIsNotNone(report.frappe_version)
		self.assertIsNotNone(report.erpnext_version)


class TestDiagnosticsCommands(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_build_report_pass_or_warning_on_validated_bench(self):
		report = build_report()
		self.assertIn(report.level, (ReleaseLevel.PASS, ReleaseLevel.WARNING))
		self.assertFalse(report.contract_failures)
		self.assertFalse(report.registry_issues)
		self.assertFalse(report.import_issues)

	def test_run_returns_level_string(self):
		level = run()
		self.assertIn(level, ("PASS", "WARNING", "FAIL"))

	def test_release_check_returns_level_string(self):
		level = release_check()
		self.assertIn(level, ("PASS", "WARNING", "FAIL"))

	def test_report_as_dict_shape(self):
		payload = report_as_dict()
		for key in (
			"level",
			"compatibility",
			"patch_status",
			"contract_failures",
			"registry_issues",
			"import_issues",
			"deferred_modules",
			"technical_debt",
			"upgrade_risks",
			"conversion_issues",
		):
			self.assertIn(key, payload)

	def test_conversion_api_check_present(self):
		report = build_report()
		names = {c.name for c in report.checks}
		self.assertIn("conversion_api", names)
		self.assertFalse(report.conversion_issues)


if __name__ == "__main__":
	unittest.main()
