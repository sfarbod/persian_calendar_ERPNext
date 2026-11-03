# Copyright (c) 2026, Persian Calendar contributors
# License: MIT

"""v2.1.1 — Query Report / Report View export Jalali conversion tests."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cstr
from openpyxl import load_workbook

from persian_calendar.jalali_support.report_export import (
	apply_report_export_patches,
	convert_query_report_result,
	convert_report_export_value,
	convert_reportview_data_rows,
	is_report_export_date_value,
	parse_export_dates_as_jalali,
	_read_jalali_flag,
)
from persian_calendar.utils.data_io import convert_export_value


class TestReportExportJalaliHelpers(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		apply_report_export_patches()

	def test_parse_flag_representations_true_false(self):
		self.assertEqual(parse_export_dates_as_jalali(None), 1)
		self.assertEqual(parse_export_dates_as_jalali(""), 1)
		self.assertEqual(parse_export_dates_as_jalali(1), 1)
		self.assertEqual(parse_export_dates_as_jalali("1"), 1)
		self.assertEqual(parse_export_dates_as_jalali(True), 1)
		self.assertEqual(parse_export_dates_as_jalali("true"), 1)
		self.assertEqual(parse_export_dates_as_jalali("yes"), 1)
		self.assertEqual(parse_export_dates_as_jalali(0), 0)
		self.assertEqual(parse_export_dates_as_jalali("0"), 0)
		self.assertEqual(parse_export_dates_as_jalali(False), 0)
		self.assertEqual(parse_export_dates_as_jalali("false"), 0)
		self.assertEqual(parse_export_dates_as_jalali("off"), 0)
		# Explicit false must not become default
		self.assertEqual(parse_export_dates_as_jalali(False, default=1), 0)
		self.assertEqual(parse_export_dates_as_jalali("0", default=1), 0)

	def test_read_jalali_flag_absent_defaults_on(self):
		self.assertEqual(_read_jalali_flag(None), 1)
		self.assertEqual(_read_jalali_flag(frappe._dict()), 1)
		self.assertEqual(_read_jalali_flag({}), 1)
		self.assertEqual(_read_jalali_flag({"export_dates_as_jalali": 0}), 0)
		self.assertEqual(_read_jalali_flag({"export_dates_as_jalali": "0"}), 0)
		self.assertEqual(_read_jalali_flag({"export_dates_as_jalali": False}), 0)
		self.assertEqual(_read_jalali_flag({"export_dates_as_jalali": 1}), 1)
		self.assertEqual(_read_jalali_flag({"export_dates_as_jalali": "true"}), 1)

	def test_patch_idempotent(self):
		from frappe.desk import query_report, reportview

		v1 = getattr(query_report._export_query, "_jalali_patch_version", None)
		v2 = getattr(reportview._export_query, "_jalali_patch_version", None)
		apply_report_export_patches()
		apply_report_export_patches()
		self.assertEqual(getattr(query_report._export_query, "_jalali_patch_version", None), v1)
		self.assertEqual(getattr(reportview._export_query, "_jalali_patch_version", None), v2)
		self.assertTrue(getattr(query_report._export_query, "_jalali_is_wrapper", False))
		self.assertTrue(getattr(reportview._export_query, "_jalali_is_wrapper", False))

	def test_iso_detection(self):
		self.assertTrue(is_report_export_date_value("2026-09-06"))
		self.assertTrue(is_report_export_date_value("2026-09-06 14:35:12"))
		self.assertTrue(is_report_export_date_value("2026-09-06T14:35:12"))
		self.assertTrue(is_report_export_date_value(date(2026, 9, 6)))
		self.assertTrue(is_report_export_date_value(datetime(2026, 9, 6, 14, 35, 12)))
		self.assertFalse(is_report_export_date_value("10.04.2026"))
		self.assertFalse(is_report_export_date_value("06/09/2026"))
		self.assertFalse(is_report_export_date_value("ACC-PINV-2026-00001"))
		self.assertFalse(is_report_export_date_value(12345.67))
		self.assertFalse(is_report_export_date_value(None))
		self.assertFalse(is_report_export_date_value(""))

	def test_convert_date_objects_and_iso(self):
		expected = convert_export_value("2026-09-06", "Date", True)
		self.assertEqual(convert_report_export_value(date(2026, 9, 6), "Date", True), expected)
		self.assertEqual(convert_report_export_value("2026-09-06", "Date", True), expected)

		expected_dt = convert_export_value("2026-09-06 14:35:12", "Datetime", True)
		self.assertEqual(
			convert_report_export_value(datetime(2026, 9, 6, 14, 35, 12), "Datetime", True),
			expected_dt,
		)
		self.assertEqual(
			convert_report_export_value("2026-09-06 14:35:12", "Datetime", True),
			expected_dt,
		)

	def test_convert_off_and_empty(self):
		self.assertEqual(convert_report_export_value("2026-09-06", "Date", False), "2026-09-06")
		self.assertIsNone(convert_report_export_value(None, "Date", True))
		self.assertEqual(convert_report_export_value("", "Date", True), "")

	def test_ambiguous_and_non_date_untouched(self):
		self.assertEqual(convert_report_export_value("10.04.2026", "Date", True), "10.04.2026")
		self.assertEqual(convert_report_export_value("06/09/2026", "Date", True), "06/09/2026")
		self.assertEqual(convert_report_export_value(1000.5, "Currency", True), 1000.5)
		self.assertEqual(
			convert_report_export_value("ACC-PINV-2026-00001", "Link", True),
			"ACC-PINV-2026-00001",
		)
		self.assertEqual(convert_report_export_value("2026-09-06", "Data", True), "2026-09-06")

	def test_already_jalali_passthrough(self):
		# Year 1405 is treated as Jalali by toshamshi — no double conversion.
		out = convert_report_export_value("1405-06-15", "Date", True)
		self.assertEqual(out, "1405-06-15")

	def test_query_report_dict_rows(self):
		data = frappe._dict(
			columns=[
				{"fieldname": "posting_date", "label": "Posting Date", "fieldtype": "Date"},
				{"fieldname": "voucher_no", "label": "Voucher", "fieldtype": "Data"},
				{"fieldname": "debit", "label": "Debit", "fieldtype": "Currency"},
				{"fieldname": "modified", "label": "Modified", "fieldtype": "Datetime"},
			],
			result=[
				{
					"posting_date": date(2026, 9, 6),
					"voucher_no": "GL-001",
					"debit": 1500.25,
					"modified": datetime(2026, 9, 6, 14, 35, 12),
				},
				{
					"posting_date": None,
					"voucher_no": "GL-002",
					"debit": 0,
					"modified": "",
				},
			],
		)
		original_date = data.result[0]["posting_date"]
		converted = convert_query_report_result(data, True)

		self.assertEqual(original_date, date(2026, 9, 6))
		self.assertEqual(
			converted.result[0]["posting_date"],
			convert_export_value("2026-09-06", "Date", True),
		)
		self.assertEqual(converted.result[0]["voucher_no"], "GL-001")
		self.assertEqual(converted.result[0]["debit"], 1500.25)
		self.assertEqual(
			converted.result[0]["modified"],
			convert_export_value("2026-09-06 14:35:12", "Datetime", True),
		)
		self.assertIsNone(converted.result[1]["posting_date"])
		# Date columns retargeted so format_fields will not re-format.
		self.assertEqual(converted.columns[0]["fieldtype"], "Data")
		self.assertEqual(converted.columns[3]["fieldtype"], "Data")
		self.assertEqual(converted.columns[1]["fieldtype"], "Data")  # was already Data
		self.assertEqual(data.columns[0]["fieldtype"], "Date")  # original untouched

	def test_query_report_list_rows(self):
		data = frappe._dict(
			columns=[
				{"fieldname": "posting_date", "label": "Posting Date", "fieldtype": "Date"},
				{"fieldname": "qty", "label": "Qty", "fieldtype": "Float"},
			],
			result=[["2026-09-06", 12.5], [None, 0]],
		)
		converted = convert_query_report_result(data, True)
		self.assertEqual(
			converted.result[0][0],
			convert_export_value("2026-09-06", "Date", True),
		)
		self.assertEqual(converted.result[0][1], 12.5)
		self.assertIsNone(converted.result[1][0])
		# Original list row unchanged
		self.assertEqual(data.result[0][0], "2026-09-06")

	def test_query_report_off_noop(self):
		data = frappe._dict(
			columns=[{"fieldname": "posting_date", "fieldtype": "Date"}],
			result=[{"posting_date": "2026-09-06"}],
		)
		out = convert_query_report_result(data, False)
		self.assertIs(out, data)

	def test_query_report_no_date_columns(self):
		data = frappe._dict(
			columns=[
				{"fieldname": "account", "fieldtype": "Link"},
				{"fieldname": "balance", "fieldtype": "Currency"},
			],
			result=[{"account": "Cash", "balance": 100}],
		)
		out = convert_query_report_result(data, True)
		self.assertIs(out, data)

	def test_reportview_rows(self):
		fields_info = [
			{"fieldname": "posting_date", "fieldtype": "Date", "label": "Posting Date"},
			{"fieldname": "name", "fieldtype": "Data", "label": "ID"},
			{"fieldname": "grand_total", "fieldtype": "Currency", "label": "Total"},
		]
		data = [
			["Sr", "Posting Date", "ID", "Total"],
			[1, date(2026, 9, 6), "PINV-1", 99.5],
			[2, "10.04.2026", "PINV-2", 10],
		]
		out = convert_reportview_data_rows(data, fields_info, True)
		self.assertEqual(out[1][1], convert_export_value("2026-09-06", "Date", True))
		self.assertEqual(out[1][2], "PINV-1")
		self.assertEqual(out[1][3], 99.5)
		# Ambiguous string in a Date column stays unchanged
		self.assertEqual(out[2][1], "10.04.2026")
		self.assertEqual(data[1][1], date(2026, 9, 6))

	def test_large_result_set(self):
		n = 2500
		data = frappe._dict(
			columns=[
				{"fieldname": "posting_date", "fieldtype": "Date"},
				{"fieldname": "amount", "fieldtype": "Currency"},
			],
			result=[{"posting_date": "2026-09-06", "amount": i} for i in range(n)],
		)
		converted = convert_query_report_result(data, True)
		expected = convert_export_value("2026-09-06", "Date", True)
		self.assertEqual(len(converted.result), n)
		self.assertEqual(converted.result[0]["posting_date"], expected)
		self.assertEqual(converted.result[-1]["amount"], n - 1)
		self.assertEqual(data.result[0]["posting_date"], "2026-09-06")


class TestQueryReportExportIntegration(FrappeTestCase):
	"""Exercise stock ``_export_query`` with synthetic report data via format_fields path."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		apply_report_export_patches()

	def setUp(self):
		super().setUp()
		frappe.local.response = frappe._dict()
		if getattr(frappe.local, "form_dict", None) is not None:
			frappe.local.form_dict.pop("export_dates_as_jalali", None)

	@staticmethod
	def _xlsx_text(content: bytes) -> str:
		wb = load_workbook(BytesIO(content), data_only=True)
		ws = wb.active
		parts = []
		for row in ws.iter_rows(values_only=True):
			for cell in row:
				if cell is not None and str(cell).strip() != "":
					parts.append(str(cell))
		return "\n".join(parts)

	@staticmethod
	def _response_text() -> str:
		content = frappe.local.response.get("filecontent")
		if content:
			if isinstance(content, bytes):
				# CSV is utf-8 bytes; xlsx needs openpyxl
				if content[:2] == b"PK":
					wb = load_workbook(BytesIO(content), data_only=True)
					ws = wb.active
					parts = []
					for row in ws.iter_rows(values_only=True):
						for cell in row:
							if cell is not None and str(cell).strip() != "":
								parts.append(str(cell))
					return "\n".join(parts)
				return cstr(content)
			return cstr(content)
		return cstr(frappe.local.response.get("result") or "")

	def _export_synthetic(self, *, jalali: int, file_format_type: str = "CSV") -> str:
		"""Run format_fields + build_xlsx_data path the same way _export_query does."""
		from frappe.desk.query_report import build_xlsx_data, format_fields
		from frappe.desk.utils import get_csv_bytes
		from frappe.utils.xlsxutils import handle_html, make_xlsx

		data = frappe._dict(
			columns=[
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
				{"label": "Voucher", "fieldname": "voucher_no", "fieldtype": "Data", "width": 120},
				{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 100},
				{
					"label": "Modified",
					"fieldname": "modified",
					"fieldtype": "Datetime",
					"width": 140,
				},
			],
			result=[
				{
					"posting_date": date(2026, 9, 6),
					"voucher_no": "JV-0001",
					"debit": 2500.0,
					"modified": datetime(2026, 9, 6, 14, 35, 12),
				}
			],
			report_name="Synthetic GL",
			filters={},
			applied_filters={},
			add_total_row=0,
		)

		# Mirror the wrapper: convert then format when jalali ON.
		if jalali:
			from persian_calendar.jalali_support.report_export import convert_query_report_result

			converted = convert_query_report_result(data, True)
			data.columns = converted.columns
			data.result = converted.result

		format_fields(data, file_format_type)
		# Skip build_styles — requires a real Report DocType name.
		xlsx_data, _widths, styles = build_xlsx_data(
			data,
			include_indentation=False,
			include_filters=False,
			include_hidden_columns=False,
			build_styles=False,
		)

		if file_format_type == "CSV":
			content = get_csv_bytes(
				[[handle_html(v) if isinstance(v, str) else v for v in r] for r in xlsx_data],
				{},
			)
			return cstr(content)
		content = make_xlsx(xlsx_data, "Synthetic GL", styles=styles).getvalue()
		return self._xlsx_text(content)

	def test_csv_jalali_off(self):
		text = self._export_synthetic(jalali=0, file_format_type="CSV")
		self.assertIn("JV-0001", text)
		self.assertIn("2500", text)
		# Stock formatdate may localize; Gregorian year 2026 must appear, not Jalali 1405.
		self.assertIn("2026", text)
		self.assertNotIn("1405-06-15", text)

	def test_csv_jalali_on(self):
		text = self._export_synthetic(jalali=1, file_format_type="CSV")
		expected = convert_export_value("2026-09-06", "Date", True)
		expected_dt = convert_export_value("2026-09-06 14:35:12", "Datetime", True)
		self.assertIn(expected, text)
		self.assertIn(expected_dt, text)
		self.assertIn("JV-0001", text)
		self.assertIn("2500", text)

	def test_xlsx_jalali_on(self):
		text = self._export_synthetic(jalali=1, file_format_type="Excel")
		expected = convert_export_value("2026-09-06", "Date", True)
		self.assertIn(expected, text)
		self.assertIn("JV-0001", text)

	def test_full_export_query_wrapper_flag(self):
		"""Call patched ``_export_query`` with a stubbed ``run`` returning synthetic data."""
		from frappe.desk import query_report as mod
		from unittest.mock import patch

		apply_report_export_patches()
		fake = {
			"columns": [
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
				{"label": "Account", "fieldname": "account", "fieldtype": "Link", "width": 120},
				{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 100},
			],
			"result": [
				{"posting_date": "2026-09-06", "account": "Cash - PC", "debit": 42},
			],
			"add_total_row": 0,
		}

		form_params = frappe._dict(
			report_name="General Ledger",
			file_format_type="CSV",
			filters={},
			applied_filters={},
			custom_columns="[]",
			visible_idx=[],
			ignore_visible_idx=1,
			export_dates_as_jalali=1,
		)

		with patch.object(mod, "run", return_value=fake):
			# Avoid permission check on missing Report / ref_doctype for export_query whitelist;
			# call _export_query directly.
			mod._export_query(form_params, {}, populate_response=True)

		result = self._response_text()
		expected = convert_export_value("2026-09-06", "Date", True)
		self.assertIn(expected, result)
		self.assertIn("Cash - PC", result)
		self.assertIn("42", result)

	def test_full_export_query_wrapper_off(self):
		from frappe.desk import query_report as mod
		from unittest.mock import patch

		apply_report_export_patches()
		fake = {
			"columns": [
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
				{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 100},
			],
			"result": [{"posting_date": date(2026, 9, 6), "debit": 7}],
			"add_total_row": 0,
		}
		form_params = frappe._dict(
			report_name="General Ledger",
			file_format_type="CSV",
			filters={},
			applied_filters={},
			custom_columns="[]",
			visible_idx=[],
			ignore_visible_idx=1,
			export_dates_as_jalali=0,
		)
		with patch.object(mod, "run", return_value=fake):
			mod._export_query(form_params, {}, populate_response=True)

		result = self._response_text()
		self.assertIn("2026", result)
		self.assertNotIn(convert_export_value("2026-09-06", "Date", True), result)
		self.assertIn("7", result)

	def test_full_export_query_absent_flag_defaults_jalali(self):
		"""Parameter absent → Jalali (v2.1.1 default)."""
		from frappe.desk import query_report as mod
		from unittest.mock import patch

		apply_report_export_patches()
		fake = {
			"columns": [
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
				{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 100},
			],
			"result": [{"posting_date": "2026-09-06", "debit": 3}],
			"add_total_row": 0,
		}
		form_params = frappe._dict(
			report_name="General Ledger",
			file_format_type="CSV",
			filters={},
			applied_filters={},
			custom_columns="[]",
			visible_idx=[],
			ignore_visible_idx=1,
		)
		self.assertNotIn("export_dates_as_jalali", form_params)
		with patch.object(mod, "run", return_value=fake):
			mod._export_query(form_params, {}, populate_response=True)

		result = self._response_text()
		expected = convert_export_value("2026-09-06", "Date", True)
		self.assertIn(expected, result)
		self.assertIn("3", result)

	def test_full_export_query_string_false_is_gregorian(self):
		from frappe.desk import query_report as mod
		from unittest.mock import patch

		apply_report_export_patches()
		fake = {
			"columns": [
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
			],
			"result": [{"posting_date": date(2026, 9, 6)}],
			"add_total_row": 0,
		}
		form_params = frappe._dict(
			report_name="General Ledger",
			file_format_type="CSV",
			filters={},
			applied_filters={},
			custom_columns="[]",
			visible_idx=[],
			ignore_visible_idx=1,
			export_dates_as_jalali="false",
		)
		with patch.object(mod, "run", return_value=fake):
			mod._export_query(form_params, {}, populate_response=True)

		result = self._response_text()
		self.assertIn("2026", result)
		self.assertNotIn(convert_export_value("2026-09-06", "Date", True), result)

	def test_repeated_exports_independent(self):
		from frappe.desk import query_report as mod
		from unittest.mock import patch

		apply_report_export_patches()
		fake = {
			"columns": [
				{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
			],
			"result": [{"posting_date": "2026-09-06"}],
			"add_total_row": 0,
		}
		expected = convert_export_value("2026-09-06", "Date", True)

		for jalali, must_have, must_not in (
			(1, expected, None),
			(0, "2026", expected),
			(1, expected, None),
		):
			frappe.local.response = frappe._dict()
			form_params = frappe._dict(
				report_name="General Ledger",
				file_format_type="CSV",
				filters={},
				applied_filters={},
				custom_columns="[]",
				visible_idx=[],
				ignore_visible_idx=1,
				export_dates_as_jalali=jalali,
			)
			with patch.object(mod, "run", return_value={
				"columns": [dict(c) for c in fake["columns"]],
				"result": [dict(r) for r in fake["result"]],
				"add_total_row": 0,
			}):
				mod._export_query(form_params, {}, populate_response=True)
			result = self._response_text()
			self.assertIn(must_have, result)
			if must_not:
				self.assertNotIn(must_not, result)
