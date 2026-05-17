import unittest
from datetime import date, datetime

from persian_calendar.utils.jalali import to_persian_digits, toshamshi


class TestToshamshi(unittest.TestCase):
	def test_date_string(self):
		self.assertEqual(toshamshi("1990-01-02"), "1368-10-12")

	def test_date_string_2026(self):
		self.assertEqual(toshamshi("2026-05-13"), "1405-02-23")

	def test_datetime_without_time_flag(self):
		self.assertEqual(toshamshi("2026-03-18 13:36:04"), "1404-12-27")

	def test_datetime_with_time(self):
		self.assertEqual(
			toshamshi("2026-03-18 13:36:04", include_time=True),
			"1404-12-27 13:36:04",
		)

	def test_microseconds_stripped(self):
		self.assertEqual(
			toshamshi("2026-03-18 13:36:04.446274", include_time=True),
			"1404-12-27 13:36:04",
		)

	def test_empty(self):
		self.assertEqual(toshamshi(None), "")
		self.assertEqual(toshamshi(""), "")

	def test_already_jalali(self):
		self.assertEqual(toshamshi("1404-12-28"), "1404-12-28")

	def test_persian_digits(self):
		self.assertEqual(
			toshamshi("1990-01-02", persian_digits=True),
			"۱۳۶۸-۱۰-۱۲",
		)

	def test_python_date(self):
		self.assertEqual(toshamshi(date(1990, 1, 2)), "1368-10-12")

	def test_python_datetime_include_time(self):
		self.assertEqual(
			toshamshi(datetime(2026, 3, 18, 13, 36, 4), include_time=True),
			"1404-12-27 13:36:04",
		)


class TestToPersianDigits(unittest.TestCase):
	def test_digits(self):
		self.assertEqual(to_persian_digits("1404-12-28 13:36:04"), "۱۴۰۴-۱۲-۲۸ ۱۳:۳۶:۰۴")

	def test_empty(self):
		self.assertEqual(to_persian_digits(None), "")


if __name__ == "__main__":
	unittest.main()
