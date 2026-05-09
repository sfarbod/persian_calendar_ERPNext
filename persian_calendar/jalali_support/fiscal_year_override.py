# Copyright (c) 2025, Persian Calendar and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

_fiscal_year_validate_dates_patched = False

def setup_fiscal_year_override():
    """Setup Fiscal Year validation override for Jalali calendar support"""
    global _fiscal_year_validate_dates_patched
    if _fiscal_year_validate_dates_patched:
        return

    # Import the original FiscalYear class
    from erpnext.accounts.doctype.fiscal_year.fiscal_year import FiscalYear as OriginalFiscalYear
    
    # Store original validate_dates method
    original_validate_dates = OriginalFiscalYear.validate_dates
    
    def jalali_validate_dates(self):
        """Override validate_dates to support Jalali calendar"""
        
        # First check if Jalali calendar is enabled
        try:
            from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import JalaliSettings
            settings = JalaliSettings.get_settings()
            
            if not settings.enabled:
                # Use original validation if Jalali is disabled
                return original_validate_dates(self)
            
            # Get effective calendar settings
            effective = JalaliSettings.get_effective_calendar()
            display_calendar = effective.get("display_calendar", "Jalali")
            
            if display_calendar == "Gregorian":
                # Use original validation if display is Gregorian
                return original_validate_dates(self)
            
            # For Jalali calendar, use different validation logic
            self.validate_from_to_dates("year_start_date", "year_end_date")
            
            if self.is_short_year:
                # Fiscal Year can be shorter than one year
                return
            
            # For Jalali calendar, check if it's approximately one year
            # Jalali years can be 29 or 30 days in the last month
            start_date = getdate(self.year_start_date)
            end_date = getdate(self.year_end_date)
            
            # Calculate the difference in days
            days_diff = (end_date - start_date).days
            
            # Allow for Jalali year variations (354-366 days)
            if days_diff < 354 or days_diff > 366:
                frappe.throw(
                    frappe._("Fiscal Year should be approximately one Jalali year (354-366 days)"),
                    frappe.exceptions.InvalidDates,
                )
                
        except Exception:
            return original_validate_dates(self)
    
    # Replace the validate_dates method
    OriginalFiscalYear.validate_dates = jalali_validate_dates
    _fiscal_year_validate_dates_patched = True


def remove_fiscal_year_override():
    """Remove Fiscal Year validation override"""
    pass
