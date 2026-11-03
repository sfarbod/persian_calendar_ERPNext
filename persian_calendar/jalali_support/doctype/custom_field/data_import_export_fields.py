# Copyright (c) 2025, Persian Calendar contributors
# License: MIT

import frappe
from frappe.utils import cstr


def _ensure_custom_field(
	dt: str,
	fieldname: str,
	label: str,
	insert_after: str,
	*,
	default: str = "0",
) -> None:
	existing = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname})
	if existing:
		doc = frappe.get_doc("Custom Field", existing)
		updated = False
		if doc.hidden:
			doc.hidden = 0
			updated = True
		if insert_after and doc.insert_after != insert_after:
			doc.insert_after = insert_after
			updated = True
		# Keep Data Export Jalali checkbox default in sync (2.1.1+).
		if default is not None and cstr(doc.default) != cstr(default):
			doc.default = default
			updated = True
		if updated:
			doc.save(ignore_permissions=True)
		return

	doc = frappe.new_doc("Custom Field")
	doc.dt = dt
	doc.module = "Persian Calendar"
	doc.label = label
	doc.fieldname = fieldname
	doc.fieldtype = "Check"
	doc.insert_after = insert_after
	doc.default = default
	doc.hidden = 0
	doc.insert(ignore_permissions=True)


def create_data_import_export_fields() -> None:
	"""Create or update Custom Fields (install / migrate)."""
	_ensure_custom_field(
		"Data Export",
		"export_dates_as_jalali",
		"Export dates as Jalali",
		"file_type",
		default="1",
	)
	_ensure_custom_field(
		"Data Import",
		"import_dates_from_jalali",
		"Import dates from Jalali",
		"import_type",
		default="0",
	)
	frappe.db.commit()
	frappe.clear_cache(doctype="Data Export")
	frappe.clear_cache(doctype="Data Import")
	try:
		from persian_calendar.jalali_support.data_import_export import apply_data_import_export_patches

		apply_data_import_export_patches()
	except Exception as e:
		frappe.log_error(title="persian_calendar data_io patches", message=frappe.get_traceback())
	frappe.logger("persian_calendar").info("Jalali Data Import/Export custom fields ensured")


def remove_data_import_export_fields() -> None:
	for dt, fieldname in (
		("Data Export", "export_dates_as_jalali"),
		("Data Import", "import_dates_from_jalali"),
	):
		name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, force=1)
	frappe.db.commit()
