"""Asset Depreciation Schedule — Business Calendar integration tests."""

from __future__ import annotations

import jdatetime

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, get_last_day, getdate, is_last_day_of_the_month

from persian_calendar.calendar.integrations.assets import (
	PersianCalendarAssetDepreciationSchedule,
	disposal_was_made_on_original_schedule_date,
)
from persian_calendar.calendar.resolve import clear_business_calendar_cache
from persian_calendar.jalali_support.doctype.custom_field.business_calendar import (
	create_business_calendar_field,
)


def _j_to_g(jy: int, jm: int, jd: int):
	return jdatetime.date(jy, jm, jd).togregorian()


class TestAssetBusinessCalendar(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_business_calendar_field()
		cls.company = "_Test Company"
		if not frappe.db.exists("Company", cls.company):
			cls.company = frappe.db.get_single_value("Global Defaults", "default_company")

	def setUp(self):
		clear_business_calendar_cache()
		self._prev_bc = frappe.db.get_value("Company", self.company, "business_calendar")
		self._prev_user_pref = frappe.db.get_value("User", "Administrator", "calendar_preference")
		self._prev_default_company = frappe.db.get_single_value("Global Defaults", "default_company")

	def tearDown(self):
		clear_business_calendar_cache()
		frappe.db.set_value(
			"Company",
			self.company,
			"business_calendar",
			self._prev_bc or "Gregorian",
			update_modified=False,
		)
		if self._prev_user_pref is not None:
			frappe.db.set_value(
				"User",
				"Administrator",
				"calendar_preference",
				self._prev_user_pref,
				update_modified=False,
			)
		if self._prev_default_company:
			frappe.db.set_single_value("Global Defaults", "default_company", self._prev_default_company)

	def _set_bc(self, value: str):
		frappe.db.set_value("Company", self.company, "business_calendar", value, update_modified=False)
		clear_business_calendar_cache()

	def _schedule_stub(self, start, frequency=1, should_get_last_day=False):
		doc = frappe.new_doc("Asset Depreciation Schedule")
		doc.company = self.company
		doc.fb_row = frappe._dict(
			depreciation_start_date=getdate(start),
			frequency_of_depreciation=frequency,
		)
		doc.should_get_last_day = should_get_last_day
		return doc

	def test_controller_is_overridden(self):
		from frappe.model.base_document import get_controller

		cls = get_controller("Asset Depreciation Schedule")
		self.assertTrue(issubclass(cls, PersianCalendarAssetDepreciationSchedule))

	def test_gregorian_same_day_matches_stock(self):
		self._set_bc("Gregorian")
		start = getdate("2026-01-15")
		doc = self._schedule_stub(start, frequency=1, should_get_last_day=False)
		for i in range(0, 6):
			got = getdate(doc.get_next_schedule_date(i))
			expected = getdate(add_months(start, i))
			self.assertEqual(got, expected, f"row {i}")

	def test_gregorian_preserve_month_end_matches_stock(self):
		self._set_bc("Gregorian")
		start = getdate("2026-01-31")
		self.assertTrue(is_last_day_of_the_month(start))
		doc = self._schedule_stub(start, frequency=1, should_get_last_day=True)
		for i in range(0, 6):
			got = getdate(doc.get_next_schedule_date(i))
			expected = get_last_day(add_months(start, i))
			self.assertEqual(got, expected, f"row {i}")

	def test_jalali_same_day_monthly(self):
		self._set_bc("Jalali")
		start = _j_to_g(1405, 1, 1)
		doc = self._schedule_stub(start, frequency=1, should_get_last_day=False)
		expected = [_j_to_g(1405, m, 1) for m in (1, 2, 3, 4)]
		got = [getdate(doc.get_next_schedule_date(i)) for i in range(4)]
		self.assertEqual(got, expected)

	def test_jalali_preserve_month_end_monthly(self):
		self._set_bc("Jalali")
		start = _j_to_g(1404, 12, 29)
		doc = self._schedule_stub(start, frequency=1, should_get_last_day=True)
		expected_j = [
			(1404, 12, 29),
			(1405, 1, 31),
			(1405, 2, 31),
			(1405, 3, 31),
			(1405, 4, 31),
			(1405, 5, 31),
			(1405, 6, 31),
			(1405, 7, 30),
		]
		got = [getdate(doc.get_next_schedule_date(i)) for i in range(8)]
		expected = [_j_to_g(*t) for t in expected_j]
		self.assertEqual(got, expected)

	def test_jalali_annual_recurrence(self):
		self._set_bc("Jalali")
		start = _j_to_g(1405, 1, 1)
		doc = self._schedule_stub(start, frequency=12, should_get_last_day=False)
		self.assertEqual(getdate(doc.get_next_schedule_date(0)), _j_to_g(1405, 1, 1))
		self.assertEqual(getdate(doc.get_next_schedule_date(1)), _j_to_g(1406, 1, 1))

	def test_disposal_helper_jalali_same_day(self):
		self._set_bc("Jalali")
		row = frappe._dict(
			depreciation_start_date=_j_to_g(1405, 1, 1),
			frequency_of_depreciation=1,
			parent=None,
			company=self.company,
		)
		target = _j_to_g(1405, 3, 1)
		self.assertTrue(disposal_was_made_on_original_schedule_date(2, row, target))
		self.assertFalse(disposal_was_made_on_original_schedule_date(2, row, _j_to_g(1405, 4, 1)))

	def test_booked_rows_not_mutated_on_regenerate(self):
		"""clear() must keep rows that already have a journal_entry."""
		self._set_bc("Jalali")
		doc = frappe.new_doc("Asset Depreciation Schedule")
		doc.company = self.company
		doc.append(
			"depreciation_schedule",
			{
				"schedule_date": _j_to_g(1405, 1, 1),
				"depreciation_amount": 1000,
				"journal_entry": "JE-FAKE-KEEP",
			},
		)
		doc.append(
			"depreciation_schedule",
			{
				"schedule_date": _j_to_g(1405, 2, 1),
				"depreciation_amount": 1000,
				"journal_entry": None,
			},
		)
		doc.clear()
		self.assertEqual(len(doc.depreciation_schedule), 1)
		self.assertEqual(doc.depreciation_schedule[0].journal_entry, "JE-FAKE-KEEP")
		self.assertEqual(doc.first_non_depreciated_row_idx, 1)

	def test_display_preference_does_not_change_schedule_math(self):
		self._set_bc("Jalali")
		frappe.db.set_value(
			"User", "Administrator", "calendar_preference", "Gregorian", update_modified=False
		)
		start = _j_to_g(1405, 1, 1)
		doc = self._schedule_stub(start, frequency=1, should_get_last_day=False)
		self.assertEqual(getdate(doc.get_next_schedule_date(1)), _j_to_g(1405, 2, 1))

	def test_initialize_variables_uses_business_month_end(self):
		"""should_get_last_day must follow Company BC, not Gregorian-only."""
		self._set_bc("Jalali")
		# 1404-12-29 is Jalali month-end but NOT Gregorian month-end (2026-03-20)
		start = _j_to_g(1404, 12, 29)
		self.assertFalse(is_last_day_of_the_month(start))

		doc = frappe.new_doc("Asset Depreciation Schedule")
		doc.company = self.company
		doc.asset = None
		doc.asset_doc = frappe._dict(
			company=self.company,
			available_for_use_date=start,
			opening_number_of_booked_depreciations=0,
			opening_accumulated_depreciation=0,
			precision=lambda *_: 2,
			net_purchase_amount=100000,
		)
		doc.fb_row = frappe._dict(
			depreciation_start_date=start,
			frequency_of_depreciation=1,
			total_number_of_depreciations=4,
			increase_in_asset_life=0,
			value_after_depreciation=100000,
			depreciation_method="Straight Line",
			expected_value_after_useful_life=0,
		)
		doc.depreciation_schedule = []
		doc.first_non_depreciated_row_idx = 0
		doc.opening_number_of_booked_depreciations = 0
		doc.opening_accumulated_depreciation = 0
		doc.shift_based = 0
		doc.disposal_date = None
		doc.initialize_variables()
		self.assertTrue(doc.should_get_last_day)
