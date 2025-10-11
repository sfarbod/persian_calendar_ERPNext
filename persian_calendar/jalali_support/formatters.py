# Copyright (c) 2024, Persian Calendar Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import formatdate as original_formatdate, format_datetime as original_format_datetime
from frappe.utils.formatters import format_value as original_format_value
from frappe.utils.data import getdate
import datetime

def formatdate(string_date=None, format_string=None, parse_day_first=False):
	"""Override formatdate to show Jalali dates when Jalali calendar is enabled"""
	if not is_jalali_enabled():
		return original_formatdate(string_date, format_string, parse_day_first)
	
	if not string_date:
		return ""
	
	try:
		# Convert Gregorian to Jalali
		date_obj = getdate(string_date)
		jalali_date = gregorian_to_jalali(date_obj.year, date_obj.month, date_obj.day)
		return f"{jalali_date['jy']}-{jalali_date['jm']:02d}-{jalali_date['jd']:02d}"
	except:
		return original_formatdate(string_date, format_string, parse_day_first)

def format_datetime(dt=None, format_string=None, parse_day_first=False):
	"""Override format_datetime to show Jalali dates when Jalali calendar is enabled"""
	if not is_jalali_enabled():
		return original_format_datetime(dt, format_string, parse_day_first)
	
	if not dt:
		return ""
	
	try:
		# Handle both string and datetime objects
		if isinstance(dt, str):
			date_obj = datetime.datetime.strptime(dt.split()[0], '%Y-%m-%d').date()
			time_part = dt.split()[1] if len(dt.split()) > 1 else ""
		else:
			date_obj = dt.date() if hasattr(dt, 'date') else dt
			time_part = dt.time().strftime('%H:%M:%S') if hasattr(dt, 'time') else ""
		
		jalali_date = gregorian_to_jalali(date_obj.year, date_obj.month, date_obj.day)
		jalali_str = f"{jalali_date['jy']}-{jalali_date['jm']:02d}-{jalali_date['jd']:02d}"
		
		if time_part:
			return f"{jalali_str} {time_part}"
		return jalali_str
	except:
		return original_format_datetime(dt, format_string, parse_day_first)

def format_value(value, df=None, doc=None, currency=None, translated=False, format=None):
	"""Override format_value to show Jalali dates when Jalali calendar is enabled"""
	if not is_jalali_enabled():
		return original_format_value(value, df, doc, currency, translated, format)
	
	if df and df.get("fieldtype") in ("Date", "Datetime"):
		if df.get("fieldtype") == "Date":
			return formatdate(value)
		elif df.get("fieldtype") == "Datetime":
			return format_datetime(value)
	
	return original_format_value(value, df, doc, currency, translated, format)

def is_jalali_enabled():
	"""Check if Jalali calendar is enabled"""
	try:
		return frappe.db.get_single_value("Jalali Settings", "enable_jalali") or False
	except:
		return False

def gregorian_to_jalali(gy, gm, gd):
	"""Convert Gregorian date to Jalali date"""
	# Import jdatetime for accurate conversion
	try:
		import jdatetime
		gregorian_date = datetime.date(gy, gm, gd)
		jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
		return {
			'jy': jalali_date.year,
			'jm': jalali_date.month,
			'jd': jalali_date.day
		}
	except ImportError:
		# Fallback to simple approximation if jdatetime is not available
		# This is a simplified conversion - not 100% accurate
		jalali_year = gy - 621
		if gm <= 3:
			jalali_year -= 1
		
		# Simple month approximation
		if gm <= 3:
			jalali_month = gm + 9
		else:
			jalali_month = gm - 3
		
		# Simple day approximation
		jalali_day = gd
		if gd > 20:
			jalali_day -= 20
		elif gd < 10:
			jalali_day += 10
		
		return {
			'jy': jalali_year,
			'jm': jalali_month,
			'jd': jalali_day
		}

# Monkey patch the original functions
frappe.utils.formatdate = formatdate
frappe.utils.format_datetime = format_datetime
frappe.utils.formatters.format_value = format_value

# No additional patching needed - the formatdate and format_datetime overrides should be sufficient
