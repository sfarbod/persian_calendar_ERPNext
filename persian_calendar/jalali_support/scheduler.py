
import datetime as dt
import frappe
from persian_calendar.jalali_support.utils.date_utils import is_j_month_end



def month_end_runner():
    today = dt.date.today()
    if not is_j_month_end(today):
        return

    # هندلرهای رجیستری شده دیگر اپ‌ها
    handlers = frappe.get_hooks("persian_month_end_handlers") or []
    for dotted in handlers:
        try:
            method = frappe.get_attr(dotted)
            frappe.enqueue(method, queue="long", job_name=f"jalali_month_end:{dotted}")
        except Exception:
            frappe.log_error(f"Failed to enqueue month_end handler: {dotted}")

    # Auto Repeatهایی که پرچم شمسی دارند
    auto_repeats = frappe.get_all(
        "Auto Repeat",
        filters={"enabled": 1, "frequency": "Monthly", "pc_use_shamsi": 1, "pc_shamsi_last_day": 1},
        pluck="name"
    )
    for name in auto_repeats:
        try:
            doc = frappe.get_doc("Auto Repeat", name)
            if hasattr(doc, "create_documents"):
                frappe.enqueue(doc.create_documents, queue="long", job_name=f"auto_repeat_shamsi:{name}")
            else:
                doc.run_method("create_documents")
        except Exception as e:
            frappe.log_error(f"Auto Repeat (Shamsi) failed for {name}: {e}")
