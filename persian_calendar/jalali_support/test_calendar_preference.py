# Copyright (c) 2025, Persian Calendar Contributors
import frappe
from frappe.tests.utils import FrappeTestCase

from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
	JalaliSettings,
)


class TestCalendarPreference(FrappeTestCase):
	def tearDown(self):
		user = frappe.session.user
		if user and user != "Guest":
			frappe.db.set_value(
				"User",
				user,
				"calendar_preference",
				"System Default",
				update_modified=False,
			)

	def test_user_gregorian_preference_effective_calendar(self):
		user = frappe.session.user
		if user == "Guest":
			self.skipTest("No logged-in user")
		frappe.db.set_value("User", user, "calendar_preference", "Gregorian", update_modified=False)
		effective = JalaliSettings.get_effective_calendar(user)
		self.assertEqual(effective["display_calendar"], "Gregorian")

	def test_user_jalali_preference_effective_calendar(self):
		user = frappe.session.user
		if user == "Guest":
			self.skipTest("No logged-in user")
		settings = JalaliSettings.get_settings()
		if not settings.enabled:
			self.skipTest("Jalali not enabled in Jalali Settings")
		frappe.db.set_value("User", user, "calendar_preference", "Jalali", update_modified=False)
		effective = JalaliSettings.get_effective_calendar(user)
		self.assertEqual(effective["display_calendar"], "Jalali")

	def test_system_default_follows_site_default(self):
		user = frappe.session.user
		if user == "Guest":
			self.skipTest("No logged-in user")
		settings = JalaliSettings.get_settings()
		frappe.db.set_value(
			"User", user, "calendar_preference", "System Default", update_modified=False
		)
		effective = JalaliSettings.get_effective_calendar(user)
		self.assertEqual(effective["display_calendar"], settings.default_calendar)

	def test_user_jalali_when_global_disabled(self):
		user = frappe.session.user
		if user == "Guest":
			self.skipTest("No logged-in user")
		frappe.db.set_value("Jalali Settings", "Jalali Settings", "enabled", 0, update_modified=False)
		frappe.db.set_value("User", user, "calendar_preference", "Jalali", update_modified=False)
		effective = JalaliSettings.get_effective_calendar(user)
		self.assertEqual(effective["display_calendar"], "Jalali")

	def test_boot_extend_bootinfo_shape(self):
		from persian_calendar.jalali_support.boot import extend_bootinfo

		bootinfo = frappe._dict()
		extend_bootinfo(bootinfo)
		self.assertIn("persian_calendar", bootinfo)
		pc = bootinfo["persian_calendar"]
		self.assertIn("display_calendar", pc)
		self.assertIn("calendar_preference", pc)
		self.assertIn("enabled", pc)
