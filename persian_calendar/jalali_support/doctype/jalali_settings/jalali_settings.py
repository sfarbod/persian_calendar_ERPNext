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
        # computation_priority معتبر باشه
        if self.computation_priority and self.computation_priority not in ("Jalali", "Gregorian"):
            frappe.throw("مقدار Computation Priority باید «Jalali» یا «Gregorian» باشد.")

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
        برمی‌گرداند تنظیمات جاری به صورت دیکشن با کلیدهای: enabled, allow_user_override, default_calendar,
        computation_priority, week_start, week_end
        """
        doc = frappe.get_single("Jalali Settings")

        enabled = True if doc.enable_jalali else False


        default_calendar = doc.default_calendar if doc.default_calendar in ("Jalali", "Gregorian") else "Jalali"
        computation_priority = doc.computation_priority if doc.computation_priority in ("Jalali", "Gregorian") else "Jalali"

        week_start = doc.week_start if (doc.week_start is not None) else 6
        week_end = doc.week_end if (doc.week_end is not None) else 5

        return frappe._dict(
            enabled = enabled,
            default_calendar = default_calendar,
            computation_priority = computation_priority,
            week_start = week_start,
            week_end = week_end
        )
