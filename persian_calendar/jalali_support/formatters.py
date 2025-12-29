# Copyright (c) 2024, Persian Calendar Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import formatdate as original_formatdate, format_datetime as original_format_datetime
from frappe.utils.formatters import format_value as original_format_value
from frappe.utils.data import getdate
import datetime
import re
import calendar

# Persian month names
JALALI_MONTH_NAMES = {
	1: "فروردین", 2: "اردیبهشت", 3: "خرداد",
	4: "تیر", 5: "مرداد", 6: "شهریور",
	7: "مهر", 8: "آبان", 9: "آذر",
	10: "دی", 11: "بهمن", 12: "اسفند"
}

# 3-letter abbreviations for Jalali months (similar to Gregorian: Jan, Feb, Mar, etc.)
JALALI_MONTH_NAMES_SHORT = {
	1: "فرو", 2: "ارد", 3: "خرد",
	4: "تیر", 5: "مرد", 6: "شهر",
	7: "مهر", 8: "آبا", 9: "آذر",
	10: "دی", 11: "بهم", 12: "اسف"
}

def format_jalali_date_with_format(jalali_date, format_string):
	"""Format Jalali date according to format_string"""
	if not format_string:
		return f"{jalali_date['jy']}-{jalali_date['jm']:02d}-{jalali_date['jd']:02d}"
	
	result = format_string
	
	# Replace year patterns
	if "YYYY" in result:
		result = result.replace("YYYY", str(jalali_date['jy']))
	elif "YY" in result:
		result = result.replace("YY", str(jalali_date['jy'])[-2:])
	
	# Replace month patterns
	if "MMMM" in result:
		result = result.replace("MMMM", JALALI_MONTH_NAMES.get(jalali_date['jm'], str(jalali_date['jm'])))
	elif "MMM" in result:
		result = result.replace("MMM", JALALI_MONTH_NAMES_SHORT.get(jalali_date['jm'], str(jalali_date['jm'])))
	elif "MM" in result:
		result = result.replace("MM", f"{jalali_date['jm']:02d}")
	elif "M" in result:
		result = result.replace("M", str(jalali_date['jm']))
	
	# Replace day patterns
	if "DD" in result:
		result = result.replace("DD", f"{jalali_date['jd']:02d}")
	elif "D" in result and "DD" not in result:
		# Only replace single D if DD is not in the string
		result = result.replace("D", str(jalali_date['jd']), 1)
	
	return result

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
		
		# If format_string is specified, format Jalali date according to format_string
		if format_string:
			result = format_jalali_date_with_format(jalali_date, format_string)
			print(f"Jalali formatdate with format: {string_date} -> {result} (format: {format_string})")
			return result
		else:
			# Default format: YYYY-MM-DD
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
	
	# Get fieldtype safely - handle dict, object, string, and None
	fieldtype = None
	if df is None:
		# No field definition provided, pass through to original formatter
		return original_format_value(value, df, doc, currency, translated, format)
	elif isinstance(df, str):
		# df is a string (field name), try to get field from doc's meta if available
		if doc:
			try:
				# Handle doc as object, dict, or string (docname)
				if isinstance(doc, str):
					# doc is a docname, need doctype - can't determine without more context
					# Pass through to original formatter
					return original_format_value(value, df, doc, currency, translated, format)
				elif isinstance(doc, dict):
					doctype = doc.get('doctype')
				else:
					doctype = getattr(doc, 'doctype', None)
				
				if doctype:
					meta = frappe.get_meta(doctype)
					field = meta.get_field(df)
					if field:
						fieldtype = field.fieldtype
			except Exception as e:
				# If anything fails, just pass through to original formatter
				pass
		# If we couldn't get fieldtype, pass through to original formatter
		if not fieldtype:
			return original_format_value(value, df, doc, currency, translated, format)
	elif isinstance(df, dict):
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

