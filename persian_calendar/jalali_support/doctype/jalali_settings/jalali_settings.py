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

    def after_save(self):
        """
        Silently reload page after saving settings (no message displayed).
        """
        # Check if this is a web request (not API call)
        if hasattr(frappe.local, 'request') and frappe.local.request:
            # For web requests, redirect to reload the page silently
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = frappe.local.request.url
        # For API calls, do nothing (no message)

    @staticmethod
    def get_settings():
        """
        برمی‌گرداند تنظیمات جاری به صورت دیکشن با کلیدهای: enabled, default_calendar, week_start, week_end
        """
        doc = frappe.get_single("Jalali Settings")

        enabled = True if doc.enable_jalali else False
        
        default_calendar = doc.default_calendar if doc.default_calendar in ("Jalali", "Gregorian") else "Jalali"

        week_start = doc.week_start if (doc.week_start is not None) else 6
        week_end = doc.week_end if (doc.week_end is not None) else 5

        return frappe._dict(
            enabled = enabled,
            default_calendar = default_calendar,
            week_start = week_start,
            week_end = week_end
        )
    
    @staticmethod
    def get_effective_calendar(user=None):
        """
        محاسبه تقویم مؤثر بر اساس منطق 3 فیلد + User Settings:
        1. enable_jalali = False → همه چیز میلادی
        2. user_calendar_preference = "System Default" → از default_calendar پیروی می‌کند
        3. user_calendar_preference = "Jalali" → همیشه شمسی
        4. user_calendar_preference = "Gregorian" → همیشه میلادی
        """
        settings = JalaliSettings.get_settings()
        
        # مرحله 1: اگر enable_jalali = False باشد
        if not settings.enabled:
            return {
                "display_calendar": "Gregorian",
                "week_start": 0,  # یکشنبه
                "week_end": 6     # شنبه
            }
        
        # مرحله 2: دریافت تنظیمات کاربر از User Settings
        user_calendar_preference = "System Default"  # Default value
        
        # Determine which user to check
        target_user = user
        if not target_user:
            # If no user specified, use current session user
            if hasattr(frappe, 'session') and hasattr(frappe.session, 'user'):
                target_user = frappe.session.user
            elif hasattr(frappe.local, 'session'):
                target_user = getattr(frappe.local.session, 'user', None)
            else:
                target_user = None
        
        if target_user and target_user != "Guest":
            try:
                # Use get_value to avoid cache issues and get fresh data from DB
                user_calendar_preference = frappe.db.get_value("User", target_user, "calendar_preference") or "System Default"
            except Exception as e:
                # If user doesn't exist or error, use System Default
                frappe.log_error(f"Error getting user calendar preference for {target_user}: {e}", "JalaliSettings")
                user_calendar_preference = "System Default"
        
        # مرحله 3: تعیین تقویم نمایش بر اساس user_calendar_preference
        if user_calendar_preference == "System Default":
            display_calendar = settings.default_calendar
        elif user_calendar_preference == "Jalali":
            display_calendar = "Jalali"
        elif user_calendar_preference == "Gregorian":
            display_calendar = "Gregorian"
        else:
            display_calendar = settings.default_calendar
        
        # مرحله 4: week_start فقط اگر enable_jalali = True باشد اعمال می‌شود
        return {
            "display_calendar": display_calendar,
            "week_start": settings.week_start,
            "week_end": settings.week_end
        }
