"""Jalali/Shamsi display helpers for Jinja print formats."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

try:
	import jdatetime
except ImportError:  # pragma: no cover
	jdatetime = None  # type: ignore

_PERSIAN_DIGIT_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

_MICROSECOND_RE = re.compile(r"(\d{1,2}:\d{2}:\d{2})\.\d+")
_DATETIME_RE = re.compile(
	r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)


def to_persian_digits(value: Any) -> str:
	"""Convert ASCII digits in *value* to Persian (۰–۹)."""
	if value is None or value == "":
		return ""
	return str(value).translate(_PERSIAN_DIGIT_MAP)


def _strip_microseconds(text: str) -> str:
	s = text.strip().replace("T", " ")
	return _MICROSECOND_RE.sub(r"\1", s)


def _is_likely_jalali_year(year: int) -> bool:
	return 1200 <= year <= 1600


def _is_likely_gregorian_year(year: int) -> bool:
	return year >= 1700


def _format_jalali_parts(
	jy: int,
	jm: int,
	jd: int,
	h: int = 0,
	mi: int = 0,
	s: int = 0,
	*,
	include_time: bool = False,
	fmt: str = "YYYY-MM-DD",
) -> str:
	out = (
		fmt.replace("YYYY", f"{jy:04d}")
		.replace("MM", f"{jm:02d}")
		.replace("DD", f"{jd:02d}")
	)
	if include_time:
		if "HH" in out or "mm" in out or "ss" in out:
			out = (
				out.replace("HH", f"{h:02d}")
				.replace("mm", f"{mi:02d}")
				.replace("ss", f"{s:02d}")
			)
		else:
			out = f"{out} {h:02d}:{mi:02d}:{s:02d}"
	return out


def _parse_to_parts(value: Any) -> tuple[int, int, int, int, int, int, bool] | None:
	"""Return (y, m, d, h, mi, s, is_jalali) or None if empty."""
	if value is None or value == "":
		return None

	if isinstance(value, datetime):
		return (
			value.year,
			value.month,
			value.day,
			value.hour,
			value.minute,
			value.second,
			False,
		)
	if isinstance(value, date):
		return (value.year, value.month, value.day, 0, 0, 0, False)

	text = _strip_microseconds(str(value))
	m = _DATETIME_RE.match(text)
	if not m:
		return None

	y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
	h = int(m.group(4)) if m.group(4) is not None else 0
	mi = int(m.group(5)) if m.group(5) is not None else 0
	s = int(m.group(6)) if m.group(6) is not None else 0
	is_jalali = _is_likely_jalali_year(y)
	if not is_jalali and not _is_likely_gregorian_year(y):
		# Unknown era — treat as Gregorian only if plausible month/day
		is_jalali = False
	return (y, mo, d, h, mi, s, is_jalali)


def toshamshi(
	value: Any,
	include_time: bool = False,
	format: str = "YYYY-MM-DD",
	persian_digits: bool = False,
) -> str:
	"""
	Convert a Gregorian date/datetime (or pass through Jalali) for print display.

	:param value: date, datetime, or ISO-like string (Gregorian or Jalali).
	:param include_time: Append time when the source has a time component.
	:param format: Output template (YYYY, MM, DD, optional HH, mm, ss).
	:param persian_digits: Use ۰–۹ instead of 0–9.
	"""
	if jdatetime is None:
		raise ImportError("jdatetime is required for toshamshi(); install persian_calendar dependencies.")

	parts = _parse_to_parts(value)
	if parts is None:
		return ""

	y, mo, d, h, mi, s, is_jalali = parts
	has_time = include_time and (h or mi or s or isinstance(value, datetime))

	if is_jalali:
		jy, jm, jd = y, mo, d
	else:
		if isinstance(value, datetime):
			jdt = jdatetime.datetime.fromgregorian(
				year=y, month=mo, day=d, hour=h, minute=mi, second=s
			)
		else:
			jd_date = jdatetime.date.fromgregorian(year=y, month=mo, day=d)
			if has_time:
				jdt = jdatetime.datetime(
					jd_date.year,
					jd_date.month,
					jd_date.day,
					h,
					mi,
					s,
				)
			else:
				jy, jm, jd = jd_date.year, jd_date.month, jd_date.day
				out = _format_jalali_parts(
					jy, jm, jd, h, mi, s, include_time=False, fmt=format
				)
				return to_persian_digits(out) if persian_digits else out

		jy, jm, jd = jdt.year, jdt.month, jdt.day
		h, mi, s = jdt.hour, jdt.minute, jdt.second

	out = _format_jalali_parts(
		jy, jm, jd, h, mi, s, include_time=bool(has_time), fmt=format
	)
	return to_persian_digits(out) if persian_digits else out


def strip_microseconds(value: Any) -> Any:
	if value is None or value == "":
		return value
	return _strip_microseconds(str(value))


def is_likely_jalali_date(value: Any) -> bool:
	parts = _parse_to_parts(value)
	return bool(parts and parts[6])


def is_likely_gregorian_date(value: Any) -> bool:
	parts = _parse_to_parts(value)
	return bool(parts and not parts[6] and _is_likely_gregorian_year(parts[0]))


def coerce_gregorian_datetime(value: Any) -> str | None:
	"""Parse Jalali/ISO/US-style datetime strings to storage ``YYYY-MM-DD HH:mm:ss`` (or date-only)."""
	if value is None or value == "":
		return None

	g = jalali_to_gregorian_datetime(value)
	if g:
		return g

	try:
		from frappe.utils import get_datetime, getdate

		if isinstance(value, str) and " " not in _strip_microseconds(value):
			d = getdate(value)
			return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
		dt = get_datetime(value)
		if isinstance(dt, datetime):
			return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
	except Exception:
		pass
	return None


def jalali_to_gregorian_datetime(value: Any) -> str | None:
	"""Convert Jalali (or normalize Gregorian) to ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:mm:ss``."""
	if jdatetime is None:
		return None
	if value is None or value == "":
		return None

	parts = _parse_to_parts(value)
	if not parts:
		return None

	y, mo, d, h, mi, s, is_jalali = parts
	has_time = h or mi or s or (
		isinstance(value, str) and " " in _strip_microseconds(str(value))
	)

	if is_jalali:
		gdate = jdatetime.date(y, mo, d).togregorian()
		base = f"{gdate.year:04d}-{gdate.month:02d}-{gdate.day:02d}"
		if has_time:
			return f"{base} {h:02d}:{mi:02d}:{s:02d}"
		return base

	if _is_likely_gregorian_year(y):
		base = f"{y:04d}-{mo:02d}-{d:02d}"
		if has_time:
			return f"{base} {h:02d}:{mi:02d}:{s:02d}"
		return base

	return None


def gregorian_to_jalali_for_export(value: Any, fieldtype: str) -> Any:
	if fieldtype == "Date":
		return toshamshi(value, include_time=False)
	if fieldtype == "Datetime":
		return toshamshi(value, include_time=True)
	return value


def jalali_import_to_python(value: Any, fieldtype: str):
	"""Parse import cell to Python date/datetime (Gregorian storage)."""
	from frappe.utils import get_datetime, getdate

	g = coerce_gregorian_datetime(value) or jalali_to_gregorian_datetime(value)
	if not g:
		return None
	if fieldtype == "Date":
		return getdate(g)
	if fieldtype == "Datetime":
		return get_datetime(g)
	return None
