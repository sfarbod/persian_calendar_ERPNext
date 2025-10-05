#import frappe
#from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings

# persian_calendar/persian_calendar/jalali_support/api.py

import frappe
from persian_calendar.jalali_support.utils.date_utils import g_to_j
from frappe.utils import getdate

@frappe.whitelist(allow_guest=True)
def convert_to_jalali(date_str: str) -> dict:
    """
    تبدیل تاریخ میلادی (YYYY-MM-DD) به تاریخ شمسی.
    اگر date_str خالی باشد یا اشتباه، مقدار {"jalali": None} برگرداند.
    """
    if not date_str:
        return {"jalali": None}
    try:
        # ابتدا رشته را به یک شیء تاریخ پایتونی تبدیل کن
        gdate = getdate(date_str)
        if not gdate:
            return {"jalali": None}
        # تبدیل به شمسی
        jdate = g_to_j(gdate)
        # ساخت رشته خروجی
        jalali_str = f"{jdate.year}-{str(jdate.month).zfill(2)}-{str(jdate.day).zfill(2)}"
        return {"jalali": jalali_str}
    except Exception as e:
        frappe.log_error(f"convert_to_jalali error: {e}", "jalali_support")
        return {"jalali": None}

@frappe.whitelist(allow_guest=False)
def get_effective_calendar(user: str = None) -> str:
    """
    تقویم مؤثر (Jalali یا Gregorian) بر اساس تنظیمات ماژول.
    """
    from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
    settings = JalaliSettings.get_settings()
    if not settings.enabled:
        return "Gregorian"
    return settings.default_calendar or "Jalali"

@frappe.whitelist(allow_guest=False)
def is_jalali_enabled() -> bool:
    from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
    settings = JalaliSettings.get_settings()
    return settings.enabled

@frappe.whitelist(allow_guest=False)
def get_week_bounds() -> dict:
    from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
    settings = JalaliSettings.get_settings()
    return {"week_start": settings.week_start, "week_end": settings.week_end}
