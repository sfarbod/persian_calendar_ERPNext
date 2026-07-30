"""Phase 5A-1 — toshamshi / toshamsi public conversion API contract tests.

Expected Jalali values are hard-coded from independent jdatetime verification
(not derived by calling the function under test to generate expectations).
"""

from __future__ import annotations

import inspect
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from persian_calendar import api as public_api
from persian_calendar.utils import jalali as jalali_mod
from persian_calendar.utils.jalali import toshamshi, toshamsi


# Independently verified Gregorian → Jalali mappings (jdatetime 4.x / 2026-07-29).
_G1990_01_02 = "1368-10-12"
_G2026_05_13 = "1405-02-23"
_G2026_03_21 = "1405-01-01"  # Farvardin 1, 1405
_G2025_03_21 = "1404-01-01"  # Farvardin 1, 1404
_G2025_03_20 = "1403-12-30"  # Esfand 30, leap year 1403
_G2024_03_19 = "1402-12-29"  # Esfand 29, non-leap 1402
_G2024_03_20 = "1403-01-01"  # Farvardin 1, 1403
_G2026_03_18_DT = "1404-12-27"
_G2025_12_31 = "1404-10-10"
_G2026_01_01 = "1404-10-11"


class TestCanonicalIdentity(unittest.TestCase):
	def test_toshamsi_is_toshamshi_identity(self):
		self.assertIs(toshamsi, toshamshi)
		self.assertIs(jalali_mod.toshamsi, jalali_mod.toshamshi)
		self.assertIs(public_api.toshamsi, public_api.toshamshi)
		self.assertIs(public_api.toshamshi, toshamshi)

	def test_signatures_identical(self):
		self.assertEqual(inspect.signature(toshamshi), inspect.signature(toshamsi))
		params = list(inspect.signature(toshamshi).parameters.values())
		self.assertEqual([p.name for p in params], ["value", "include_time", "format", "persian_digits"])
		self.assertEqual(params[1].default, False)
		self.assertEqual(params[2].default, "YYYY-MM-DD")
		self.assertEqual(params[3].default, False)

	def test_public_api_exports(self):
		self.assertIn("toshamshi", public_api.__all__)
		self.assertIn("toshamsi", public_api.__all__)


