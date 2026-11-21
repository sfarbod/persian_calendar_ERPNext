# Copyright (c) 2026, Persian Calendar contributors
# License: MIT

"""v2.1.4 — List View date filter compatibility (Frappe ≥16.60 filter panel)."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from persian_calendar.utils.jalali import toshamshi


APP_ROOT = Path(__file__).resolve().parents[1]
PC_JS = APP_ROOT / "public" / "js" / "jalali_support" / "persian_calendar.js"
JALAALI_JS = APP_ROOT / "public" / "js" / "jalali_support" / "jalaali.js"


class TestListFilterJalaliSourceContracts(FrappeTestCase):
	"""Guard Frappe filter-panel compatibility shims in persian_calendar.js."""

	def test_datepicker_shim_defines_destroy_and_select_date(self):
		src = PC_JS.read_text(encoding="utf-8")
		self.assertIn("function installJalaliDatepickerShim", src)
		self.assertIn("destroy()", src)
		self.assertIn("selectDate(dates)", src)
		self.assertIn("destroy_calendar", src)
		# Must not leave selectDate as an empty no-op body without set_value.
		self.assertIn("control.set_value(dateLikeToGregorianModel", src)

	def test_air_datepicker_cleanup_preserves_daterange_and_filters(self):
		src = PC_JS.read_text(encoding="utf-8")
		self.assertIn("shouldPreserveAirDatepickerInput", src)
		self.assertIn('ft === "DateRange"', src)
		self.assertIn(".filter-field", src)
		self.assertIn("if (!shouldUseJalaliCalendar())", src)

	def test_control_daterange_jalali_normalize_override_present(self):
		src = PC_JS.read_text(encoding="utf-8")
		self.assertIn("JalaliControlDateRange", src)
		self.assertIn("ControlDateRange", src)

	def test_jalaali_normalize_model_date_helpers_present(self):
		src = JALAALI_JS.read_text(encoding="utf-8")
		self.assertIn("normalizeModelDate", src)
		self.assertIn("jalaliToGregorianISO", src)


class TestListFilterJalaliServerEquivalence(FrappeTestCase):
	"""Server-side: Jalali-equivalent Gregorian filters must match for Stock Entry."""

	SAMPLE = "MAT-STE-2026-37328"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("DocType", "Stock Entry"):
			raise unittest.SkipTest("Stock Entry not installed")
		if not frappe.db.exists("Stock Entry", cls.SAMPLE):
			raise unittest.SkipTest(f"{cls.SAMPLE} not on site")

	def test_sample_doc_posting_date_and_items(self):
		posting_date = frappe.db.get_value("Stock Entry", self.SAMPLE, "posting_date")
		self.assertTrue(posting_date)
		item_count = frappe.db.count("Stock Entry Detail", {"parent": self.SAMPLE})
		self.assertGreaterEqual(item_count, 1)

	def test_equals_filter_matches_jalali_converted_date(self):
		posting_date = frappe.db.get_value("Stock Entry", self.SAMPLE, "posting_date")
		if isinstance(posting_date, date):
			g_iso = posting_date.isoformat()
		else:
			g_iso = str(posting_date)[:10]

		jalali = toshamshi(g_iso, include_time=False)
		self.assertTrue(jalali)
		# Round-trip via jdatetime to ensure the displayed Jalali day maps back.
		import jdatetime

		parts = [int(x) for x in str(jalali).split("-")[:3]]
		back = jdatetime.date(parts[0], parts[1], parts[2]).togregorian().isoformat()
		self.assertEqual(back, g_iso)

		by_gregorian = set(
			frappe.get_all(
				"Stock Entry",
				filters={"posting_date": g_iso},
				pluck="name",
			)
		)
		by_roundtrip = set(
			frappe.get_all(
				"Stock Entry",
				filters={"posting_date": back},
				pluck="name",
			)
		)
		self.assertEqual(by_gregorian, by_roundtrip)
		self.assertIn(self.SAMPLE, by_gregorian)

		# Unconverted Jalali year must not match stored Gregorian rows.
		wrong = set(
			frappe.get_all(
				"Stock Entry",
				filters={"posting_date": str(jalali)},
				pluck="name",
			)
		)
		self.assertNotIn(self.SAMPLE, wrong)

	def test_between_and_comparison_operators(self):
		posting_date = frappe.db.get_value("Stock Entry", self.SAMPLE, "posting_date")
		g_iso = posting_date.isoformat() if isinstance(posting_date, date) else str(posting_date)[:10]

		eq = frappe.db.count("Stock Entry", {"posting_date": g_iso})
		between = frappe.db.count(
			"Stock Entry", {"posting_date": ["between", [g_iso, g_iso]]}
		)
		gte = frappe.db.count("Stock Entry", {"posting_date": [">=", g_iso]})
		lte = frappe.db.count("Stock Entry", {"posting_date": ["<=", g_iso]})

		self.assertEqual(eq, between)
		self.assertGreaterEqual(gte, eq)
		self.assertGreaterEqual(lte, eq)
		self.assertGreater(eq, 0)

	def test_reportview_get_with_posting_date_filter(self):
		"""Exercise Frappe list get path with Gregorian posting_date (= / Between)."""
		from frappe.desk.reportview import get as reportview_get

		posting_date = frappe.db.get_value("Stock Entry", self.SAMPLE, "posting_date")
		g_iso = posting_date.isoformat() if isinstance(posting_date, date) else str(posting_date)[:10]

		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Stock Entry",
				"fields": '["`tabStock Entry`.`name`","`tabStock Entry`.`posting_date`"]',
				"filters": f'[["Stock Entry","posting_date","=","{g_iso}"]]',
				"order_by": "`tabStock Entry`.`modified` desc",
				"start": 0,
				"page_length": 50,
				"view": "List",
			}
		)
		data = reportview_get()
		# compress() returns keys/values; ensure our sample appears when within page
		self.assertTrue(data)
		frappe.local.form_dict = frappe._dict(
			{
				"doctype": "Stock Entry",
				"fields": '["`tabStock Entry`.`name`","`tabStock Entry`.`posting_date`"]',
				"filters": f'[["Stock Entry","posting_date","Between",["{g_iso}","{g_iso}"]]]',
				"order_by": "`tabStock Entry`.`modified` desc",
				"start": 0,
				"page_length": 50,
				"view": "List",
			}
		)
		data2 = reportview_get()
		self.assertTrue(data2)
