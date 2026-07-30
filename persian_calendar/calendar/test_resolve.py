"""Tests for Company Business Calendar resolution.

Business Calendar must never follow User Display Calendar preference.
"""

from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	clear_business_calendar_cache,
	get_business_calendar_for_company,
	normalize_business_calendar,
)
from persian_calendar.jalali_support.doctype.custom_field.business_calendar import (
	create_business_calendar_field,
)
from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings


class TestNormalizeBusinessCalendar(unittest.TestCase):
	def test_defaults_and_valid(self):
		self.assertEqual(normalize_business_calendar(None), "Gregorian")
		self.assertEqual(normalize_business_calendar(""), "Gregorian")
		self.assertEqual(normalize_business_calendar("Jalali"), "Jalali")
		self.assertEqual(normalize_business_calendar("Gregorian"), "Gregorian")
		self.assertEqual(normalize_business_calendar("Hijri"), "Gregorian")


class TestBusinessCalendarResolver(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_business_calendar_field()

	def setUp(self):
		clear_business_calendar_cache()
		self.company = frappe.db.get_single_value("Global Defaults", "default_company")
		if not self.company:
			self.company = frappe.db.get_value("Company", {}, "name")
		self.assertTrue(self.company, "Need at least one Company for resolver tests")
		self._prev_bc = frappe.db.get_value("Company", self.company, "business_calendar")
		self._prev_user_pref = frappe.db.get_value("User", "Administrator", "calendar_preference")
		self._prev_jalali_enabled = frappe.db.get_single_value("Jalali Settings", "enable_jalali")
		self._prev_default_cal = frappe.db.get_single_value("Jalali Settings", "default_calendar")

	def tearDown(self):
		clear_business_calendar_cache()
		if self.company:
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
		frappe.db.set_single_value("Jalali Settings", "enable_jalali", self._prev_jalali_enabled)
		frappe.db.set_single_value("Jalali Settings", "default_calendar", self._prev_default_cal)

	def test_explicit_gregorian_company(self):
		frappe.db.set_value("Company", self.company, "business_calendar", "Gregorian", update_modified=False)
		clear_business_calendar_cache()
		self.assertEqual(get_business_calendar_for_company(self.company), BUSINESS_CALENDAR_GREGORIAN)
		self.assertEqual(CalendarEngine.for_company(self.company).name, "Gregorian")

	def test_explicit_jalali_company(self):
		frappe.db.set_value("Company", self.company, "business_calendar", "Jalali", update_modified=False)
		clear_business_calendar_cache()
		self.assertEqual(get_business_calendar_for_company(self.company), BUSINESS_CALENDAR_JALALI)
		self.assertEqual(CalendarEngine.for_company(self.company).name, "Jalali")

	def test_missing_company_falls_back_to_gregorian_or_default(self):
		# Empty company still returns a valid calendar (never raises)
		result = get_business_calendar_for_company(None)
		self.assertIn(result, (BUSINESS_CALENDAR_GREGORIAN, BUSINESS_CALENDAR_JALALI))

	def test_empty_field_treated_as_gregorian(self):
		frappe.db.set_value("Company", self.company, "business_calendar", "", update_modified=False)
		clear_business_calendar_cache()
		self.assertEqual(get_business_calendar_for_company(self.company), BUSINESS_CALENDAR_GREGORIAN)

	def test_display_preference_does_not_affect_business_provider(self):
		# Company stays Gregorian while user Display is Jalali and site default is Jalali
		frappe.db.set_value("Company", self.company, "business_calendar", "Gregorian", update_modified=False)
		frappe.db.set_value("User", "Administrator", "calendar_preference", "Jalali", update_modified=False)
		frappe.db.set_single_value("Jalali Settings", "enable_jalali", 1)
		frappe.db.set_single_value("Jalali Settings", "default_calendar", "Jalali")
		clear_business_calendar_cache()

		effective_display = JalaliSettings.get_effective_calendar(user="Administrator")
		self.assertEqual(effective_display["display_calendar"], "Jalali")

		self.assertEqual(get_business_calendar_for_company(self.company), BUSINESS_CALENDAR_GREGORIAN)
		self.assertEqual(CalendarEngine.for_company(self.company).name, "Gregorian")

		# Flip: Company Jalali, User Display Gregorian
		frappe.db.set_value("Company", self.company, "business_calendar", "Jalali", update_modified=False)
		frappe.db.set_value(
			"User", "Administrator", "calendar_preference", "Gregorian", update_modified=False
		)
		clear_business_calendar_cache()

		effective_display = JalaliSettings.get_effective_calendar(user="Administrator")
		self.assertEqual(effective_display["display_calendar"], "Gregorian")
		self.assertEqual(CalendarEngine.for_company(self.company).name, "Jalali")
