"""Normalize Date/Datetime model values to Gregorian storage before save."""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from persian_calendar.utils.jalali import coerce_gregorian_datetime


def _is_jalali_enabled() -> bool:
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
			JalaliSettings,
		)

		return bool(JalaliSettings.get_settings().enabled)
	except Exception:
		return False


def _coerce_field(
	doc: Document | frappe._dict, fieldname: str, fieldtype: str = "Datetime"
) -> None:
	value = doc.get(fieldname)
	if value is None or value == "":
		return
	coerced = coerce_gregorian_datetime(value)
	if not coerced:
		return
	if fieldtype == "Date":
		coerced = coerced[:10]
	if coerced != value:
		doc.set(fieldname, coerced)


def normalize_doc_datetimes(doc: Document | frappe._dict, method: str | None = None) -> None:
	"""Coerce non-ISO datetime strings (e.g. M/D/YYYY H:mm from import) on validate."""
	if not _is_jalali_enabled():
		return
	if not doc or not getattr(doc, "doctype", None):
		return

	meta = frappe.get_meta(doc.doctype)
	for df in meta.fields:
		if df.fieldtype == "Datetime":
			_coerce_field(doc, df.fieldname, "Datetime")
		elif df.fieldtype == "Date":
			_coerce_field(doc, df.fieldname, "Date")
		elif df.fieldtype == "Table":
			rows = doc.get(df.fieldname) or []
			if not rows:
				continue
			child_meta = frappe.get_meta(df.options)
			for row in rows:
				for child_df in child_meta.fields:
					if child_df.fieldtype in ("Datetime", "Date"):
						_coerce_field(row, child_df.fieldname, child_df.fieldtype)
