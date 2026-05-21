"""Normalize Date/Datetime model values to Gregorian storage before save."""

from __future__ import annotations

import re
from datetime import time, timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from persian_calendar.utils.jalali import coerce_gregorian_datetime

_BAD_DATETIME_RE = re.compile(r"invalid\s*date|nan", re.I)
_NUMERIC_GARBAGE_RE = re.compile(r"[^0-9.\-+eE,]")


def _is_jalali_enabled() -> bool:
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
			JalaliSettings,
		)

		return bool(JalaliSettings.get_settings().enabled)
	except Exception:
		return False


def _set_doc_value(doc: Document | frappe._dict, fieldname: str, value) -> None:
	setter = getattr(doc, "set", None)
	if callable(setter):
		setter(fieldname, value)
	else:
		doc[fieldname] = value


def _is_bad_datetime_value(value) -> bool:
	if value is None or value == "":
		return False
	return bool(_BAD_DATETIME_RE.search(str(value)))


def _sanitize_time_field(doc: Document | frappe._dict, fieldname: str) -> None:
	value = doc.get(fieldname)
	if value is None or value == "":
		return
	if isinstance(value, timedelta):
		total_seconds = int(value.total_seconds()) % 86400
		h, rem = divmod(total_seconds, 3600)
		m, s = divmod(rem, 60)
		_set_doc_value(doc, fieldname, f"{h:02d}:{m:02d}:{s:02d}")
		return
	if isinstance(value, time):
		_set_doc_value(doc, fieldname, f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}")
		return
	text = str(value).strip()
	if _is_bad_datetime_value(text):
		if doc.get("name"):
			restored = frappe.db.get_value(doc.doctype, doc.name, fieldname)
			if restored and not _is_bad_datetime_value(restored):
				_set_doc_value(doc, fieldname, restored)
				return
		_set_doc_value(doc, fieldname, "00:00:00")
		return
	from frappe.utils import get_time

	try:
		parsed = get_time(text)
		normalized = f"{parsed.hour:02d}:{parsed.minute:02d}:{parsed.second:02d}"
		if normalized != value:
			_set_doc_value(doc, fieldname, normalized)
	except Exception:
		if doc.get("name"):
			restored = frappe.db.get_value(doc.doctype, doc.name, fieldname)
			if restored and not _is_bad_datetime_value(restored):
				_set_doc_value(doc, fieldname, restored)
				return
		frappe.throw(
			frappe._("Could not parse {0}: {1}").format(fieldname, value),
			title=frappe._("Invalid Time"),
		)


def _coerce_field(
	doc: Document | frappe._dict, fieldname: str, fieldtype: str = "Datetime"
) -> None:
	value = doc.get(fieldname)
	if value is None or value == "":
		return
	if _is_bad_datetime_value(value):
		frappe.throw(
			frappe._("{0} has an invalid date/time value. Fix the field before saving.").format(
				fieldname
			),
			title=frappe._("Invalid Date"),
		)
	coerced = coerce_gregorian_datetime(value)
	if not coerced:
		frappe.throw(
			frappe._("Could not parse {0}: {1}").format(fieldname, value),
			title=frappe._("Invalid Date"),
		)
	if fieldtype == "Date":
		coerced = coerced[:10]
	if coerced != value:
		_set_doc_value(doc, fieldname, coerced)


def _sanitize_numeric_field(
	doc: Document | frappe._dict, fieldname: str, fieldtype: str
) -> None:
	value = doc.get(fieldname)
	if value is None or value == "":
		return
	if isinstance(value, (int, float)):
		return
	text = str(value).strip()
	if not text:
		return
	if _BAD_DATETIME_RE.search(text):
		_set_doc_value(doc, fieldname, 0)
		return
	cleaned = _NUMERIC_GARBAGE_RE.sub("", text)
	if not cleaned:
		_set_doc_value(doc, fieldname, 0)
		return
	# Thousand separators from CSV (e.g. 5,625.000000C -> 5625.0)
	if "," in cleaned and "." in cleaned:
		cleaned = cleaned.replace(",", "")
	elif "," in cleaned and "." not in cleaned:
		parts = cleaned.split(",")
		if len(parts) == 2 and len(parts[1]) == 3:
			cleaned = parts[0] + parts[1]
		else:
			cleaned = cleaned.replace(",", "")
	parsed = flt(cleaned)
	if fieldtype == "Int":
		parsed = int(parsed)
	_set_doc_value(doc, fieldname, parsed)


def normalize_doc_datetimes(doc: Document | frappe._dict, method: str | None = None) -> None:
	"""Coerce non-ISO datetime strings (e.g. M/D/YYYY H:mm from import) on validate.

	Runs for all sites with Persian Calendar installed, including Calendar Preference
	= Gregorian. Bulk CSV import still delivers US/EU display dates that must be
	coerced before MySQL storage.
	"""
	if not doc or not getattr(doc, "doctype", None):
		return

	meta = frappe.get_meta(doc.doctype)
	for df in meta.fields:
		if df.fieldtype == "Datetime":
			_coerce_field(doc, df.fieldname, "Datetime")
		elif df.fieldtype == "Date":
			_coerce_field(doc, df.fieldname, "Date")
		elif df.fieldtype == "Time":
			_sanitize_time_field(doc, df.fieldname)
		elif df.fieldtype == "Table":
			rows = doc.get(df.fieldname) or []
			if not rows:
				continue
			child_meta = frappe.get_meta(df.options)
			for row in rows:
				for child_df in child_meta.fields:
					if child_df.fieldtype in ("Datetime", "Date"):
						_coerce_field(row, child_df.fieldname, child_df.fieldtype)
					elif child_df.fieldtype == "Time":
						_sanitize_time_field(row, child_df.fieldname)
					elif child_df.fieldtype in ("Float", "Int", "Currency"):
						_sanitize_numeric_field(row, child_df.fieldname, child_df.fieldtype)
		elif df.fieldtype in ("Float", "Int", "Currency") and doc.get(df.fieldname) not in (
			None,
			"",
		):
			_sanitize_numeric_field(doc, df.fieldname, df.fieldtype)
