"""Resolve Company Business Calendar → CalendarProvider.

Never uses the current user's Display Calendar preference.
"""

from __future__ import annotations

BUSINESS_CALENDAR_GREGORIAN = "Gregorian"
BUSINESS_CALENDAR_JALALI = "Jalali"
VALID_BUSINESS_CALENDARS = frozenset({BUSINESS_CALENDAR_GREGORIAN, BUSINESS_CALENDAR_JALALI})

# Request-local cache: company name → calendar system string
_company_calendar_cache: dict[str, str] = {}


def clear_business_calendar_cache() -> None:
	"""Clear the in-process company → calendar cache (tests / after Company save)."""
	_company_calendar_cache.clear()


def normalize_business_calendar(value: str | None) -> str:
	"""Return a valid Business Calendar name; default Gregorian."""
	if not value:
		return BUSINESS_CALENDAR_GREGORIAN
	name = str(value).strip()
	if name not in VALID_BUSINESS_CALENDARS:
		return BUSINESS_CALENDAR_GREGORIAN
	return name


def get_business_calendar_for_company(company: str | None = None) -> str:
	"""Resolve Business Calendar for ``company``.

	Resolution order:
	1. Explicit ``company`` argument (Company.business_calendar)
	2. User default company (only when ``company`` is empty)
	3. Global Defaults default_company
	4. Gregorian safe fallback

	Does **not** consult User Display Calendar or Jalali Settings display defaults.
	"""
	import frappe

	if company:
		cached = _company_calendar_cache.get(company)
		if cached is not None:
			return cached
		value = _read_company_business_calendar(company)
		_company_calendar_cache[company] = value
		return value

	# No explicit company — try user default / global defaults
	fallback_company = None
	try:
		fallback_company = frappe.defaults.get_user_default("company")
	except Exception:
		fallback_company = None

	if not fallback_company:
		try:
			fallback_company = frappe.db.get_single_value("Global Defaults", "default_company")
		except Exception:
			fallback_company = None

	if fallback_company:
		return get_business_calendar_for_company(fallback_company)

	return BUSINESS_CALENDAR_GREGORIAN


def _read_company_business_calendar(company: str) -> str:
	import frappe

	try:
		value = frappe.db.get_value("Company", company, "business_calendar")
	except Exception:
		# Column may not exist yet during migrate
		return BUSINESS_CALENDAR_GREGORIAN

	return normalize_business_calendar(value)
