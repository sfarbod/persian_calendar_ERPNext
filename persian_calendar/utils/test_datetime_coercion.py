import unittest
from datetime import datetime

from persian_calendar.utils.jalali import (
	coerce_gregorian_datetime,
	jalali_to_gregorian_datetime,
	toshamshi,
)


class TestCoerceGregorianDatetime(unittest.TestCase):
	def test_us_datetime_import_format(self):
		self.assertEqual(
			coerce_gregorian_datetime("4/20/2026 8:30"),
			"2026-04-20 08:30:00",
		)

	def test_iso_datetime_unchanged(self):
		self.assertEqual(
			coerce_gregorian_datetime("2026-04-20 08:30:00"),
			"2026-04-20 08:30:00",
		)

	def test_jalali_datetime_to_gregorian(self):
		# jdatetime: 1405-02-01 == 2026-04-21 (not 2026-04-20)
		self.assertEqual(
			coerce_gregorian_datetime("1405-02-01 08:30:00"),
			"2026-04-21 08:30:00",
		)

	def test_jalali_to_gregorian_datetime_iso(self):
		self.assertEqual(
			jalali_to_gregorian_datetime("2026-04-20 08:30:00"),
			"2026-04-20 08:30:00",
		)

	def test_toshamshi_roundtrip_display(self):
		# jdatetime: 2026-04-20 == 1405-01-31; round-trip via coerce stays stable
		self.assertEqual(
			toshamshi("2026-04-20 08:30:00", include_time=True),
			"1405-01-31 08:30:00",
		)
		gregorian = coerce_gregorian_datetime("1405-02-01 08:30:00")
		self.assertEqual(gregorian, "2026-04-21 08:30:00")
		self.assertEqual(
			toshamshi(gregorian, include_time=True),
			"1405-02-01 08:30:00",
		)


class TestCoerceGregorianDatetimeObjects(unittest.TestCase):
	def test_python_datetime(self):
		dt = datetime(2026, 4, 20, 8, 30, 0)
		self.assertEqual(coerce_gregorian_datetime(dt), "2026-04-20 08:30:00")


class TestCoerceGregorianDatetimeVariants(unittest.TestCase):
	def test_us_datetime_with_leading_zeros(self):
		self.assertEqual(
			coerce_gregorian_datetime("04/20/2026 08:30"),
			"2026-04-20 08:30:00",
		)

	def test_iso_without_seconds(self):
		self.assertEqual(
			coerce_gregorian_datetime("2026-04-20 08:30"),
			"2026-04-20 08:30:00",
		)


if __name__ == "__main__":
	unittest.main()
