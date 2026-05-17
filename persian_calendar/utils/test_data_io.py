import unittest
from datetime import date, datetime

from persian_calendar.utils.data_io import convert_export_value, convert_import_value
from persian_calendar.utils.jalali import (
	gregorian_to_jalali_for_export,
	is_likely_gregorian_date,
	is_likely_jalali_date,
	jalali_to_gregorian_datetime,
	strip_microseconds,
	toshamshi,
)


class TestDataExportConversion(unittest.TestCase):
	def test_date_gregorian_to_jalali(self):
		self.assertEqual(
			convert_export_value("2026-05-13", "Date", True),
			"1405-02-23",
		)

	def test_posting_date_iso(self):
		self.assertEqual(
			convert_export_value("2026-04-10", "Date", True),
			"1405-01-21",
		)

	def test_date_object(self):
		self.assertEqual(
			convert_export_value(date(2026, 4, 10), "Date", True),
			"1405-01-21",
		)

	def test_excel_user_formatted_date_string(self):
		"""Values like 10-04-2026 from formatdate must still convert."""
		from frappe.utils import formatdate

		formatted = formatdate("2026-04-10")
		self.assertEqual(
			convert_export_value(formatted, "Date", True),
			"1405-01-21",
		)
		self.assertNotEqual(formatted, "1405-01-21")

	def test_datetime_gregorian_to_jalali(self):
		out = convert_export_value("2026-03-18 13:36:04.446274", "Datetime", True)
		self.assertEqual(out, "1404-12-27 13:36:04")

	def test_unchecked_unchanged(self):
		self.assertEqual(convert_export_value("2026-05-13", "Date", False), "2026-05-13")

	def test_child_table_style_value(self):
		self.assertEqual(
			gregorian_to_jalali_for_export(date(1990, 1, 2), "Date"),
			"1368-10-12",
		)


class TestDataImportConversion(unittest.TestCase):
	def test_date_jalali_to_gregorian(self):
		result = convert_import_value("1405-02-23", "Date", True)
		self.assertEqual(result, date(2026, 5, 13))

	def test_datetime_jalali_to_gregorian(self):
		result = convert_import_value("1404-12-27 13:36:04", "Datetime", True)
		self.assertEqual(result, datetime(2026, 3, 18, 13, 36, 4))

	def test_unchecked_string_unchanged(self):
		self.assertEqual(convert_import_value("1405-02-23", "Date", False), "1405-02-23")

	def test_strip_microseconds_import_path(self):
		g = jalali_to_gregorian_datetime("1404-12-27 13:36:04.99")
		self.assertEqual(g, "2026-03-18 13:36:04")

	def test_detection_helpers(self):
		self.assertTrue(is_likely_jalali_date("1405-02-23"))
		self.assertTrue(is_likely_gregorian_date("2026-05-13"))
		self.assertEqual(strip_microseconds("2026-03-18 13:36:04.446274"), "2026-03-18 13:36:04")


if __name__ == "__main__":
	unittest.main()
