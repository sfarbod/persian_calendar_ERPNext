# Copyright (c) 2026, Persian Calendar contributors
# License: MIT

"""v2.1.0 — Frappe import/export signature compatibility and regression tests."""

from __future__ import annotations

import inspect
import json
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cstr

from persian_calendar.jalali_support import data_import_export as dio
from persian_calendar.jalali_support.data_import_export import apply_data_import_export_patches
from persian_calendar.utils.data_io import convert_export_value, convert_import_value


class TestFrappeIOCompatibility(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		apply_data_import_export_patches()

	def test_import_exporter_add_data_row_matches_frappe(self):
		from frappe.core.doctype.data_import.exporter import Exporter

		(
			stock_init,
			stock_add,
		) = dio._load_stock_exporter_methods()
		style = dio._detect_import_exporter_add_data_row_style(stock_add)
		self.assertEqual(style, "v1652")
		params = [
			p.name for p in inspect.signature(Exporter.add_data_row).parameters.values() if p.name != "self"
		]
		self.assertEqual(params[:4], ["table_fieldname", "doc", "rows", "row_idx"])
		self.assertEqual(getattr(Exporter.add_data_row, "_jalali_style", None), "v1652")

	def test_repeated_apply_is_idempotent(self):
		from frappe.core.doctype.data_import.exporter import Exporter

		first = Exporter.add_data_row
		apply_data_import_export_patches()
		apply_data_import_export_patches()
		self.assertIs(Exporter.add_data_row, first)
		self.assertEqual(Exporter._jalali_patch_version, dio._IMPORT_EXPORTER_PATCH_VERSION)

	def test_download_template_http_style_no_500(self):
		from frappe.core.doctype.data_import.data_import import download_template

		frappe.local.response = frappe._dict()
		download_template(
			doctype="User",
			export_fields=json.dumps({"User": ["name", "birth_date"]}),
			export_records="5_records",
			file_type="CSV",
			export_dates_as_jalali=1,
		)
		result = cstr(frappe.local.response.get("result") or "")
		self.assertTrue(result)
		self.assertIn("ID", result)

	def test_import_value_helpers(self):
		self.assertEqual(convert_import_value("1405-06-15", "Date", True), date(2026, 9, 6))
		self.assertEqual(convert_import_value("2026-09-06", "Date", False), "2026-09-06")
		self.assertEqual(
			convert_export_value("2026-09-06 14:35:12", "Datetime", True),
			"1405-06-15 14:35:12",
		)


class TestDataImportJalaliFlag(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		apply_data_import_export_patches()

	def test_parse_value_converts_when_flag_set(self):
		from frappe.core.doctype.data_import.importer import Row

		row = Row.__new__(Row)
		col = frappe._dict(df=frappe._dict(fieldtype="Date"))
		frappe.flags.import_dates_from_jalali = 1
		try:
			got = Row.parse_value(row, "1405-06-15", col)
			self.assertEqual(got, date(2026, 9, 6))
		finally:
			frappe.flags.import_dates_from_jalali = 0

	def test_parse_value_passthrough_when_flag_unset(self):
		from frappe.core.doctype.data_import.importer import Row

		row = Row.__new__(Row)
		col = frappe._dict(df=frappe._dict(fieldtype="Date", date_format=None))
		# Without flag, stock parse may return string if no date_format
		frappe.flags.import_dates_from_jalali = 0
		got = Row.parse_value(row, "1405-06-15", col)
		# Must NOT convert Jalali when flag off
		self.assertNotEqual(got, date(2026, 9, 6))
