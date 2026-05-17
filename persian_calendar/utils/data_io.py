"""Data Import / Data Export Jalali conversion helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from persian_calendar.utils.jalali import gregorian_to_jalali_for_export, jalali_import_to_python


def coerce_gregorian_value_for_export(value: Any, fieldtype: str) -> Any:
	"""Normalize Date/Datetime cells (objects, ISO, or user format like dd-mm-yyyy) for conversion."""
	if value is None or value == "":
		return None
	if fieldtype not in ("Date", "Datetime"):
		return value

	try:
		import frappe
		from frappe.utils import get_datetime, getdate

		if isinstance(value, datetime):
			return value.replace(microsecond=0) if fieldtype == "Datetime" else value.date()
		if isinstance(value, date):
			return value

		if fieldtype == "Date":
			return getdate(value)
		return get_datetime(value)
	except Exception:
		return value


def convert_export_value(value: Any, fieldtype: str | None, enabled: bool) -> Any:
	if not enabled or not fieldtype or value in (None, ""):
		return value
	if fieldtype not in ("Date", "Datetime"):
		return value
	try:
		coerced = coerce_gregorian_value_for_export(value, fieldtype)
		out = gregorian_to_jalali_for_export(coerced, fieldtype)
		return out if out not in (None, "") else value
	except Exception:
		return value


def convert_import_value(value: Any, fieldtype: str | None, enabled: bool) -> Any:
	"""Return Python date/datetime when conversion applies, else original value."""
	if not enabled or not fieldtype or value in (None, ""):
		return value
	if fieldtype not in ("Date", "Datetime"):
		return value
	try:
		parsed = jalali_import_to_python(value, fieldtype)
		return parsed if parsed is not None else value
	except Exception:
		return value
