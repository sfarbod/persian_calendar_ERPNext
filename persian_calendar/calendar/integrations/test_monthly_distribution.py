"""Tests for Monthly Distribution calendar-neutral month-position mapping."""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import jdatetime
from frappe.utils import flt

from persian_calendar.calendar.integrations.monthly_distribution import (
	GREGORIAN_MONTH_LABELS,
	business_month_position,
	infer_calendar_system_from_period_list,
	month_label_for_position,
	resolve_distribution_percentage,
	validate_distribution_positions,
)
from persian_calendar.calendar.patches import (
	apply_calendar_patches,
	get_patch_state,
	reset_calendar_patches_for_tests,
)


def _j(y, m, d):
	return jdatetime.date(y, m, d).togregorian()


def _md_doc(percentages=None):
	"""Legacy January–December equal split (idx 1–12)."""
	if percentages is None:
		percentages = [
			SimpleNamespace(month=name, percentage_allocation=100.0 / 12, idx=i + 1)
			for i, name in enumerate(GREGORIAN_MONTH_LABELS)
		]
	return SimpleNamespace(name="TEST-MD", percentages=percentages, get=lambda k: percentages)


class TestMonthPositionMapping(unittest.TestCase):
	def test_gregorian_positions(self):
		self.assertEqual(business_month_position(date(2026, 1, 15), "Gregorian"), 1)
		self.assertEqual(business_month_position(date(2026, 12, 1), "Gregorian"), 12)

	def test_jalali_positions(self):
		self.assertEqual(business_month_position(_j(1405, 1, 1), "Jalali"), 1)
		self.assertEqual(business_month_position(_j(1405, 12, 29), "Jalali"), 12)
		self.assertEqual(business_month_position(_j(1405, 7, 1), "Jalali"), 7)

	def test_labels_are_presentation_only(self):
		self.assertEqual(month_label_for_position(1, "Jalali", "en"), "Farvardin")
		self.assertEqual(month_label_for_position(12, "Jalali", "en"), "Esfand")
		self.assertEqual(month_label_for_position(1, "Gregorian", "en"), "January")


class TestResolveDistributionPercentage(unittest.TestCase):
	def test_gregorian_january_uses_stock_name_matching(self):
		doc = _md_doc()
		# Capture originals via patch applicator so Gregorian path uses stock
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		pct = resolve_distribution_percentage(
			doc, date(2026, 1, 1), 1, calendar_system="Gregorian"
		)
		self.assertAlmostEqual(pct, 100.0 / 12, places=5)

	def test_jalali_farvardin_uses_idx_not_march_label(self):
		"""Farvardin starts in Gregorian March — must NOT pick March's English row by name alone.

		Position 1 (idx=1, labeled January in legacy docs) is Farvardin for Jalali.
		"""
		doc = _md_doc()
		# Put a distinctive percentage on position 1 vs March (idx 3)
		doc.percentages[0].percentage_allocation = 50.0  # idx 1
		doc.percentages[2].percentage_allocation = 5.0  # idx 3 = March / Khordad
		# renormalize not required for this unit check
		pct = resolve_distribution_percentage(
			doc, _j(1405, 1, 1), 1, calendar_system="Jalali"
		)
		self.assertAlmostEqual(pct, 50.0, places=5)

	def test_jalali_quarterly_sums_three_positions(self):
		doc = _md_doc()
		for i, row in enumerate(doc.percentages):
			row.percentage_allocation = float(i + 1)  # 1..12
		# Renormalize not needed — we check sum of positions 1+2+3 = 6
		pct = resolve_distribution_percentage(
			doc, _j(1405, 1, 1), 3, calendar_system="Jalali"
		)
		self.assertAlmostEqual(pct, 1 + 2 + 3, places=5)

	def test_same_neutral_doc_works_for_both_calendars(self):
		doc = _md_doc()
		reset_calendar_patches_for_tests()
		apply_calendar_patches()
		g = resolve_distribution_percentage(
			doc, date(2026, 4, 1), 1, calendar_system="Gregorian"
		)
		j = resolve_distribution_percentage(
			doc, _j(1405, 1, 1), 1, calendar_system="Jalali"
		)
		# Both position-1 / April vs Farvardin — equal split → same percentage
		self.assertAlmostEqual(g, 100.0 / 12, places=5)
		self.assertAlmostEqual(j, 100.0 / 12, places=5)

	def test_decimal_percentages(self):
		doc = _md_doc(
			[
				SimpleNamespace(month="January", percentage_allocation=8.333, idx=1),
				*[
					SimpleNamespace(
						month=GREGORIAN_MONTH_LABELS[i],
						percentage_allocation=8.333 if i < 11 else 8.337,
						idx=i + 1,
					)
					for i in range(1, 12)
				],
			]
		)
		pct = resolve_distribution_percentage(
			doc, _j(1405, 1, 1), 1, calendar_system="Jalali"
		)
		self.assertEqual(flt(pct, 3), flt(8.333, 3))


class TestDistributionValidation(unittest.TestCase):
	def test_duplicate_positions_rejected(self):
		import frappe

		doc = _md_doc(
			[
				SimpleNamespace(month="January", percentage_allocation=50, idx=1),
				SimpleNamespace(month="February", percentage_allocation=50, idx=1),
			]
		)
		with self.assertRaises((ValueError, frappe.ValidationError)):
			validate_distribution_positions(doc)

	def test_total_not_100_rejected(self):
		import frappe

		doc = _md_doc(
			[
				SimpleNamespace(month="January", percentage_allocation=40, idx=1),
				SimpleNamespace(month="February", percentage_allocation=40, idx=2),
			]
		)
		with self.assertRaises((ValueError, frappe.ValidationError)):
			validate_distribution_positions(doc)


class TestCalendarInference(unittest.TestCase):
	def test_infer_from_jalali_keys(self):
		period_list = [SimpleNamespace(key="j01_1405", get=lambda k, d=None: "j01_1405")]
		# frappe._dict style
		period_list = [{"key": "j01_1405"}]
		self.assertEqual(infer_calendar_system_from_period_list(period_list), "Jalali")

	def test_infer_gregorian_default(self):
		period_list = [{"key": "jan_2026"}]
		self.assertEqual(infer_calendar_system_from_period_list(period_list), "Gregorian")

	def test_company_overrides_key(self):
		period_list = [{"key": "j01_1405"}]
		with patch(
			"persian_calendar.calendar.integrations.monthly_distribution.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			self.assertEqual(
				infer_calendar_system_from_period_list(period_list, company="G"),
				"Gregorian",
			)


class TestMDPatchLifecycle(unittest.TestCase):
	def setUp(self):
		reset_calendar_patches_for_tests()

	def tearDown(self):
		reset_calendar_patches_for_tests()

	def test_md_functions_patched(self):
		status = apply_calendar_patches()
		from persian_calendar.calendar.patches import PatchStatus

		self.assertEqual(status, PatchStatus.APPLIED)
		state = get_patch_state()
		self.assertIsNotNone(state.original_get_periodwise_distribution_data)
		self.assertIsNotNone(state.adapter_get_periodwise_distribution_data)
		self.assertIsNot(
			state.original_get_periodwise_distribution_data,
			state.adapter_get_periodwise_distribution_data,
		)

		import erpnext.accounts.doctype.monthly_distribution.monthly_distribution as md_mod

		self.assertIs(
			md_mod.get_periodwise_distribution_data,
			state.adapter_get_periodwise_distribution_data,
		)


if __name__ == "__main__":
	unittest.main()
