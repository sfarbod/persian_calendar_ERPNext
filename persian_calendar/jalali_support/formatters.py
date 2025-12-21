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
	
	# Check effective display calendar
	display_calendar = get_effective_display_calendar()
	if display_calendar == "Gregorian":
		return original_formatdate(string_date, format_string, parse_day_first)
	
	if not string_date:
		return ""
	
	try:
		# Convert Gregorian to Jalali
		date_obj = getdate(string_date)
		jalali_date = gregorian_to_jalali(date_obj.year, date_obj.month, date_obj.day)
		result = f"{jalali_date['jy']}-{jalali_date['jm']:02d}-{jalali_date['jd']:02d}"
		print(f"Jalali formatdate: {string_date} -> {result}")
		return result
	except Exception as e:
		print(f"Error in formatdate: {e}")
		return original_formatdate(string_date, format_string, parse_day_first)

def format_datetime(dt=None, format_string=None, parse_day_first=False):
	"""Override format_datetime to show Jalali dates when Jalali calendar is enabled"""
	if not is_jalali_enabled():
		return original_format_datetime(dt, format_string, parse_day_first)
	
	# Check effective display calendar
	display_calendar = get_effective_display_calendar()
	if display_calendar == "Gregorian":
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
		
		result = f"{jalali_str} {time_part}" if time_part else jalali_str
		print(f"Jalali format_datetime: {dt} -> {result}")
		return result
	except Exception as e:
		print(f"Error in format_datetime: {e}")
		return original_format_datetime(dt, format_string, parse_day_first)

def format_value(value, df=None, doc=None, currency=None, translated=False, format=None):
	"""Override format_value to show Jalali dates when Jalali calendar is enabled"""
	if not is_jalali_enabled():
		return original_format_value(value, df, doc, currency, translated, format)
	
	# Check effective display calendar
	display_calendar = get_effective_display_calendar()
	if display_calendar == "Gregorian":
		return original_format_value(value, df, doc, currency, translated, format)
	
	# Get fieldtype safely - handle both dict and object
	fieldtype = None
	if isinstance(df, dict):
		fieldtype = df.get("fieldtype")
	else:
		fieldtype = getattr(df, "fieldtype", None)
	
	if fieldtype in ("Date", "Datetime"):
		if fieldtype == "Date":
			return formatdate(value)
		elif fieldtype == "Datetime":
			return format_datetime(value)
	
	return original_format_value(value, df, doc, currency, translated, format)

def is_jalali_enabled():
	"""Check if Jalali calendar is enabled"""
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
		settings = JalaliSettings.get_settings()
		return settings.enabled
	except:
		return False

def get_effective_display_calendar():
	"""Get the effective display calendar based on 4-field logic for current user"""
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
		# Always get effective calendar for current session user
		# get_effective_calendar() without user parameter will use frappe.session.user
		effective = JalaliSettings.get_effective_calendar(user=None)  # None means use session user
		return effective.get("display_calendar", "Jalali")
	except Exception as e:
		print(f"Error in get_effective_display_calendar: {e}")
		return "Jalali"

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

# Override make_xlsx directly to convert datetime objects to Jalali strings
def make_xlsx_jalali(data, sheet_name, wb=None, column_widths=None):
    """Override make_xlsx to convert datetime objects to Jalali strings"""
    if is_jalali_enabled():
        print(f"Converting {len(data)} rows to Jalali format...")
        # Convert datetime objects to Jalali strings
        converted_data = []
        for row_idx, row in enumerate(data):
            converted_row = []
            for col_idx, item in enumerate(row):
                if isinstance(item, datetime.datetime):
                    jalali_str = format_datetime(item)
                    print(f"Row {row_idx}, Col {col_idx}: {item} -> {jalali_str}")
                    converted_row.append(jalali_str)
                elif isinstance(item, datetime.date):
                    jalali_str = formatdate(item)
                    print(f"Row {row_idx}, Col {col_idx}: {item} -> {jalali_str}")
                    converted_row.append(jalali_str)
                else:
                    converted_row.append(item)
            converted_data.append(converted_row)
        return original_make_xlsx(converted_data, sheet_name, wb, column_widths)
    else:
        return original_make_xlsx(data, sheet_name, wb, column_widths)

# Store original make_xlsx
import frappe.utils.xlsxutils
original_make_xlsx = frappe.utils.xlsxutils.make_xlsx

def setup_jalali_formatters():
    """Setup Jalali formatters on each request"""
    print("Setting up Jalali formatters on request...")
    
    # Apply make_xlsx patch only when needed
    try:
        if not hasattr(frappe.utils.xlsxutils, '_jalali_patched'):
            frappe.utils.xlsxutils.make_xlsx = make_xlsx_jalali
            frappe.utils.xlsxutils._jalali_patched = True
            print("make_xlsx patched for Jalali support")
    except Exception as e:
        print(f"Error patching make_xlsx: {e}")
    
    # Just ensure our overrides are active
    print(f"formatdate override: {frappe.utils.formatdate}")
    print(f"format_datetime override: {frappe.utils.format_datetime}")
    print(f"format_value override: {frappe.utils.formatters.format_value}")
