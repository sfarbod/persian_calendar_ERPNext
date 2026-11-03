# Copyright (c) 2026, Persian Calendar contributors
# License: MIT

"""Jalali date conversion for Frappe Query Report / Report View export.

Patched upstream surfaces (Frappe ≥16.52):

* ``frappe.desk.query_report._export_query`` — Query Report / Script Report CSV & Excel
* ``frappe.desk.query_report.format_fields`` — skipped for Date/Datetime when Jalali ON
* ``frappe.desk.reportview._export_query`` — Report View / Report Builder export

Conversion is **export-only**: report ``run()`` results used for desk display are not
shared with the converted export rows (rows are shallow-copied before mutation).

Column detection (v2.1.2):

1. Explicit ``Date`` / ``Datetime`` metadata.
2. Python ``date`` / ``datetime`` objects (unless fieldtype is a non-date type).
3. Strict ISO date/datetime strings (optional fraction + timezone) for Date/Datetime
   columns, or for incomplete metadata on date-like fieldnames.
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
# v3: Datetime/ISO-with-tz + incomplete metadata date columns.
_QUERY_REPORT_PATCH_VERSION = 3
_REPORTVIEW_PATCH_VERSION = 3

# Never treat these fieldtypes as convertible date columns.
_NON_DATE_FIELDTYPES = frozenset(
	{
		"Time",
		"Duration",
		"Int",
		"Float",
		"Currency",
		"Percent",
		"Check",
		"Link",
		"Dynamic Link",
		"Select",
		"Text",
		"Small Text",
		"Long Text",
		"Code",
		"HTML",
		"JSON",
		"Table",
		"Attach",
		"Attach Image",
		"Password",
		"Color",
		"Rating",
		"Geolocation",
	}
)

# Strict ISO date/datetime (optional fractional seconds + Z/±HH:MM offset).
# Rejects ambiguous locale forms such as 10.04.2026 or 06/09/2026.
_ISO_DATE_RE = re.compile(
	r"^(\d{4})-(\d{1,2})-(\d{1,2})"
	r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.(\d+))?"
	r"(?:Z|[+-]\d{2}:?\d{2})?)?$"
)

_TIME_ONLY_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?$")

# Fieldnames that reliably denote date/datetime columns when metadata is incomplete.
# Intentionally excludes Time-only names (posting_time, etc.).
_DATE_FIELDNAME_RE = re.compile(
	r"^(date|datetime|timestamp)$|(_date|_datetime)$|^(posting_date|transaction_date|due_date|from_date|to_date|schedule_date|creation|modified)$",
	re.IGNORECASE,
)


def apply_report_export_patches() -> None:
	"""Idempotent install of report-export Jalali adapters."""
	global _patches_applied
	_patch_query_report_export()
	_patch_reportview_export()
	_patches_applied = True


def _normalize_iso_text(value: str) -> str:
	text = value.strip()
	if "T" in text and " " not in text.split("T", 1)[0]:
		text = text.replace("T", " ", 1)
	return text


def is_report_export_date_value(value: Any) -> bool:
	"""True when *value* is a date/datetime object or a strict ISO date/datetime string."""
	if value is None or value == "":
		return False
	if isinstance(value, datetime):
		return True
	# Pure date (not datetime subclass check already done).
	if isinstance(value, date) and not isinstance(value, datetime):
		return True
	if isinstance(value, str):
		text = _normalize_iso_text(value)
		# Strip fractional seconds for matching after capturing via regex — full match below.
		return bool(_ISO_DATE_RE.match(text))
	return False


def is_time_only_value(value: Any) -> bool:
	"""True for time-only values that must never be Jalali-converted."""
	if value is None or value == "":
		return False
	try:
		from datetime import time as dt_time
		from datetime import timedelta

		if isinstance(value, (dt_time, timedelta)):
			return True
	except Exception:
		pass
	if isinstance(value, str) and _TIME_ONLY_RE.match(value.strip()):
		return True
	return False


def _iso_has_time(text: str) -> bool:
	m = _ISO_DATE_RE.match(_normalize_iso_text(text))
	return bool(m and m.group(4) is not None)


def _strip_timezone_for_parse(text: str) -> str:
	"""Keep wall-clock components; drop Z / ±HH:MM so shared helpers can parse."""
	t = _normalize_iso_text(text)
	if t.endswith("Z") or t.endswith("z"):
		t = t[:-1]
	t = re.sub(r"[+-]\d{2}:?\d{2}$", "", t)
	# Normalize fractional seconds for get_datetime / toshamshi
	t = re.sub(r"(\d{1,2}:\d{2}:\d{2})\.\d+", r"\1", t)
	return t.strip()


def resolve_report_export_fieldtype(
	fieldtype: str | None,
	value: Any,
	*,
	fieldname: str | None = None,
) -> str | None:
	"""Resolve effective Date/Datetime type for a report cell.

	Priority:
	1. Explicit Date / Datetime metadata.
	2. Python date / datetime objects (when column is not a non-date fieldtype).
	3. Strict ISO strings when fieldtype is Date/Datetime, or when metadata is
	   incomplete (None / Data) and *fieldname* is a reliable date indicator.
	"""
	if is_time_only_value(value):
		return None

	ft = (fieldtype or "").strip() if isinstance(fieldtype, str) else fieldtype
	if ft in _NON_DATE_FIELDTYPES:
		return None

	if ft in ("Date", "Datetime"):
		# Prefer Datetime when the value clearly carries a time component.
		if ft == "Date" and isinstance(value, datetime):
			return "Datetime"
		if ft == "Date" and isinstance(value, str) and _iso_has_time(value):
			return "Datetime"
		return ft

	# Incomplete metadata: trust Python temporal objects.
	if not ft or ft == "Data":
		if isinstance(value, datetime):
			return "Datetime"
		if isinstance(value, date):
			return "Date"
		# ISO strings only when fieldname semantics establish a date column.
		if isinstance(value, str) and fieldname and _DATE_FIELDNAME_RE.search(str(fieldname)):
			if is_report_export_date_value(value):
				return "Datetime" if _iso_has_time(value) else "Date"

	return None


def convert_report_export_value(
	value: Any,
	fieldtype: str | None,
	enabled: bool,
	*,
	fieldname: str | None = None,
) -> Any:
	"""Convert a report cell for Jalali export without touching ambiguous strings."""
	if not enabled or value in (None, ""):
		return value
	if is_time_only_value(value):
		return value

	effective = resolve_report_export_fieldtype(fieldtype, value, fieldname=fieldname)
	if not effective:
		return value

	include_time = effective == "Datetime"

	if isinstance(value, str):
		if not is_report_export_date_value(value):
			# Ambiguous / locale-formatted / non-ISO — leave unchanged.
			return value
		from persian_calendar.utils.jalali import is_likely_jalali_date, toshamshi

		normalized = _strip_timezone_for_parse(value)
		if is_likely_jalali_date(normalized):
			return toshamshi(normalized, include_time=include_time)
		# convert_export_value → toshamshi; pass normalized wall-clock string.
		return convert_export_value(normalized, effective, True)

	if isinstance(value, datetime):
		# Use naive wall-clock components (preserve displayed local time).
		naive = value.replace(tzinfo=None, microsecond=0) if value.tzinfo or value.microsecond else value
		return convert_export_value(naive, effective, True)

	if isinstance(value, date):
		return convert_export_value(value, effective, True)

	return convert_export_value(value, effective, True)


def _convertible_column_indexes(columns: list) -> list[tuple[int, str, str | None]]:
	"""Return (index, fieldname, declared_fieldtype) for potentially convertible columns.

	Includes explicit Date/Datetime columns and incomplete metadata (None/Data)
	with date-like fieldnames. Final per-cell gating uses resolve_report_export_fieldtype.
	"""
	out: list[tuple[int, str, str | None]] = []
	for i, col in enumerate(columns or []):
		if not isinstance(col, dict):
			continue
		ft = col.get("fieldtype")
		fname = col.get("fieldname") or col.get("field") or i
		if ft in ("Date", "Datetime"):
			out.append((i, fname, ft))
			continue
		if (not ft or ft == "Data") and fname and _DATE_FIELDNAME_RE.search(str(fname)):
			out.append((i, fname, ft))
	return out


def convert_query_report_result(data: frappe._dict, enabled: bool) -> frappe._dict:
	"""Return a copy of *data* with Date/Datetime cells converted when *enabled*.

	Does not mutate the original ``data.result`` list or its row objects.
	When enabled, converted columns' fieldtypes are set to ``Data`` on the copy
	so stock ``format_fields`` will not re-apply ``formatdate`` / ``format_datetime``.
	"""
	if not enabled or not data:
		return data

	columns = data.get("columns") or []
	date_cols = _convertible_column_indexes(columns)
	if not date_cols:
		# Still scan for explicit Date/Datetime only via declared types — nothing to do.
		return data

	# Copy container + columns so we can retarget fieldtypes without touching cache.
	out = frappe._dict(data)
	out.columns = [dict(c) if isinstance(c, dict) else c for c in columns]
	date_cols = _convertible_column_indexes(out.columns)

	converted_col_indexes: set[int] = set()
	new_result = []
	for row in data.get("result") or []:
		if isinstance(row, dict):
			new_row = dict(row)
			for i, fname, ft in date_cols:
				if fname not in new_row:
					continue
				before = new_row[fname]
				after = convert_report_export_value(before, ft, True, fieldname=str(fname))
				if after != before:
					converted_col_indexes.add(i)
				new_row[fname] = after
			new_result.append(new_row)
		elif isinstance(row, (list, tuple)):
			new_row = list(row)
			for i, fname, ft in date_cols:
				if i >= len(new_row):
					continue
				before = new_row[i]
				after = convert_report_export_value(before, ft, True, fieldname=str(fname))
				if after != before:
					converted_col_indexes.add(i)
				new_row[i] = after
			new_result.append(new_row)
		else:
			new_result.append(row)

	out.result = new_result

	# Prevent stock format_fields from reformatting converted (or Date/Datetime) columns.
	for i, _fname, ft in date_cols:
		col = out.columns[i]
		if not isinstance(col, dict):
			continue
		if ft in ("Date", "Datetime") or i in converted_col_indexes:
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

	date_offsets: list[tuple[int, str | None, str | None]] = []
	for i, info in enumerate(fields_info):
		info = info or {}
		ft = info.get("fieldtype")
		fname = info.get("fieldname")
		if ft in ("Date", "Datetime") or (
			(not ft or ft == "Data") and fname and _DATE_FIELDNAME_RE.search(str(fname))
		):
			# data columns: 0 = Sr, 1.. = fields_info[0..]
			date_offsets.append((i + 1, ft, fname))

	if not date_offsets:
		return data

	out = [data[0]]
	for row in data[1:]:
		if not isinstance(row, (list, tuple)):
			out.append(row)
			continue
		new_row = list(row)
		for col_idx, ft, fname in date_offsets:
			if col_idx < len(new_row):
				new_row[col_idx] = convert_report_export_value(
					new_row[col_idx], ft, True, fieldname=str(fname) if fname else None
				)
		out.append(new_row)
	return out

def parse_export_dates_as_jalali(raw: Any, *, default: int = 1) -> int:
	"""Parse export_dates_as_jalali from request/form values.

	* Missing / empty → *default* (Jalali ON for report export).
	* Explicit false-y: ``0``, ``False``, ``"0"``, ``"false"``, ``"no"``, ``"off"`` → 0.
	* Explicit true-y: ``1``, ``True``, ``"1"``, ``"true"``, ``"yes"``, ``"on"`` → 1.

	An explicit OFF is never treated as missing.
	"""
	if raw is None or raw == "":
		return 1 if default else 0
	if isinstance(raw, bool):
		return 1 if raw else 0
	if isinstance(raw, (int, float)):
		return 1 if int(raw) else 0
	s = str(raw).strip().lower()
	if s in ("0", "false", "no", "off"):
		return 0
	if s in ("1", "true", "yes", "on"):
		return 1
	return 1 if cint(raw) else 0


def _read_jalali_flag(form_params) -> int:
	"""Return 1 (Jalali) by default for report export when the flag is absent."""
	raw = None
	present = False
	if form_params is not None:
		if isinstance(form_params, dict):
			if "export_dates_as_jalali" in form_params:
				raw = form_params.get("export_dates_as_jalali")
				present = True
		elif hasattr(form_params, "export_dates_as_jalali"):
			# frappe._dict may expose missing keys as None via getattr; prefer key check.
			if isinstance(form_params, frappe._dict) and "export_dates_as_jalali" in form_params:
				raw = form_params.get("export_dates_as_jalali")
				present = True
			elif not isinstance(form_params, frappe._dict):
				raw = getattr(form_params, "export_dates_as_jalali", None)
				present = True

	if not present and hasattr(frappe.local, "form_dict") and frappe.local.form_dict is not None:
		fd = frappe.local.form_dict
		if "export_dates_as_jalali" in fd:
			raw = fd.get("export_dates_as_jalali")
			present = True

	if not present:
		return parse_export_dates_as_jalali(None, default=1)
	return parse_export_dates_as_jalali(raw, default=1)


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
