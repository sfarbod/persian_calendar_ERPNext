# Copyright (c) 2025, Persian Calendar contributors
# License: MIT

"""Jalali Data Import / Export compatibility patches for Frappe v16.

Patched upstream surfaces (Frappe ≥16.52 / ERPNext ≥16.51):

* ``frappe.core.doctype.data_export.exporter`` — ``export_data``, ``DataExporter``
* ``frappe.core.doctype.data_import.exporter.Exporter`` — List View / template export
* ``frappe.core.doctype.data_import.data_import.download_template``
* ``frappe.core.doctype.data_import.importer`` — Jalali import parse

Frappe 16.52 changed ``Exporter.add_data_row`` from::

    add_data_row(doctype, parentfield, doc, rows, row_idx)

to::

    add_data_row(table_fieldname, doc, rows, row_idx)

Persian Calendar v2.0.2 still wrapped the old signature, causing HTTP 500 on
List View Export / download_template. This module detects the installed
signature and installs a matching wrapper.
"""

from __future__ import annotations

import inspect
import logging

import frappe
from frappe.utils import cint

from persian_calendar.utils.data_io import convert_export_value, convert_import_value

logger = logging.getLogger("persian_calendar.data_import_export")

_patches_applied = False

# Bump when wrapper contracts change so workers rebind after upgrade.
_IMPORT_EXPORTER_PATCH_VERSION = 3
_DATA_EXPORT_PATCH_VERSION = 2
_DOWNLOAD_TEMPLATE_PATCH_VERSION = 2
_IMPORTER_PATCH_VERSION = 2


def apply_data_import_export_patches() -> None:
	"""Idempotent install of import/export Jalali adapters (safe to call often)."""
	global _patches_applied

	_patch_data_export_exporter()
	_patch_data_import_exporter()
	_patch_data_import_importer()
	_patch_download_template()
	_patches_applied = True


def _load_stock_data_exporter_methods():
	import importlib.util
	from pathlib import Path

	from frappe.core.doctype.data_export import exporter as mod

	spec = importlib.util.spec_from_file_location(
		"_persian_calendar_frappe_data_exporter_stock",
		Path(mod.__file__).resolve(),
	)
	stock = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(stock)
	return stock.DataExporter.__init__, stock.DataExporter.add_data_row, stock.export_data


def _patch_data_export_exporter() -> None:
	from frappe.core.doctype.data_export import exporter as mod

	if getattr(mod.export_data, "_jalali_patch_version", None) == _DATA_EXPORT_PATCH_VERSION:
		return

	_orig_init, _orig_add_data_row, _ = _load_stock_data_exporter_methods()
	mod.DataExporter._jalali_orig_init = _orig_init
	mod.DataExporter._jalali_orig_add_data_row = _orig_add_data_row

	def __init__(self, *args, export_dates_as_jalali=False, **kwargs):
		self.export_dates_as_jalali = cint(export_dates_as_jalali)
		_orig_init(self, *args, **kwargs)

	__init__._jalali_is_wrapper = True

	def add_data_row(self, rows, dt, parentfield, doc, rowidx):
		if not getattr(self, "export_dates_as_jalali", 0):
			return _orig_add_data_row(self, rows, dt, parentfield, doc, rowidx)

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

	add_data_row._jalali_is_wrapper = True

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

	export_data._jalali_patched = True
	export_data._jalali_patch_version = _DATA_EXPORT_PATCH_VERSION

	mod.DataExporter.__init__ = __init__
	mod.DataExporter.add_data_row = add_data_row
	mod.DataExporter._jalali_patched = True
	mod.export_data = export_data


def _detect_import_exporter_add_data_row_style(orig_add_data_row) -> str:
	"""Return ``v1652`` (table_fieldname, doc, rows, row_idx) or ``legacy``."""
	try:
		params = [
			p.name
			for p in inspect.signature(orig_add_data_row).parameters.values()
			if p.name != "self" and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
		]
	except (TypeError, ValueError):
		params = []

	if params[:4] == ["table_fieldname", "doc", "rows", "row_idx"]:
		return "v1652"
	if len(params) >= 5 and params[0] == "doctype" and params[1] == "parentfield":
		return "legacy"
	if len(params) == 4:
		return "v1652"
	if len(params) >= 5:
		return "legacy"
	logger.warning(
		"Unable to detect Exporter.add_data_row signature %s; assuming v1652",
		params,
	)
	return "v1652"


def _load_stock_exporter_methods():
	"""Load unpatched Exporter methods from Frappe source (survives prior wraps)."""
	import importlib.util
	from pathlib import Path

	from frappe.core.doctype.data_import import exporter as mod

	spec = importlib.util.spec_from_file_location(
		"_persian_calendar_frappe_exporter_stock",
		Path(mod.__file__).resolve(),
	)
	stock = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(stock)
	return stock.Exporter.__init__, stock.Exporter.add_data_row


