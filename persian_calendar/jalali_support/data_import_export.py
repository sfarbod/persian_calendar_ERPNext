# Copyright (c) 2025, Persian Calendar contributors
# License: MIT

from __future__ import annotations

import frappe
from frappe.utils import cint

from persian_calendar.utils.data_io import convert_export_value, convert_import_value

_patches_applied = False


def apply_data_import_export_patches() -> None:
	global _patches_applied
	if _patches_applied:
		return
	_patches_applied = True

	_patch_data_export_exporter()
	_patch_data_import_exporter()
	_patch_data_import_importer()
	_patch_download_template()


def _patch_data_export_exporter() -> None:
	from frappe.core.doctype.data_export import exporter as mod

	if getattr(mod.export_data, "_jalali_patched", False):
		return

	_orig_init = mod.DataExporter.__init__
	_orig_add_data_row = mod.DataExporter.add_data_row
	_orig_export_data = mod.export_data

	def __init__(self, *args, export_dates_as_jalali=False, **kwargs):
		_orig_init(self, *args, **kwargs)
		self.export_dates_as_jalali = cint(export_dates_as_jalali)

	def add_data_row(self, rows, dt, parentfield, doc, rowidx):
		if not getattr(self, "export_dates_as_jalali", 0):
			return _orig_add_data_row(self, rows, dt, parentfield, doc, rowidx)

		# Jalali export: same as core exporter but Date/Datetime → Jalali (no formatdate).
		from frappe.core.utils import html2text
		from frappe.utils import format_duration

		d = doc.copy() if hasattr(doc, "copy") else dict(doc)
		meta = frappe.get_meta(dt)
		if self.all_doctypes:
			d.name = f'"{d.name}"'

		if len(rows) < rowidx + 1:
			rows.append([""] * (len(self.columns) + 1))
		row = rows[rowidx]

		_column_start_end = self.column_start_end.get((dt, parentfield))
		if _column_start_end:
			for i, c in enumerate(self.columns[_column_start_end.start : _column_start_end.end]):
				df = meta.get_field(c)
				fieldtype = df.fieldtype if df else "Data"
				raw = d.get(c, "")
				value = raw
				if value not in (None, ""):
					if fieldtype in ("Date", "Datetime"):
						value = convert_export_value(raw, fieldtype, True)
					elif fieldtype == "Duration" and df:
						value = format_duration(value, df.hide_days)
					elif fieldtype == "Text Editor" and value:
						value = html2text(value)
				row[_column_start_end.start + i + 1] = value

	@frappe.whitelist()
	def export_data(
		doctype=None,
		parent_doctype=None,
		all_doctypes=True,
		with_data=False,
		select_columns=None,
		file_type="CSV",
		template=False,
		filters=None,
		export_without_column_meta=False,
		export_dates_as_jalali=False,
	):
		_doctype = doctype
		if isinstance(_doctype, list):
			_doctype = _doctype[0]
		mod.make_access_log(
			doctype=_doctype,
			file_type=file_type,
			columns=select_columns,
			filters=filters,
			method=parent_doctype,
		)

		template_bool = template
		if isinstance(template, str):
			template_bool = template.lower() == "true"

		export_without_column_meta_bool = export_without_column_meta
		if isinstance(export_without_column_meta, str):
			export_without_column_meta_bool = export_without_column_meta.lower() == "true"

		fd = frappe.form_dict or {}
		if "export_dates_as_jalali" in fd:
			raw_jalali = fd.get("export_dates_as_jalali")
		else:
			raw_jalali = export_dates_as_jalali
		jalali_flag = cint(raw_jalali)

		exporter = mod.DataExporter(
			doctype=doctype,
			parent_doctype=parent_doctype,
			all_doctypes=all_doctypes,
			with_data=with_data,
			select_columns=select_columns,
			file_type=file_type,
			template=template_bool,
			filters=filters,
			export_without_column_meta=export_without_column_meta_bool,
			export_dates_as_jalali=jalali_flag,
		)
		exporter.build_response()

	mod.DataExporter.__init__ = __init__
	mod.DataExporter.add_data_row = add_data_row
	mod.export_data = export_data
	mod.export_data._jalali_patched = True


def _patch_data_import_exporter() -> None:
	from frappe.core.doctype.data_import import exporter as mod

	if getattr(mod.Exporter, "_jalali_patched", False):
		return

	_orig_init = mod.Exporter.__init__
	_orig_add_data_row = mod.Exporter.add_data_row

	def __init__(self, *args, export_dates_as_jalali=False, **kwargs):
		_orig_init(self, *args, **kwargs)
		self.export_dates_as_jalali = cint(export_dates_as_jalali)

	def add_data_row(self, doctype, parentfield, doc, rows, row_idx):
		rows = _orig_add_data_row(self, doctype, parentfield, doc, rows, row_idx)
		if not getattr(self, "export_dates_as_jalali", 0):
			return rows
		row = rows[row_idx]
		for i, df in enumerate(self.fields):
			if df.parent == doctype:
				if df.is_child_table_field and df.child_table_df.fieldname != parentfield:
					continue
				if df.fieldtype in ("Date", "Datetime"):
					row[i] = convert_export_value(row[i], df.fieldtype, True)
		return rows

	mod.Exporter.__init__ = __init__
	mod.Exporter.add_data_row = add_data_row
	mod.Exporter._jalali_patched = True


def _patch_download_template() -> None:
	from frappe.core.doctype.data_import import data_import as mod

	if getattr(mod.download_template, "_jalali_patched", False):
		return

	@frappe.whitelist()
	def download_template(
		doctype,
		export_fields=None,
		export_records=None,
		export_filters=None,
		file_type="CSV",
		export_dates_as_jalali=False,
	):
		frappe.has_permission(doctype, "read", throw=True)

		export_fields = frappe.parse_json(export_fields)
		export_filters = frappe.parse_json(export_filters)
		export_data_flag = export_records != "blank_template"

		e = mod.Exporter(
			doctype,
			export_fields=export_fields,
			export_data=export_data_flag,
			export_filters=export_filters,
			file_type=file_type,
			export_page_length=5 if export_records == "5_records" else None,
			export_dates_as_jalali=export_dates_as_jalali,
		)
		e.build_response()

	mod.download_template = download_template
	mod.download_template._jalali_patched = True


def _patch_data_import_importer() -> None:
	from frappe.core.doctype.data_import import importer as mod

	if getattr(mod.Row, "_jalali_patched", False):
		return

	_orig_before = mod.Importer.before_import
	_orig_parse = mod.Row.parse_value
	_orig_import_data = mod.Importer.import_data

	def before_import(self):
		frappe.flags.import_dates_from_jalali = cint(
			self.data_import.get("import_dates_from_jalali") if self.data_import else 0
		)
		return _orig_before(self)

	def import_data(self):
		try:
			return _orig_import_data(self)
		finally:
			frappe.flags.import_dates_from_jalali = 0

	def parse_value(self, value, col):
		if frappe.flags.get("import_dates_from_jalali") and col.df.fieldtype in ("Date", "Datetime"):
			converted = convert_import_value(value, col.df.fieldtype, True)
			if converted is not value and converted is not None:
				return converted
		return _orig_parse(self, value, col)

	mod.Importer.before_import = before_import
	mod.Importer.import_data = import_data
	mod.Row.parse_value = parse_value
	mod.Row._jalali_patched = True
