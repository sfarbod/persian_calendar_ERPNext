"""bench --site SITE execute persian_calendar.jalali_support.savedocs_probe.run"""

from __future__ import annotations

import json
import traceback

import frappe


@frappe.whitelist()
def run(job_card: str = "PO-JOB01041") -> dict:
	frappe.set_user("Administrator")
	out: dict = {"job_card": job_card}
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
			JalaliSettings,
		)

		out["jalali_enabled"] = bool(JalaliSettings.get_settings().enabled)
	except Exception as e:
		out["jalali_enabled"] = f"error:{e}"

	doc = frappe.get_doc("Job Card", job_card)
	if not doc.time_logs:
		doc.append(
			"time_logs",
			{
				"time_in_mins": 150,
			},
		)
	row = doc.time_logs[0]
	row.from_time = "20-04-2026 08:30:00"
	row.to_time = "20-04-2026 13:30:00"
	row.completed_qty = "5,625.000000C"
	row.time_in_mins = 150

	out["payload"] = {
		"from_time": row.from_time,
		"to_time": row.to_time,
		"completed_qty": row.completed_qty,
	}

	try:
		frappe.get_attr(
			"persian_calendar.jalali_support.e2e_fixtures.prepare_work_order_for_job_card_save"
		)(job_card)
		from frappe.desk.form.save import savedocs

		doc_dict = doc.as_dict()
		for tl in doc_dict.get("time_logs") or []:
			tl["from_time"] = "20-04-2026 08:30:00"
			tl["to_time"] = "20-04-2026 13:30:00"
			tl["completed_qty"] = "5,625.000000C"
		# savedocs expects doc as JSON string (like browser)
		savedocs(doc=frappe.as_json(doc_dict), action="Save")
		out["savedocs"] = {"ok": True}
	except Exception:
		out["savedocs"] = {"ok": False, "traceback": traceback.format_exc()}

	print(json.dumps(out, default=str, indent=2))
	return out
