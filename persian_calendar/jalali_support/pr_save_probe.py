"""bench --site SITE execute persian_calendar.jalali_support.pr_save_probe.run"""

from __future__ import annotations

import json
import traceback

import frappe

from persian_calendar.jalali_support.datetime_normalizer import normalize_doc_datetimes
from persian_calendar.utils.jalali import coerce_gregorian_datetime


def _date_time_fields(doc) -> dict:
	meta = frappe.get_meta(doc.doctype)
	out = {}
	for df in meta.fields:
		if df.fieldtype in ("Date", "Datetime", "Time"):
			out[df.fieldname] = doc.get(df.fieldname)
	for df in meta.fields:
		if df.fieldtype != "Table":
			continue
		child_meta = frappe.get_meta(df.options)
		for row in doc.get(df.fieldname) or []:
			for cdf in child_meta.fields:
				if cdf.fieldtype in ("Date", "Datetime", "Time"):
					key = f"{df.fieldname}[{row.idx}].{cdf.fieldname}"
					out[key] = row.get(cdf.fieldname)
	return out


def run(name: str = "MAT-PRE-2026-00075") -> dict:
	frappe.set_user("Administrator")
	doc = frappe.get_doc("Purchase Receipt", name)
	out = {
		"name": name,
		"date_time_fields_before": _date_time_fields(doc),
		"coerce_samples": {
			"posting_date": coerce_gregorian_datetime(doc.posting_date),
			"posting_time": coerce_gregorian_datetime(doc.posting_time),
		},
	}
	try:
		normalize_doc_datetimes(doc)
		out["date_time_fields_after_norm"] = _date_time_fields(doc)
		doc.save()
		frappe.db.commit()
		out["save"] = "ok"
	except Exception:
		out["save"] = "fail"
		out["traceback"] = traceback.format_exc()
	doc.reload()
	out["date_time_fields_after_save"] = _date_time_fields(doc)
	print(json.dumps(out, default=str, indent=2))
	return out


def run_simulated_payload(name: str = "MAT-PRE-2026-00075") -> dict:
	"""Simulate bad client savedocs payload (Jalali date in model)."""
	frappe.set_user("Administrator")
	doc = frappe.get_doc("Purchase Receipt", name)
	out = {"name": name, "cases": []}
	cases = [
		("jalali_posting_date", {"posting_date": "1405-02-30"}),
		("jalali_posting_date_with_time", {"posting_date": "1405-02-30 01:29:08"}),
		("dd_mm_posting", {"posting_date": "20-05-2026"}),
		("invalid_posting_time", {"posting_time": "Invalid date"}),
	]
	for label, overrides in cases:
		trial = frappe.get_doc("Purchase Receipt", name)
		for k, v in overrides.items():
			trial.set(k, v)
		case = {"label": label, "overrides": overrides, "before": _date_time_fields(trial)}
		try:
			normalize_doc_datetimes(trial)
			case["after_norm"] = _date_time_fields(trial)
			trial.save()
			frappe.db.rollback()
			case["save"] = "ok"
		except Exception:
			case["save"] = "fail"
			case["traceback"] = traceback.format_exc()
		out["cases"].append(case)
	print(json.dumps(out, default=str, indent=2))
	return out
