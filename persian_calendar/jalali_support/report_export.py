# Copyright (c) 2026, Persian Calendar contributors
# License: MIT

"""Jalali date conversion for Frappe Query Report / Report View export.

Patched upstream surfaces (Frappe ≥16.52):

* ``frappe.desk.query_report._export_query`` — Query Report / Script Report CSV & Excel
* ``frappe.desk.query_report.format_fields`` — skipped for Date/Datetime when Jalali ON
* ``frappe.desk.reportview._export_query`` — Report View / Report Builder export

Conversion is **export-only**: report ``run()`` results used for desk display are not
shared with the converted export rows (rows are shallow-copied before mutation).
Column detection is metadata-driven (``fieldtype`` Date / Datetime only).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

import frappe
from frappe.utils import cint

from persian_calendar.utils.data_io import convert_export_value

logger = logging.getLogger("persian_calendar.report_export")

_patches_applied = False
_QUERY_REPORT_PATCH_VERSION = 1
_REPORTVIEW_PATCH_VERSION = 1

# Strict ISO-like date/datetime only — no locale-ambiguous forms (dd/mm/yyyy, 10.04.2026).
_ISO_DATE_RE = re.compile(
	r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?$"
)


def apply_report_export_patches() -> None:
	"""Idempotent install of report-export Jalali adapters."""
	global _patches_applied
	_patch_query_report_export()
	_patch_reportview_export()
	_patches_applied = True


def is_report_export_date_value(value: Any) -> bool:
	"""True when *value* is a date/datetime object or a strict ISO date/datetime string."""
	if value is None or value == "":
		return False
	if isinstance(value, (datetime, date)):
		return True
	if isinstance(value, str):
		text = value.strip()
		if "T" in text:
			text = text.replace("T", " ", 1)
		text = re.sub(r"(\d{1,2}:\d{2}:\d{2})\.\d+", r"\1", text)
		return bool(_ISO_DATE_RE.match(text))
	return False


def convert_report_export_value(value: Any, fieldtype: str | None, enabled: bool) -> Any:
	"""Convert a report cell for Jalali export without touching ambiguous strings."""
	if not enabled or not fieldtype or fieldtype not in ("Date", "Datetime"):
		return value
	if value in (None, ""):
		return value

	include_time = fieldtype == "Datetime"

	if isinstance(value, str):
		if not is_report_export_date_value(value):
			# Ambiguous / already-formatted / non-ISO — leave unchanged.
			return value
		# Avoid coerce→getdate on Jalali ISO strings (would treat them as Gregorian).
		from persian_calendar.utils.jalali import is_likely_jalali_date, toshamshi

		if is_likely_jalali_date(value):
			return toshamshi(value, include_time=include_time)
		return convert_export_value(value, fieldtype, True)

	if isinstance(value, (datetime, date)):
		# DB/report date objects are Gregorian; year-in-Jalali-range is extremely rare.
		return convert_export_value(value, fieldtype, True)

	return convert_export_value(value, fieldtype, True)


def _date_column_indexes(columns: list) -> list[tuple[int, str, str]]:
	"""Return (index, fieldname, fieldtype) for Date/Datetime report columns."""
	out: list[tuple[int, str, str]] = []
	for i, col in enumerate(columns or []):
		if not isinstance(col, dict):
			continue
		ft = col.get("fieldtype")
		if ft not in ("Date", "Datetime"):
			continue
		fname = col.get("fieldname") or col.get("field") or i
		out.append((i, fname, ft))
	return out


def convert_query_report_result(data: frappe._dict, enabled: bool) -> frappe._dict:
	"""Return a copy of *data* with Date/Datetime cells converted when *enabled*.

	Does not mutate the original ``data.result`` list or its row objects.
	When enabled, Date/Datetime column fieldtypes are set to ``Data`` on the copy
	so stock ``format_fields`` will not re-apply ``formatdate`` / ``format_datetime``.
	"""
	if not enabled or not data:
		return data

	columns = data.get("columns") or []
	date_cols = _date_column_indexes(columns)
	if not date_cols:
		return data

	# Copy container + columns so we can retarget fieldtypes without touching cache.
	out = frappe._dict(data)
	out.columns = [dict(c) if isinstance(c, dict) else c for c in columns]
	date_cols = _date_column_indexes(out.columns)

	new_result = []
	for row in data.get("result") or []:
		if isinstance(row, dict):
			new_row = dict(row)
			for _i, fname, ft in date_cols:
				if fname in new_row:
					new_row[fname] = convert_report_export_value(new_row[fname], ft, True)
			new_result.append(new_row)
		elif isinstance(row, (list, tuple)):
			new_row = list(row)
			for i, _fname, ft in date_cols:
				if i < len(new_row):
					new_row[i] = convert_report_export_value(new_row[i], ft, True)
			new_result.append(new_row)
		else:
			new_result.append(row)

	out.result = new_result

	# Prevent stock format_fields from reformatting Jalali strings as Gregorian.
	for i, _fname, _ft in date_cols:
		col = out.columns[i]
		if isinstance(col, dict):
			col["fieldtype"] = "Data"

	return out


def convert_reportview_data_rows(
	data: list[list],
	fields_info: list[dict],
	enabled: bool,
) -> list[list]:
	"""Convert Date/Datetime cells in Report View export rows (header + Sr column).

	``data[0]`` is the header ``[Sr, label, ...]``. Body rows are
	``[sr, value0, value1, ...]`` matching ``fields_info`` starting at index 1.
	"""
	if not enabled or not data or len(data) < 2 or not fields_info:
		return data

	date_offsets: list[tuple[int, str]] = []
	for i, info in enumerate(fields_info):
		ft = (info or {}).get("fieldtype")
		if ft in ("Date", "Datetime"):
			# data columns: 0 = Sr, 1.. = fields_info[0..]
			date_offsets.append((i + 1, ft))

	if not date_offsets:
		return data

	out = [data[0]]
	for row in data[1:]:
		if not isinstance(row, (list, tuple)):
			out.append(row)
			continue
		new_row = list(row)
		for col_idx, ft in date_offsets:
			if col_idx < len(new_row):
				new_row[col_idx] = convert_report_export_value(new_row[col_idx], ft, True)
		out.append(new_row)
	return out


def _read_jalali_flag(form_params) -> int:
	if form_params is None:
		return 0
	if isinstance(form_params, dict):
		raw = form_params.get("export_dates_as_jalali")
	else:
		raw = getattr(form_params, "export_dates_as_jalali", None)
	if raw is None and hasattr(frappe.local, "form_dict"):
		raw = frappe.local.form_dict.get("export_dates_as_jalali")
	return cint(raw)


def _unwrap_export_query(fn):
	"""Return the stock ``_export_query`` if *fn* is already our wrapper."""
	while getattr(fn, "_jalali_is_wrapper", False) and getattr(fn, "_jalali_orig", None):
		fn = fn._jalali_orig
	return fn


def _patch_query_report_export() -> None:
	from frappe.desk import query_report as mod

	if getattr(mod._export_query, "_jalali_patch_version", None) == _QUERY_REPORT_PATCH_VERSION:
		return

	# Keep the live-module function so its globals resolve ``format_fields`` on *mod*.
	_orig = _unwrap_export_query(mod._export_query)

	def _export_query(form_params, csv_params, populate_response=True):
		jalali = _read_jalali_flag(form_params)
		if not jalali:
			return _orig(form_params, csv_params, populate_response=populate_response)

		# Temporarily replace format_fields: convert after run+filter, before format.
		_orig_format = mod.format_fields

		def _format_fields_jalali(data, file_format_type=None):
			converted = convert_query_report_result(data, True)
			# Replace result/columns with copies so original row objects from run()
			# are not mutated; stock format_fields then sees Jalali strings / Data cols.
			data.columns = converted.columns
			data.result = converted.result
			return _orig_format(data, file_format_type)

		mod.format_fields = _format_fields_jalali
		try:
			return _orig(form_params, csv_params, populate_response=populate_response)
		finally:
			mod.format_fields = _orig_format

	_export_query._jalali_is_wrapper = True
	_export_query._jalali_patch_version = _QUERY_REPORT_PATCH_VERSION
	_export_query._jalali_orig = _orig
	mod._export_query = _export_query
	logger.debug("patched frappe.desk.query_report._export_query (v%s)", _QUERY_REPORT_PATCH_VERSION)


def _patch_reportview_export() -> None:
	from frappe.desk import reportview as mod

	if getattr(mod._export_query, "_jalali_patch_version", None) == _REPORTVIEW_PATCH_VERSION:
		return

	_orig = _unwrap_export_query(mod._export_query)

	def _export_query(form_params, csv_params, populate_response=True):
		jalali = _read_jalali_flag(form_params)
		if not jalali:
			return _orig(form_params, csv_params, populate_response=populate_response)

		# Convert after duration handling: capture fields_info, then rewrite rows.
		_orig_handle = mod.handle_duration_fieldtype_values
		_orig_get_field_info = mod.get_field_info
		fields_info_box: dict[str, Any] = {"info": None}

		def _get_field_info(fields, parent_doctype):
			info = _orig_get_field_info(fields, parent_doctype)
			fields_info_box["info"] = info
			return info

		def _handle_duration(parent_doctype, data, fields):
			data = _orig_handle(parent_doctype, data, fields)
			info = fields_info_box.get("info") or []
			return convert_reportview_data_rows(data, info, True)

		mod.get_field_info = _get_field_info
		mod.handle_duration_fieldtype_values = _handle_duration
		try:
			return _orig(form_params, csv_params, populate_response=populate_response)
		finally:
			mod.get_field_info = _orig_get_field_info
			mod.handle_duration_fieldtype_values = _orig_handle

	_export_query._jalali_is_wrapper = True
	_export_query._jalali_patch_version = _REPORTVIEW_PATCH_VERSION
	_export_query._jalali_orig = _orig
	mod._export_query = _export_query
	logger.debug("patched frappe.desk.reportview._export_query (v%s)", _REPORTVIEW_PATCH_VERSION)