# Monkey patch get_period_list to convert labels to Jalali
def patch_get_period_list():
	"""Patch get_period_list to convert period labels to Jalali format"""
	try:
		from erpnext.accounts.report.financial_statements import get_period_list as original_get_period_list
		
		def get_period_list_jalali(*args, **kwargs):
			"""Wrapper for get_period_list that converts labels to Jalali"""
			period_list = original_get_period_list(*args, **kwargs)
			
			# Only convert if Jalali is enabled
			if not is_jalali_enabled():
				return period_list
			
			display_calendar = get_effective_display_calendar()
			if display_calendar == "Gregorian":
				return period_list
			
			# Convert labels to Jalali format
			for period in period_list:
				if period.get("label"):
					label = period.get("label")
					try:
						# First, try to use from_date if available (most accurate)
						if period.get("from_date"):
							from_date = getdate(period.get("from_date"))
							jalali_date = gregorian_to_jalali(from_date.year, from_date.month, from_date.day)
							jalali_label = f"{JALALI_MONTH_NAMES_SHORT.get(jalali_date['jm'], str(jalali_date['jm']))} {jalali_date['jy']}"
							period["label"] = jalali_label
							print(f"Converted period label using from_date: {label} -> {jalali_label}")
							continue
						
						# Fallback: Try to parse the label as a date and convert to Jalali
						# Labels are typically in "MMM YYYY" format (e.g., "Apr 2025")
						
						# Check if label contains month name (English)
						month_names = {
							"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
							"Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
							"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
							"July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
						}
						
						# Try to extract month and year from label
						month = None
						year = None
						
						# Pattern 1: "MMM YYYY" or "MMMM YYYY"
						for month_name, month_num in month_names.items():
							if month_name in label:
								month = month_num
								# Extract year (4 digits)
								year_match = re.search(r'\b(\d{4})\b', label)
								if year_match:
									year = int(year_match.group(1))
								break
						
						# Pattern 2: "YYYY-MM"
						if not month and not year:
							date_match = re.match(r'(\d{4})-(\d{1,2})', label)
							if date_match:
								year = int(date_match.group(1))
								month = int(date_match.group(2))
						
						# If we found month and year, convert to Jalali
						# Use middle of month (15th) for more accurate conversion
						# This ensures we get the correct Jalali month
						if month and year:
							# Use 15th day of month for conversion (middle of month)
							# This is more accurate than using 1st day
							try:
								gregorian_date = datetime.date(year, month, 15)
							except ValueError:
								# If 15th doesn't exist (e.g., Feb 30), use last day of month
								last_day = calendar.monthrange(year, month)[1]
								gregorian_date = datetime.date(year, month, last_day)
							
							jalali_date = gregorian_to_jalali(gregorian_date.year, gregorian_date.month, gregorian_date.day)
							
							# Format as "MMM YYYY" in Jalali
							jalali_label = f"{JALALI_MONTH_NAMES_SHORT.get(jalali_date['jm'], str(jalali_date['jm']))} {jalali_date['jy']}"
							period["label"] = jalali_label
							print(f"Converted period label: {label} -> {jalali_label}")
					except Exception as e:
						print(f"Error converting period label '{label}' to Jalali: {e}")
			
			return period_list
		
		# Apply the patch
		import erpnext.accounts.report.financial_statements
		erpnext.accounts.report.financial_statements.get_period_list = get_period_list_jalali
		print("get_period_list patched for Jalali support")
	except ImportError:
		# ERPNext might not be installed, skip patching
		pass
	except Exception as e:
		print(f"Error patching get_period_list: {e}")

# Override make_xlsx directly to convert datetime objects to Jalali strings
def make_xlsx_jalali(data, sheet_name, wb=None, column_widths=None):
    """Override make_xlsx to convert datetime objects to Jalali strings"""
    # Get the original make_xlsx function
    orig_make_xlsx = _get_original_make_xlsx()
    
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
        return orig_make_xlsx(converted_data, sheet_name, wb, column_widths)
    else:
        return orig_make_xlsx(data, sheet_name, wb, column_widths)

# Store original make_xlsx (lazy import to avoid errors if xlsxutils is not available)
original_make_xlsx = None

def _get_original_make_xlsx():
    """Get the original make_xlsx function, importing it if necessary"""
    global original_make_xlsx
    if original_make_xlsx is None:
        try:
            import frappe.utils.xlsxutils
            original_make_xlsx = frappe.utils.xlsxutils.make_xlsx
        except (ImportError, AttributeError) as e:
            # If xlsxutils is not available, use a fallback
            print(f"Warning: Could not import make_xlsx: {e}")
            # Return a dummy function that just passes through
            def dummy_make_xlsx(data, sheet_name, wb=None, column_widths=None):
                # Try to import and use the original if available
                try:
                    import frappe.utils.xlsxutils
                    return frappe.utils.xlsxutils.make_xlsx(data, sheet_name, wb, column_widths)
                except:
                    raise ImportError("make_xlsx is not available")
            original_make_xlsx = dummy_make_xlsx
    return original_make_xlsx

def setup_jalali_formatters():
    """Setup Jalali formatters on each request"""
    try:
        print("Setting up Jalali formatters on request...")
    except Exception as e:
        # If print fails (shouldn't happen, but just in case), log to frappe
        frappe.log_error(f"Error in setup_jalali_formatters print: {e}")
    
    # Apply make_xlsx patch only when needed
    try:
        import frappe.utils.xlsxutils
        if not hasattr(frappe.utils.xlsxutils, '_jalali_patched'):
            # Ensure we have the original function
            _get_original_make_xlsx()
            frappe.utils.xlsxutils.make_xlsx = make_xlsx_jalali
            frappe.utils.xlsxutils._jalali_patched = True
            print("make_xlsx patched for Jalali support")
    except Exception as e:
        print(f"Error patching make_xlsx: {e}")
    
    # Patch get_period_list for Jalali support
    try:
        if not hasattr(frappe, '_get_period_list_patched'):
            patch_get_period_list()
            frappe._get_period_list_patched = True
    except Exception as e:
        print(f"Error patching get_period_list: {e}")
    
    # Just ensure our overrides are active
    print(f"formatdate override: {frappe.utils.formatdate}")
    print(f"format_datetime override: {frappe.utils.format_datetime}")
    print(f"format_value override: {frappe.utils.formatters.format_value}")