class TestToshamshiInputs(unittest.TestCase):
	def test_none_and_empty(self):
		self.assertEqual(toshamshi(None), "")
		self.assertEqual(toshamshi(""), "")
		self.assertEqual(toshamsi(None), "")
		self.assertEqual(toshamsi(""), "")

	def test_whitespace_only(self):
		self.assertEqual(toshamshi("   "), "")
		self.assertEqual(toshamsi("\t"), "")

	def test_gregorian_date_string(self):
		self.assertEqual(toshamshi("1990-01-02"), _G1990_01_02)
		self.assertEqual(toshamshi("2026-05-13"), _G2026_05_13)

	def test_gregorian_datetime_string(self):
		self.assertEqual(toshamshi("2026-03-18 13:36:04"), _G2026_03_18_DT)
		self.assertEqual(
			toshamshi("2026-03-18 13:36:04", include_time=True),
			f"{_G2026_03_18_DT} 13:36:04",
		)

	def test_python_date_and_datetime(self):
		self.assertEqual(toshamshi(date(1990, 1, 2)), _G1990_01_02)
		self.assertEqual(
			toshamshi(datetime(2026, 3, 18, 13, 36, 4), include_time=True),
			f"{_G2026_03_18_DT} 13:36:04",
		)

	def test_timezone_aware_preserves_wall_clock(self):
		# No site/timezone conversion — uses datetime component fields as-is.
		aware = datetime(2026, 3, 18, 13, 36, 4, tzinfo=timezone(timedelta(hours=3, minutes=30)))
		self.assertEqual(toshamshi(aware, include_time=True), f"{_G2026_03_18_DT} 13:36:04")
		aware_utc = datetime(2026, 3, 18, 13, 36, 4, tzinfo=timezone.utc)
		self.assertEqual(toshamshi(aware_utc, include_time=True), f"{_G2026_03_18_DT} 13:36:04")

	def test_invalid_inputs_return_empty(self):
		self.assertEqual(toshamshi("not-a-date"), "")
		self.assertEqual(toshamshi(object()), "")
		self.assertEqual(toshamshi(12345), "")
		self.assertEqual(toshamsi({"a": 1}), "")

	def test_already_jalali_year_heuristic(self):
		self.assertEqual(toshamshi("1404-12-28"), "1404-12-28")
		self.assertEqual(toshamshi("1403-12-30"), "1403-12-30")

	def test_farvardin_1(self):
		self.assertEqual(toshamshi("2026-03-21"), _G2026_03_21)
		self.assertEqual(toshamshi("2025-03-21"), _G2025_03_21)
		self.assertEqual(toshamshi(date(2024, 3, 20)), _G2024_03_20)

	def test_esfand_29_non_leap(self):
		self.assertEqual(toshamshi("2024-03-19"), _G2024_03_19)

	def test_esfand_30_leap_year(self):
		self.assertEqual(toshamshi("2025-03-20"), _G2025_03_20)

	def test_gregorian_year_transition(self):
		self.assertEqual(toshamshi("2025-12-31"), _G2025_12_31)
		self.assertEqual(toshamshi("2026-01-01"), _G2026_01_01)

	def test_default_and_explicit_format(self):
		self.assertEqual(toshamshi("2026-05-13"), "1405-02-23")
		self.assertEqual(toshamshi("2026-05-13", format="YYYY/MM/DD"), "1405/02/23")
		self.assertEqual(
			toshamshi("2026-03-18 13:36:04", True, "YYYY/MM/DD"),
			"1404/12/27 13:36:04",
		)

	def test_persian_digits(self):
		self.assertEqual(toshamshi("1990-01-02", persian_digits=False), _G1990_01_02)
		self.assertEqual(toshamshi("1990-01-02", persian_digits=True), "۱۳۶۸-۱۰-۱۲")
		self.assertEqual(
			toshamshi("2026-03-18 13:36:04", include_time=True, persian_digits=True),
			"۱۴۰۴-۱۲-۲۷ ۱۳:۳۶:۰۴",
		)

	def test_input_not_mutated(self):
		d = date(2026, 5, 13)
		dt = datetime(2026, 3, 18, 13, 36, 4)
		s = "2026-05-13"
		toshamshi(d)
		toshamshi(dt, include_time=True)
		toshamshi(s)
		self.assertEqual(d, date(2026, 5, 13))
		self.assertEqual(dt, datetime(2026, 3, 18, 13, 36, 4))
		self.assertEqual(s, "2026-05-13")

	def test_include_time_false_on_midnight_datetime(self):
		# Midnight datetime still counts as datetime → time appended when include_time=True
		self.assertEqual(toshamshi(datetime(2026, 5, 13, 0, 0, 0)), _G2026_05_13)
		self.assertEqual(
			toshamshi(datetime(2026, 5, 13, 0, 0, 0), include_time=True),
			f"{_G2026_05_13} 00:00:00",
		)


class TestAliasEquivalence(unittest.TestCase):
	CASES = (
		(("2026-05-13",), {}),
		(("2026-05-13", True), {}),
		(("2026-03-18 13:36:04", True, "YYYY/MM/DD"), {}),
		(("2026-03-18 13:36:04", True, "YYYY/MM/DD", True), {}),
		(("1990-01-02",), {"persian_digits": True}),
		((None,), {}),
		(("",), {}),
		((date(2025, 3, 20),), {}),
	)

	def test_positional_and_keyword_parity(self):
		for args, kwargs in self.CASES:
			with self.subTest(args=args, kwargs=kwargs):
				self.assertEqual(toshamshi(*args, **kwargs), toshamsi(*args, **kwargs))
				self.assertEqual(
					public_api.toshamshi(*args, **kwargs),
					jalali_mod.toshamshi(*args, **kwargs),
				)


