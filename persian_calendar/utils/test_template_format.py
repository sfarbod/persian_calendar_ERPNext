import unittest
from datetime import date

from persian_calendar.utils.template_format import (
	expand_toshamshi_placeholders,
	render_brace_template,
)


class TestRenderBraceTemplate(unittest.TestCase):
	def test_plain_field(self):
		out = render_brace_template("Cheque {cheque_no} — {party}", {"cheque_no": "2323211", "party": "Test Co"})
		self.assertEqual(out, "Cheque 2323211 — Test Co")

	def test_toshamshi_field(self):
		ctx = {"cheque_no": "1", "party": "A", "cheque_due_date": "2026-05-13"}
		tpl = "ثبت چک {cheque_no} — {party}\n{toshamshi(cheque_due_date)}"
		out = render_brace_template(tpl, ctx)
		self.assertIn("1405-02-23", out)
		self.assertIn("1", out)

	def test_toshamshi_include_time(self):
		ctx = {"posting_date": "2026-03-18 13:36:04"}
		out = render_brace_template("{toshamshi(posting_date, include_time=True)}", ctx)
		self.assertEqual(out, "1404-12-27 13:36:04")

	def test_empty_value(self):
		self.assertEqual(render_brace_template("{toshamshi(missing)}", {}), "")

	def test_missing_plain_field_preserved(self):
		self.assertEqual(render_brace_template("x {unknown} y", {}), "x {unknown} y")

	def test_datetime_date_object(self):
		out = render_brace_template("{toshamshi(birthdate)}", {"birthdate": date(1990, 1, 2)})
		self.assertEqual(out, "1368-10-12")

	def test_expand_only(self):
		self.assertEqual(
			expand_toshamshi_placeholders("{toshamshi(x)}", {"x": "2026-05-13"}),
			"1405-02-23",
		)


if __name__ == "__main__":
	unittest.main()
