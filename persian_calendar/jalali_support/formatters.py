# Copyright (c) 2024, Persian Calendar Contributors
# License: MIT. See LICENSE
#
# Server-side: no global monkey-patching of frappe.utils.formatdate / format_datetime /
# format_value — exports, APIs, and Excel generation stay Gregorian/ISO. Jalali display is
# handled in the desk JS layer (jalali_support/formatters.js, persian_calendar.js).

import datetime
import calendar
import importlib
import re

import frappe
from frappe.utils.data import getdate

# Persian month names (used by ERPNext financial report period labels only)
JALALI_MONTH_NAMES_SHORT = {
	1: "فرو", 2: "ارد", 3: "خرد",
	4: "تیر", 5: "مرد", 6: "شهر",
	7: "مهر", 8: "آبا", 9: "آذر",
	10: "دی", 11: "بهم", 12: "اسف"
}


def is_jalali_enabled():
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
		settings = JalaliSettings.get_settings()
		return settings.enabled
	except Exception:
		return False


def get_effective_display_calendar():
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
		effective = JalaliSettings.get_effective_calendar(user=None)
		return effective.get("display_calendar", "Jalali")
	except Exception:
		return "Jalali"


def gregorian_to_jalali(gy, gm, gd):
	try:
		import jdatetime
		gregorian_date = datetime.date(gy, gm, gd)
		jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
		return {"jy": jalali_date.year, "jm": jalali_date.month, "jd": jalali_date.day}
	except ImportError:
		jalali_year = gy - 621
		if gm <= 3:
			jalali_year -= 1
		if gm <= 3:
			jalali_month = gm + 9
		else:
			jalali_month = gm - 3
		jalali_day = gd
		if gd > 20:
			jalali_day -= 20
		elif gd < 10:
			jalali_day += 10
		return {"jy": jalali_year, "jm": jalali_month, "jd": jalali_day}


def patch_get_period_list():
	"""Optional ERPNext: Jalali labels on financial statement period list (UI/report charts)."""
	try:
		from erpnext.accounts.report.financial_statements import get_period_list as original_get_period_list

		def get_period_list_jalali(*args, **kwargs):
			period_list = original_get_period_list(*args, **kwargs)
			if not is_jalali_enabled():
				return period_list
			if get_effective_display_calendar() == "Gregorian":
				return period_list

			for period in period_list:
				if not period.get("label"):
					continue
				label = period.get("label")
				try:
					if period.get("from_date"):
						from_date = getdate(period.get("from_date"))
						jalali_date = gregorian_to_jalali(from_date.year, from_date.month, from_date.day)
						jalali_label = f"{JALALI_MONTH_NAMES_SHORT.get(jalali_date['jm'], str(jalali_date['jm']))} {jalali_date['jy']}"
						period["label"] = jalali_label
						continue

					month_names = {
						"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
						"Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
						"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
						"July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
					}

					month = None
					year = None
					for month_name, month_num in month_names.items():
						if month_name in label:
							month = month_num
							year_match = re.search(r"\b(\d{4})\b", label)
							if year_match:
								year = int(year_match.group(1))
							break

					if not month and not year:
						date_match = re.match(r"(\d{4})-(\d{1,2})", label)
						if date_match:
							year = int(date_match.group(1))
							month = int(date_match.group(2))

					if month and year:
						try:
							gregorian_date = datetime.date(year, month, 15)
						except ValueError:
							last_day = calendar.monthrange(year, month)[1]
							gregorian_date = datetime.date(year, month, last_day)

						jalali_date = gregorian_to_jalali(gregorian_date.year, gregorian_date.month, gregorian_date.day)
						jalali_label = f"{JALALI_MONTH_NAMES_SHORT.get(jalali_date['jm'], str(jalali_date['jm']))} {jalali_date['jy']}"
						period["label"] = jalali_label
				except Exception:
					pass

			return period_list

		import erpnext.accounts.report.financial_statements
		erpnext.accounts.report.financial_statements.get_period_list = get_period_list_jalali
	except ImportError:
		pass
	except Exception:
		pass


def setup_jalali_formatters():
	"""Per-request: restore stock xlsxutils if an old worker still had make_xlsx patched; patch ERPNext period labels once."""
	try:
		import frappe.utils.xlsxutils as _xw
		if getattr(_xw, "_jalali_patched", False):
			importlib.reload(_xw)
	except Exception:
		pass

	try:
		if not getattr(frappe, "_get_period_list_patched", False):
			patch_get_period_list()
			frappe._get_period_list_patched = True
	except Exception:
		pass