def _patch_data_import_exporter() -> None:
	from frappe.core.doctype.data_import import exporter as mod

	if getattr(mod.Exporter, "_jalali_patch_version", None) == _IMPORT_EXPORTER_PATCH_VERSION:
		return

	_orig_init, _orig_add_data_row = _load_stock_exporter_methods()
	mod.Exporter._jalali_orig_init = _orig_init
	mod.Exporter._jalali_orig_add_data_row = _orig_add_data_row
	style = _detect_import_exporter_add_data_row_style(_orig_add_data_row)

	def __init__(self, *args, export_dates_as_jalali=False, **kwargs):
		self.export_dates_as_jalali = cint(export_dates_as_jalali)
		_orig_init(self, *args, **kwargs)

	__init__._jalali_is_wrapper = True

	if style == "v1652":

		def add_data_row(self, table_fieldname, doc, rows, row_idx):
			rows = _orig_add_data_row(self, table_fieldname, doc, rows, row_idx)
			if not getattr(self, "export_dates_as_jalali", 0):
				return rows
			row = rows[row_idx]
			for i, df in enumerate(self.fields):
				if df.is_child_table_field:
					if not df.child_table_df or df.child_table_df.fieldname != table_fieldname:
						continue
				elif table_fieldname:
					continue
				if df.fieldtype in ("Date", "Datetime"):
					row[i] = convert_export_value(row[i], df.fieldtype, True)
			return rows

	else:

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

	add_data_row._jalali_is_wrapper = True
	add_data_row._jalali_style = style

	mod.Exporter.__init__ = __init__
	mod.Exporter.add_data_row = add_data_row
	mod.Exporter._jalali_patched = True
	mod.Exporter._jalali_patch_version = _IMPORT_EXPORTER_PATCH_VERSION
	logger.info("Patched data_import.Exporter.add_data_row style=%s", style)


def _patch_download_template() -> None:
	from frappe.core.doctype.data_import import data_import as mod
	from frappe.core.doctype.data_import.exporter import Exporter
	from frappe.model.utils.user_settings import get_user_settings

	if getattr(mod.download_template, "_jalali_patch_version", None) == _DOWNLOAD_TEMPLATE_PATCH_VERSION:
		return

	@frappe.whitelist()
	def download_template(
		doctype: str,
		export_fields=None,
		export_records=None,
		export_filters=None,
		file_type: str = "CSV",
		export_dates_as_jalali=False,
	):
		"""List View / Data Import template download — Frappe v16.52+ + Jalali flag."""
		frappe.has_permission(doctype, "read", throw=True)

		export_fields = frappe.parse_json(export_fields)
		export_filters = frappe.parse_json(export_filters)
		export_data = export_records != "blank_template"

		list_settings = frappe.parse_json(get_user_settings(doctype)).get("List", {})
		sort_by = list_settings.get("sort_by")
		sort_order = list_settings.get("sort_order")

		if sort_by and not frappe.get_meta(doctype).get_field(sort_by):
			sort_by = None

		if sort_order and sort_order.upper() not in ("ASC", "DESC"):
			sort_order = None

		order_by = f"{sort_by} {sort_order}" if sort_by and sort_order else None

		fd = frappe.form_dict or {}
		if "export_dates_as_jalali" in fd:
			raw_jalali = fd.get("export_dates_as_jalali")
		else:
			raw_jalali = export_dates_as_jalali
		jalali_flag = cint(raw_jalali)

		e = Exporter(
			doctype,
			export_fields=export_fields,
			export_data=export_data,
			export_filters=export_filters,
			file_type=file_type,
			export_page_length=5 if export_records == "5_records" else None,
			order_by=order_by,
			export_dates_as_jalali=jalali_flag,
		)
		e.build_response()

	download_template._jalali_patched = True
	download_template._jalali_patch_version = _DOWNLOAD_TEMPLATE_PATCH_VERSION
	mod.download_template = download_template


def _patch_data_import_importer() -> None:
	from frappe.core.doctype.data_import import importer as mod

	if getattr(mod.Row, "_jalali_patch_version", None) == _IMPORTER_PATCH_VERSION:
		return

	if not getattr(mod.Importer.before_import, "_jalali_is_wrapper", False):
		mod.Importer._jalali_orig_before_import = mod.Importer.before_import
	if not getattr(mod.Row.parse_value, "_jalali_is_wrapper", False):
		mod.Row._jalali_orig_parse_value = mod.Row.parse_value
	if not getattr(mod.Importer.import_data, "_jalali_is_wrapper", False):
		mod.Importer._jalali_orig_import_data = mod.Importer.import_data

	_orig_before = mod.Importer._jalali_orig_before_import
	_orig_parse = mod.Row._jalali_orig_parse_value
	_orig_import_data = mod.Importer._jalali_orig_import_data

	def before_import(self):
		frappe.flags.import_dates_from_jalali = cint(
			self.data_import.get("import_dates_from_jalali") if self.data_import else 0
		)
		return _orig_before(self)

	before_import._jalali_is_wrapper = True

	def import_data(self):
		try:
			return _orig_import_data(self)
		finally:
			frappe.flags.import_dates_from_jalali = 0

	import_data._jalali_is_wrapper = True

	def parse_value(self, value, col):
		if frappe.flags.get("import_dates_from_jalali") and col.df.fieldtype in ("Date", "Datetime"):
			converted = convert_import_value(value, col.df.fieldtype, True)
			if converted is not value and converted is not None:
				return converted
		return _orig_parse(self, value, col)

	parse_value._jalali_is_wrapper = True

	mod.Importer.before_import = before_import
	mod.Importer.import_data = import_data
	mod.Row.parse_value = parse_value
	mod.Row._jalali_patched = True
	mod.Row._jalali_patch_version = _IMPORTER_PATCH_VERSION
