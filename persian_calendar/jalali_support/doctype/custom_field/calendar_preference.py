# Copyright (c) 2025, Persian Calendar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class CustomFieldCalendarPreference(Document):
    pass

# Auto-create the custom field when the app is installed
def create_calendar_preference_field():
    """Create calendar_preference custom field for User DocType"""
    
    # Check if the custom field already exists
    if frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "calendar_preference"}):
        print("Calendar preference custom field already exists")
        return
    
    try:
        # Create the custom field
        custom_field = frappe.new_doc("Custom Field")
        custom_field.dt = "User"
        custom_field.module = "Persian Calendar"
        custom_field.label = "Calendar Preference"
        custom_field.fieldname = "calendar_preference"
        custom_field.insert_after = "language"
        custom_field.fieldtype = "Select"
        custom_field.options = "System Default\nJalali\nGregorian"
        custom_field.default = "System Default"
        custom_field.reqd = 0
        custom_field.save()
        
        print("Calendar preference custom field created successfully")
        
        # Commit the changes
        frappe.db.commit()
        
    except Exception as e:
        print(f"Error creating calendar preference custom field: {e}")
        frappe.db.rollback()

# Function to remove the custom field (for uninstall)
def remove_calendar_preference_field():
    """Remove calendar_preference custom field from User DocType"""
    
    try:
        custom_field = frappe.get_doc("Custom Field", {"dt": "User", "fieldname": "calendar_preference"})
        custom_field.delete()
        
        print("Calendar preference custom field removed successfully")
        
        # Commit the changes
        frappe.db.commit()
        
    except Exception as e:
        print(f"Error removing calendar preference custom field: {e}")
        frappe.db.rollback()