class TestNoCalendarCoupling(unittest.TestCase):
	def test_independent_of_display_calendar_helpers(self):
		"""Explicit conversion must ignore Display Calendar preference helpers."""
		value = "2026-05-13"
		with patch(
			"persian_calendar.jalali_support.formatters.get_effective_display_calendar",
			return_value="Gregorian",
		):
			a = toshamshi(value)
		with patch(
			"persian_calendar.jalali_support.formatters.get_effective_display_calendar",
			return_value="Jalali",
		):
			b = toshamshi(value)
		self.assertEqual(a, _G2026_05_13)
		self.assertEqual(b, _G2026_05_13)
		self.assertEqual(a, b)

	def test_independent_of_business_calendar_resolver(self):
		with patch(
			"persian_calendar.calendar.resolve.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(toshamshi("2026-05-13"), _G2026_05_13)
		with patch(
			"persian_calendar.calendar.resolve.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			self.assertEqual(toshamsi("2026-05-13"), _G2026_05_13)

	def test_module_does_not_import_period_engine(self):
		import ast
		from pathlib import Path

		src = Path(jalali_mod.__file__).read_text(encoding="utf-8")
		tree = ast.parse(src)
		names: set[str] = set()
		for node in ast.walk(tree):
			if isinstance(node, ast.ImportFrom):
				for alias in node.names:
					names.add(alias.name)
			elif isinstance(node, ast.Import):
				for alias in node.names:
					names.add(alias.name)
		self.assertNotIn("BusinessPeriodEngine", names)
		self.assertNotIn("BusinessPeriod", names)
		self.assertNotIn("get_business_calendar_for_company", names)


class TestJinjaExposure(FrappeTestCase):
	def test_both_names_in_jinja_hooks(self):
		from frappe.utils.jinja import get_jinja_hooks

		methods, _filters = get_jinja_hooks()
		self.assertIsNotNone(methods)
		self.assertIn("toshamshi", methods)
		self.assertIn("toshamsi", methods)
		self.assertIs(methods["toshamsi"], methods["toshamshi"])
		self.assertIs(methods["toshamshi"], toshamshi)

	def test_jinja_render_toshamshi_and_toshamsi(self):
		import frappe

		ctx = {"posting_date": "2026-05-13", "creation": "2026-03-18 13:36:04"}
		out_a = frappe.render_template("{{ toshamshi(posting_date) }}", ctx)
		out_b = frappe.render_template("{{ toshamsi(posting_date) }}", ctx)
		self.assertEqual(out_a, _G2026_05_13)
		self.assertEqual(out_b, _G2026_05_13)
		self.assertEqual(out_a, out_b)

		timed = frappe.render_template(
			"{{ toshamshi(creation, include_time=True) }}",
			ctx,
		)
		self.assertEqual(timed, f"{_G2026_03_18_DT} 13:36:04")
		timed_alias = frappe.render_template(
			"{{ toshamsi(creation, include_time=True, format='YYYY/MM/DD') }}",
			ctx,
		)
		self.assertEqual(timed_alias, "1404/12/27 13:36:04")

		digits = frappe.render_template(
			"{{ toshamshi(posting_date, persian_digits=True) }}",
			ctx,
		)
		self.assertEqual(digits, "۱۴۰۵-۰۲-۲۳")
		self.assertNotIn("datetime", digits.lower())
		self.assertIsInstance(digits, str)

	def test_print_html_path_safe_output(self):
		"""Shared HTML/Jinja path used by Print Formats (PDF uses the same render)."""
		import frappe

		html = frappe.render_template(
			"<p>{{ toshamshi(doc.posting_date, format='YYYY/MM/DD') }}</p>"
			"<p>{{ toshamsi(doc.posting_date) }}</p>",
			{"doc": {"posting_date": "2026-05-13"}},
		)
		self.assertIn("1405/02/23", html)
		self.assertIn(_G2026_05_13, html)
		self.assertNotIn("<object", html)
		self.assertNotIn("datetime.date", html)


class TestConversionDiagnostics(FrappeTestCase):
	def test_validate_public_conversion_api_clean(self):
		from persian_calendar.calendar.diagnostics import validate_public_conversion_api

		issues = validate_public_conversion_api()
		self.assertEqual(issues, [], msg="\n".join(issues))


if __name__ == "__main__":
	unittest.main()
