"""Phase 5A-2 — CRM Display Calendar coverage verification.

Outcome A: CRM Form/List/Query Report Date and Datetime surfaces inherit the
global desk Display Calendar layer. This module locks that inventory and the
documented limitations. No CRM-specific display adapters are registered.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from persian_calendar.api import toshamshi, toshamsi
from persian_calendar.jalali_support.datetime_normalizer import (
	_coerce_field,
	normalize_doc_datetimes,
)
from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
	JalaliSettings,
)

# Independently verified Gregorian → Jalali (same anchors as Phase 5A-1).
_G2026_05_13 = "1405-02-23"
_G2025_03_20 = "1403-12-30"  # Esfand 30 leap 1403
_G2026_03_21 = "1405-01-01"  # Farvardin 1 1405

_CRM_REPORTS = (
	"sales_pipeline_analytics",
	"opportunity_summary_by_sales_stage",
	"lost_opportunity",
	"lead_details",
	"lead_owner_efficiency",
	"lead_conversion_time",
	"first_response_time_for_opportunity",
	"campaign_efficiency",
	"prospects_engaged_but_not_converted",
)

_CRM_DOCTYPES_WITH_DATES = {
	"Lead": (("qualified_on", "Date"),),
	"Opportunity": (("expected_closing", "Date"), ("transaction_date", "Date")),
	"Appointment": (("scheduled_time", "Datetime"),),
	"Email Campaign": (("start_date", "Date"), ("end_date", "Date")),
	"CRM Note": (("added_on", "Datetime"),),
	"Contract": (
		("start_date", "Date"),
		("end_date", "Date"),
		("signed_on", "Datetime"),
		("fulfilment_deadline", "Date"),
	),
}


def _erpnext_crm_root() -> Path:
	return Path(frappe.get_app_path("erpnext")).joinpath("crm")


def _load_report_js(report_folder: str) -> str:
	path = _erpnext_crm_root() / "report" / report_folder / f"{report_folder}.js"
	if not path.is_file():
		return ""
	return path.read_text(encoding="utf-8")


def _load_report_py(report_folder: str) -> str:
	path = _erpnext_crm_root() / "report" / report_folder / f"{report_folder}.py"
	if not path.is_file():
		return ""
	return path.read_text(encoding="utf-8")


class TestCrmDocTypeDateInventory(FrappeTestCase):
	"""CRM Date/Datetime fields remain standard types (global formatters apply)."""

	def test_crm_doctype_date_fields_are_standard_types(self):
		for doctype, expected in _CRM_DOCTYPES_WITH_DATES.items():
			if not frappe.db.exists("DocType", doctype):
				self.skipTest(f"{doctype} not installed")
			meta = frappe.get_meta(doctype)
			for fieldname, fieldtype in expected:
				df = meta.get_field(fieldname)
				self.assertIsNotNone(df, f"{doctype}.{fieldname} missing")
				self.assertEqual(
					df.fieldtype,
					fieldtype,
					f"{doctype}.{fieldname} must stay {fieldtype} for Display Calendar",
				)

	def test_related_desk_doctypes_use_standard_date_types(self):
		related = {
			"Communication": (("communication_date", "Datetime"),),
			"Event": (("starts_on", "Datetime"), ("ends_on", "Datetime")),
			"ToDo": (("date", "Date"),),
		}
		for doctype, expected in related.items():
			meta = frappe.get_meta(doctype)
			for fieldname, fieldtype in expected:
				df = meta.get_field(fieldname)
				self.assertIsNotNone(df, f"{doctype}.{fieldname}")
				self.assertEqual(df.fieldtype, fieldtype)

	def test_crm_list_js_has_no_custom_date_formatters(self):
		crm = _erpnext_crm_root() / "doctype"
		for path in crm.glob("*/*_list.js"):
			text = path.read_text(encoding="utf-8")
			self.assertNotRegex(
				text,
				r"\bformatters\s*:",
				msg=f"{path.name} defines listview formatters that may bypass Display Calendar",
			)
			self.assertNotIn("str_to_user", text)
			self.assertNotIn("strftime", text)


class TestCrmReportDisplayContract(FrappeTestCase):
	def test_crm_report_filters_use_date_fieldtype(self):
		for folder in _CRM_REPORTS:
			js = _load_report_js(folder)
			if not js:
				self.skipTest(f"missing report js: {folder}")
			if "from_date" not in js and "to_date" not in js:
				continue
			self.assertIn('fieldtype: "Date"', js, f"{folder} date filters must be Date")

	def test_sales_pipeline_grouping_remains_gregorian_labels(self):
		"""Phase 5A-2 must not claim Business Calendar for pipeline months."""
		py = _load_report_py("sales_pipeline_analytics")
		self.assertIn("MonthName", py)
		self.assertIn('strftime("%B")', py)
		adapter = Path(
			frappe.get_app_path("persian_calendar"),
			"calendar",
			"integrations",
			"crm_pipeline.py",
		)
		self.assertFalse(adapter.is_file(), "CRM Pipeline BC adapter must stay deferred")

	def test_first_response_grid_date_column_typed(self):
		py = _load_report_py("first_response_time_for_opportunity")
		self.assertIn('"fieldtype": "Date"', py)
		self.assertIn("creation_date", py)
		js = _load_report_js("first_response_time_for_opportunity")
		# Documented limitation: chart labels use raw ISO
		self.assertIn("d.creation_date", js)

	def test_prospects_last_communication_date_is_date(self):
		py = _load_report_py("prospects_engaged_but_not_converted")
		self.assertIn('"fieldname": "last_communication_date"', py)
		self.assertIn('"fieldtype": "Date"', py)
		self.assertIn('"fieldtype": "Data"', py)  # last_communication text column


class TestCrmDisplayArchitectureGuards(FrappeTestCase):
	def test_no_formatdate_monkey_patch(self):
		import frappe.utils as fu
		from frappe.utils.data import format_date

		self.assertIs(fu.formatdate, format_date)

	def test_jalali_bundle_included_for_desk(self):
		hooks = frappe.get_hooks("app_include_js") or []
		joined = " ".join(hooks)
		self.assertIn("jalali_support.bundle.js", joined)

	def test_no_crm_doctype_js_overrides_in_persian_calendar(self):
		hooks = frappe.get_hooks("doctype_js") or {}
		crm_names = set(_CRM_DOCTYPES_WITH_DATES)
		overlap = crm_names.intersection(hooks.keys())
		self.assertFalse(
			overlap,
			f"Unexpected CRM doctype_js overrides: {overlap} — prefer global Display Calendar",
		)

	def test_datetime_normalizer_hook_is_global(self):
		events = frappe.get_hooks("doc_events") or {}
		star = events.get("*") or {}
		validate = star.get("validate") or []
		joined = " ".join(validate)
		self.assertIn("datetime_normalizer", joined)

	def test_appointment_email_still_uses_unpatched_format_datetime(self):
		"""Known limitation — Gregorian in appointment confirmed email args."""
		path = _erpnext_crm_root() / "doctype" / "appointment" / "appointment.py"
		src = path.read_text(encoding="utf-8")
		self.assertIn("format_datetime(self.scheduled_time)", src)


class TestCrmInputRoundTripStorage(FrappeTestCase):
	"""Jalali-looking inputs normalize to Gregorian storage (global normalizer)."""

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_opportunity_date_fields_coerce_jalali_strings(self, _enabled):
		if not frappe.db.exists("DocType", "Opportunity"):
			self.skipTest("Opportunity not installed")
		row = frappe._dict(
			doctype="Opportunity",
			transaction_date="1405-01-01",
			expected_closing="1403-12-30",
		)
		_coerce_field(row, "transaction_date", "Date")
		_coerce_field(row, "expected_closing", "Date")
		self.assertEqual(str(row.transaction_date)[:10], "2026-03-21")
		self.assertEqual(str(row.expected_closing)[:10], "2025-03-20")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_appointment_datetime_coerce_preserves_wall_clock(self, _enabled):
		if not frappe.db.exists("DocType", "Appointment"):
			self.skipTest("Appointment not installed")
		row = frappe._dict(
			doctype="Appointment",
			scheduled_time="1405-02-23 14:30:00",
		)
		_coerce_field(row, "scheduled_time", "Datetime")
		self.assertEqual(str(row.scheduled_time), "2026-05-13 14:30:00")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_normalize_doc_datetimes_on_opportunity_new_doc(self, _enabled):
		if not frappe.db.exists("DocType", "Opportunity"):
			self.skipTest("Opportunity not installed")
		doc = frappe.new_doc("Opportunity")
		doc.transaction_date = "1405-01-01"
		doc.expected_closing = "1402-12-29"
		normalize_doc_datetimes(doc)
		self.assertEqual(str(doc.transaction_date)[:10], "2026-03-21")
		self.assertEqual(str(doc.expected_closing)[:10], "2024-03-19")


class TestDisplayVersusBusinessAndExplicitConversion(FrappeTestCase):
	def tearDown(self):
		user = frappe.session.user
		if user and user != "Guest":
			frappe.db.set_value(
				"User",
				user,
				"calendar_preference",
				"System Default",
				update_modified=False,
			)

	def test_toshamshi_independent_of_user_display_calendar(self):
		user = frappe.session.user
		if user == "Guest":
			self.skipTest("No logged-in user")
		value = "2026-05-13"
		frappe.db.set_value("User", user, "calendar_preference", "Gregorian", update_modified=False)
		a = toshamshi(value)
		frappe.db.set_value("User", user, "calendar_preference", "Jalali", update_modified=False)
		b = toshamshi(value)
		self.assertEqual(a, _G2026_05_13)
		self.assertEqual(b, _G2026_05_13)
		self.assertEqual(JalaliSettings.get_effective_calendar(user)["display_calendar"], "Jalali")
		self.assertIs(toshamsi, toshamshi)

	def test_toshamshi_independent_of_company_business_calendar(self):
		with patch(
			"persian_calendar.calendar.resolve.get_business_calendar_for_company",
			return_value="Jalali",
		):
			self.assertEqual(toshamshi("2025-03-20"), _G2025_03_20)
		with patch(
			"persian_calendar.calendar.resolve.get_business_calendar_for_company",
			return_value="Gregorian",
		):
			self.assertEqual(toshamshi("2026-03-21"), _G2026_03_21)

	def test_jinja_crm_print_pattern(self):
		html = frappe.render_template(
			"<p>{{ toshamshi(doc.expected_closing, format='YYYY/MM/DD') }}</p>"
			"<p>{{ toshamsi(doc.transaction_date) }}</p>",
			{
				"doc": {
					"expected_closing": "2026-05-13",
					"transaction_date": "2026-03-21",
				}
			},
		)
		self.assertIn("1405/02/23", html)
		self.assertIn(_G2026_03_21, html)


class TestCrmDisplayRegistry(FrappeTestCase):
	def test_registry_marks_crm_display_covered(self):
		from persian_calendar.calendar.registry import INTEGRATED_MODULES

		names = {m.name: m for m in INTEGRATED_MODULES}
		self.assertIn("CRM Display Calendar", names)
		mod = names["CRM Display Calendar"]
		self.assertEqual(mod.status, "display_covered")
		self.assertEqual(mod.patch_targets, ())
		self.assertIn("CRM_DISPLAY_CALENDAR", mod.documentation)

		pipeline = names["CRM Pipeline Analytics"]
		self.assertEqual(pipeline.status, "deferred")


if __name__ == "__main__":
	import unittest

	unittest.main()
