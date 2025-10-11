# Copyright (c) 2025, Farbod Siyahpoosh and contributors
# For license information, please see license.txt



import frappe
from frappe.model.document import Document

class JalaliSettings(Document):

    def validate(self):
        """
        اعتبارسنجی هنگام ذخیره.
        """
        # اگر week_start و week_end تعریف شده باشند
        if self.week_start is not None and self.week_end is not None:
            if self.week_start == self.week_end:
                frappe.throw("Week Start و Week End نمی‌توانند برابر باشند.")
        # default_calendar معتبر باشه
        if self.default_calendar and self.default_calendar not in ("Jalali", "Gregorian"):
            frappe.throw("مقدار Default Calendar باید «Jalali» یا «Gregorian» باشد.")
        # user_calendar معتبر باشه
        if self.user_calendar and self.user_calendar not in ("System Default", "Jalali", "Gregorian"):
            frappe.throw("مقدار User Calendar باید «System Default»، «Jalali» یا «Gregorian» باشد.")

    def after_save(self):
        """
        بعد از ذخیره تنظیمات، صفحه را reload کن تا تغییرات اعمال شود.
        """
        # Check if this is a web request (not API call)
        if hasattr(frappe.local, 'request') and frappe.local.request:
            # For web requests, redirect to reload the page
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = frappe.local.request.url
        else:
            # For API calls, just show a message
            frappe.msgprint("تنظیمات تقویم جلالی ذخیره شد. لطفاً صفحه را refresh کنید تا تغییرات اعمال شود.")

    @staticmethod
    def get_settings():
        """
        برمی‌گرداند تنظیمات جاری به صورت دیکشن با کلیدهای: enabled, default_calendar, user_calendar, week_start, week_end
        """
        doc = frappe.get_single("Jalali Settings")

        enabled = True if doc.enable_jalali else False
        
        default_calendar = doc.default_calendar if doc.default_calendar in ("Jalali", "Gregorian") else "Jalali"
        user_calendar = doc.user_calendar if doc.user_calendar in ("System Default", "Jalali", "Gregorian") else "System Default"

        week_start = doc.week_start if (doc.week_start is not None) else 6
        week_end = doc.week_end if (doc.week_end is not None) else 5

        return frappe._dict(
            enabled = enabled,
            default_calendar = default_calendar,
            user_calendar = user_calendar,
            week_start = week_start,
            week_end = week_end
        )
    
    @staticmethod
    def get_effective_calendar():
        """
        محاسبه تقویم مؤثر بر اساس منطق 4 فیلد:
        1. enable_jalali = False → همه چیز میلادی
        2. user_calendar = "System Default" → از default_calendar پیروی می‌کند
        3. user_calendar = "Jalali" → همیشه شمسی
        4. user_calendar = "Gregorian" → همیشه میلادی
        """
        settings = JalaliSettings.get_settings()
        
        # مرحله 1: اگر enable_jalali = False باشد
        if not settings.enabled:
            return {
                "display_calendar": "Gregorian",
                "week_start": 0,  # یکشنبه
                "week_end": 6     # شنبه
            }
        
        # مرحله 2: تعیین تقویم نمایش بر اساس user_calendar
        if settings.user_calendar == "System Default":
            display_calendar = settings.default_calendar
        elif settings.user_calendar == "Jalali":
            display_calendar = "Jalali"
        elif settings.user_calendar == "Gregorian":
            display_calendar = "Gregorian"
        else:
            display_calendar = settings.default_calendar
        
        # مرحله 3: week_start فقط اگر enable_jalali = True باشد اعمال می‌شود
        return {
            "display_calendar": display_calendar,
            "week_start": settings.week_start,
            "week_end": settings.week_end
        }
