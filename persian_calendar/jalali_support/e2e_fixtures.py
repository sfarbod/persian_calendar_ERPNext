# Copyright (c) 2026, Persian Calendar Contributors
"""
Minimal ERPNext manufacturing docs for browser E2E tests (Job Card + Time Logs).

Guarded: only runs when allow_tests, developer_mode, or site_config
``persian_calendar_e2e_fixtures`` is truthy.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime


def _e2e_allowed() -> bool:
	if frappe.session.user == "Guest":
		return False
	if not frappe.local.conf.get("persian_calendar_e2e_fixtures") and not (
		frappe.conf.get("allow_tests") or frappe.conf.get("developer_mode")
	):
		return False
	return True


def _require_e2e() -> None:
	if not _e2e_allowed():
		frappe.throw(_("Persian Calendar E2E fixtures are not enabled on this site."), frappe.PermissionError)


def _default_company() -> str:
	c = frappe.defaults.get_global_default("default_company")
	if c:
		return c
	row = frappe.db.get_list("Company", limit_page_length=1, pluck="name")
	if not row:
		frappe.throw(_("No Company found"))
	return row[0]


def _default_item_group() -> str:
	rows = frappe.db.get_list(
		"Item Group", filters={"is_group": 0, "name": ("!=", "All Item Groups")}, limit_page_length=1, pluck="name"
	)
	if rows:
		return rows[0]
	return "Products"


def _pick_warehouse(company: str, hint: str) -> str:
	wh = frappe.db.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0, "warehouse_name": ("like", f"%{hint}%")},
		limit_page_length=1,
		pluck="name",
	)
	if wh:
		return wh[0]
	wh = frappe.db.get_list(
		"Warehouse", filters={"company": company, "is_group": 0}, limit_page_length=1, pluck="name"
	)
	if not wh:
		frappe.throw(_("No warehouse for company {0}").format(company))
	return wh[0]


@frappe.whitelist()
def create_job_card_time_log_fixture() -> dict[str, Any]:
	"""Create Item, BOM, Work Order, Job Card, one Time Log row. Returns names for cleanup."""
	_require_e2e()
	if "erpnext" not in frappe.get_installed_apps():
		frappe.throw(_("ERPNext is required for this fixture"))

	from erpnext.manufacturing.doctype.work_order.work_order import make_job_card

	suffix = frappe.generate_hash(length=10)
	company = _default_company()
	fg = f"PC-E2E-FG-{suffix}"
	rm = f"PC-E2E-RM-{suffix}"
	op_name = f"PC-E2E-OP-{suffix}"
	ws_name = f"PC-E2E-WS-{suffix}"
	item_group = _default_item_group()

	ws = frappe.new_doc("Workstation")
	ws.workstation_name = ws_name
	ws.company = company
	ws.production_capacity = 1
	ws.insert()

	op = frappe.get_doc({"doctype": "Operation", "name": op_name, "workstation": ws_name})
	op.insert()

	for code in (fg, rm):
		if frappe.db.exists("Item", code):
			continue
		item = frappe.new_doc("Item")
		item.item_code = code
		item.item_name = code
		item.item_group = item_group
		item.stock_uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
		item.is_stock_item = 1
		item.include_item_in_manufacturing = 1
		item.insert(ignore_permissions=True)

	frappe.db.commit()

	wip = _pick_warehouse(company, "WIP")
	fg_wh = _pick_warehouse(company, "Finished") or wip

	bom = frappe.new_doc("BOM")
	bom.item = fg
	bom.quantity = 1
	bom.company = company
	bom.is_active = 1
	bom.is_default = 1
	bom.with_operations = 1
	rate = 100
	bom.append("items", {"item_code": rm, "qty": 1, "rate": rate})
	bom.append(
		"operations",
		{
			"operation": op_name,
			"workstation": ws_name,
			"time_in_mins": 60,
			"hour_rate": 20,
		},
	)
	bom.insert()
	bom.submit()

	wo = frappe.new_doc("Work Order")
	wo.production_item = fg
	wo.bom_no = bom.name
	wo.qty = 1
	wo.company = company
	wo.wip_warehouse = wip
	wo.fg_warehouse = fg_wh
	wo.scrap_warehouse = fg_wh
	wo.skip_transfer = 1
	wo.transfer_material_against = "Work Order"
	wo.planned_start_date = now_datetime()
	wo.get_items_and_operations_from_bom()
	wo.insert()

	wo.reload()
	operations: list[dict[str, Any]] = []
	for row in wo.operations:
		d = row.as_dict()
		d["qty"] = 1
		d["pending_qty"] = 1
		operations.append(d)

	make_job_card(wo.name, json.dumps(operations))

	jc_name = frappe.db.get_value("Job Card", {"work_order": wo.name}, "name")
	if not jc_name:
		frappe.throw(_("Job Card was not created"))

	jc = frappe.get_doc("Job Card", jc_name)
	ts = "2026-04-20 15:30:00"
	ts2 = "2026-04-20 18:00:00"
	jc.append(
		"time_logs",
		{
			"from_time": ts,
			"to_time": ts2,
			"time_in_mins": 150,
			"completed_qty": 0,
		},
	)
	jc.save()

	return {
		"suffix": suffix,
		"job_card": jc.name,
		"work_order": wo.name,
		"bom": bom.name,
		"items": [fg, rm],
		"operation": op_name,
		"workstation": ws_name,
	}


@frappe.whitelist()
def delete_job_card_time_log_fixture(payload: str | dict | None = None) -> None:
	"""Best-effort cleanup for ``create_job_card_time_log_fixture``."""
	_require_e2e()
	if isinstance(payload, str):
		payload = json.loads(payload)
	payload = payload or {}

	jc = payload.get("job_card")
	wo = payload.get("work_order")
	bom = payload.get("bom")
	items = payload.get("items") or []
	op_name = payload.get("operation")
	ws_name = payload.get("workstation")

	if jc and frappe.db.exists("Job Card", jc):
		doc = frappe.get_doc("Job Card", jc)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("Job Card", jc, force=1, ignore_permissions=True)

	if wo and frappe.db.exists("Work Order", wo):
		wdoc = frappe.get_doc("Work Order", wo)
		if wdoc.docstatus == 1:
			wdoc.cancel()
		frappe.delete_doc("Work Order", wo, force=1, ignore_permissions=True)

	if bom and frappe.db.exists("BOM", bom):
		b = frappe.get_doc("BOM", bom)
		if b.docstatus == 1:
			b.cancel()
		frappe.delete_doc("BOM", bom, force=1, ignore_permissions=True)

	for item in items:
		if item and frappe.db.exists("Item", item):
			try:
				frappe.delete_doc("Item", item, force=1, ignore_permissions=True)
			except Exception:
				pass

	if op_name and str(op_name).startswith("PC-E2E-OP-") and frappe.db.exists("Operation", op_name):
		try:
			frappe.delete_doc("Operation", op_name, force=1, ignore_permissions=True)
		except Exception:
			pass

	if ws_name and str(ws_name).startswith("PC-E2E-WS-") and frappe.db.exists("Workstation", ws_name):
		try:
			frappe.delete_doc("Workstation", ws_name, force=1, ignore_permissions=True)
		except Exception:
			pass

	frappe.db.commit()


@frappe.whitelist()
def prepare_work_order_for_job_card_save(job_card: str) -> dict[str, Any]:
	"""E2E only: mark prior WO operations complete so Job Card save is not blocked by sequence."""
	_require_e2e()
	jc = frappe.get_doc("Job Card", job_card)
	if not jc.work_order or not jc.sequence_id:
		return {"ok": False, "reason": "missing work_order or sequence_id"}
	updated = []
	for row in frappe.get_all(
		"Work Order Operation",
		filters={"parent": jc.work_order, "docstatus": 1, "sequence_id": ("<", jc.sequence_id)},
		fields=["name", "operation", "sequence_id"],
	):
		frappe.db.set_value(
			"Work Order Operation",
			row.name,
			{"completed_qty": 999999, "status": "Completed"},
			update_modified=False,
		)
		updated.append(row.name)
	frappe.db.commit()
	return {"ok": True, "updated": updated, "job_card": job_card}


@frappe.whitelist()
def set_calendar_e2e_context(
	default_calendar: str = "Jalali",
	user_calendar_preference: str = "System Default",
	persian_calendar_enabled: bool | None = None,
) -> dict[str, Any]:
	"""E2E: set Administrator calendar preference and site default_calendar."""
	_require_e2e()
	if default_calendar not in ("Jalali", "Gregorian"):
		frappe.throw(_("default_calendar must be Jalali or Gregorian"))
	if user_calendar_preference not in ("System Default", "Jalali", "Gregorian"):
		frappe.throw(_("user_calendar_preference invalid"))
	frappe.db.set_value(
		"User",
		"Administrator",
		"calendar_preference",
		user_calendar_preference,
		update_modified=False,
	)
	frappe.db.set_value(
		"Jalali Settings", "Jalali Settings", "default_calendar", default_calendar, update_modified=False
	)
	if persian_calendar_enabled is not None:
		frappe.db.set_value(
			"Jalali Settings",
			"Jalali Settings",
			"enable_jalali",
			1 if persian_calendar_enabled else 0,
			update_modified=False,
		)
	frappe.db.commit()
	frappe.clear_cache()
	try:
		frappe.clear_document_cache("User", "Administrator")
	except Exception:
		pass
	return {
		"user": "Administrator",
		"default_calendar": default_calendar,
		"calendar_preference": user_calendar_preference,
		"persian_calendar_enabled": persian_calendar_enabled,
	}


def _get_or_create_e2e_employee() -> str:
	company = _default_company()
	email = "pc-e2e-checkin@example.com"
	employee = frappe.db.get_value("Employee", {"user_id": email}, "name")
	if employee:
		return employee
	employee = frappe.db.get_value("Employee", {"company": company, "status": "Active"}, "name")
	if employee:
		return employee
	doc = frappe.new_doc("Employee")
	doc.first_name = "PC"
	doc.last_name = "E2E Checkin"
	doc.company = company
	doc.date_of_birth = "1990-01-01"
	doc.date_of_joining = frappe.utils.today()
	doc.gender = "Male"
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def create_employee_checkin_datetime_fixture(
	checkin_time: str = "2026-05-24 23:30:00",
) -> dict[str, Any]:
	"""Create a development-only Employee Checkin row for list/form datetime E2E."""
	_require_e2e()
	if "hrms" not in frappe.get_installed_apps():
		frappe.throw(_("HRMS is required for Employee Checkin E2E fixture"))

	employee = _get_or_create_e2e_employee()

	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee
	doc.time = checkin_time
	doc.device_id = "PC-E2E"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"employee": employee,
		"time": str(doc.time),
		"checkin_time": checkin_time,
	}


@frappe.whitelist()
def delete_employee_checkin_e2e_fixture(name: str) -> dict[str, Any]:
	"""Remove development-only Employee Checkin fixture."""
	_require_e2e()
	if not name or not frappe.db.exists("Employee Checkin", name):
		return {"deleted": False, "name": name}
	doc = frappe.get_doc("Employee Checkin", name)
	if doc.device_id != "PC-E2E":
		frappe.throw(_("Refusing to delete non-E2E Employee Checkin"))
	frappe.delete_doc("Employee Checkin", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"deleted": True, "name": name}


@frappe.whitelist()
def get_calendar_e2e_debug_state() -> dict[str, Any]:
	"""Server-side calendar state for E2E failure dumps."""
	_require_e2e()
	from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
		JalaliSettings,
	)

	settings = JalaliSettings.get_settings()
	user_pref = (
		frappe.db.get_value("User", "Administrator", "calendar_preference") or "System Default"
	)
	effective = JalaliSettings.get_effective_calendar(user="Administrator")
	return {
		"user_calendar_preference": user_pref,
		"jalali_settings_enabled": bool(settings.enabled),
		"jalali_settings_default_calendar": settings.default_calendar,
		"effective_display_calendar": effective.get("display_calendar"),
	}
