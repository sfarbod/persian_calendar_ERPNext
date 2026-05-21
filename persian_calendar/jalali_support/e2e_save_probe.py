"""One-off bench probe: bench --site SITE execute persian_calendar.jalali_support.e2e_save_probe.run"""

from __future__ import annotations

import json
import traceback

import frappe
from frappe.utils import flt

from persian_calendar.jalali_support.datetime_normalizer import normalize_doc_datetimes
from persian_calendar.utils.jalali import coerce_gregorian_datetime


def run(job_card: str = "PO-JOB01041") -> dict:
	frappe.set_user("Administrator")
	out: dict = {"job_card": job_card, "coercion_samples": {}, "save": None}
	for sample in (
		"20-04-2026 08:30:00",
		"4/20/2026 8:30",
		"2026-04-20 08:30:00",
		"Invalid date",
	):
		out["coercion_samples"][sample] = coerce_gregorian_datetime(sample)

	doc = frappe.get_doc("Job Card", job_card)
	out["time_logs_before"] = [
		{
			"from_time": r.from_time,
			"to_time": r.to_time,
			"time_in_mins": r.time_in_mins,
			"completed_qty": r.completed_qty,
			"employee": r.employee,
			"operation": r.operation,
		}
		for r in (doc.time_logs or [])
	]

	# Simulate CSV import + UI display state (DD-MM user format in model)
	if not doc.time_logs:
		row = doc.append(
			"time_logs",
			{
				"from_time": "20-04-2026 08:30:00",
				"to_time": "20-04-2026 11:00:00",
				"time_in_mins": 150,
				"completed_qty": "5,625.000000C",
			},
		)
	else:
		row = doc.time_logs[0]
		row.from_time = "20-04-2026 08:30:00"
		row.to_time = "20-04-2026 11:00:00"
		row.completed_qty = "5,625.000000C"

	out["time_logs_payload"] = [
		{
			"from_time": r.from_time,
			"to_time": r.to_time,
			"completed_qty": r.completed_qty,
		}
		for r in doc.time_logs
	]

	try:
		frappe.get_attr(
			"persian_calendar.jalali_support.e2e_fixtures.prepare_work_order_for_job_card_save"
		)(job_card)
		normalize_doc_datetimes(doc)
		out["time_logs_after_normalize"] = [
			{
				"from_time": r.from_time,
				"to_time": r.to_time,
				"completed_qty": r.completed_qty,
			}
			for r in doc.time_logs
		]
		doc.save()
		frappe.db.commit()
		out["save"] = {"ok": True}
	except Exception:
		out["save"] = {"ok": False, "traceback": traceback.format_exc()}

	doc.reload()
	out["time_logs_after"] = [
		{
			"from_time": r.from_time,
			"to_time": r.to_time,
			"completed_qty": r.completed_qty,
		}
		for r in (doc.time_logs or [])
	]
	print(json.dumps(out, default=str, indent=2))
	return out
