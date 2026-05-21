# Copyright (c) 2025, Farbod Siyahpoosh and Contributors
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from persian_calendar.jalali_support.datetime_normalizer import (
	_coerce_field,
	normalize_doc_datetimes,
)


class TestDatetimeNormalizer(FrappeTestCase):
	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_job_card_time_log_import_payload(self, _enabled):
		"""Regression: CSV M/D/YYYY H:mm must not reach MySQL on save."""
		row = frappe._dict(
			doctype="Job Card Time Log",
			from_time="4/20/2026 8:30",
			to_time="4/20/2026 11:00",
		)
		_coerce_field(row, "from_time", "Datetime")
		_coerce_field(row, "to_time", "Datetime")
		self.assertEqual(str(row.from_time), "2026-04-20 08:30:00")
		self.assertEqual(str(row.to_time), "2026-04-20 11:00:00")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_normalize_doc_datetimes_job_card_child_table(self, _enabled):
		if not frappe.db.exists("DocType", "Job Card"):
			self.skipTest("ERPNext Job Card not installed")
		doc = frappe.new_doc("Job Card")
		doc.append(
			"time_logs",
			{
				"from_time": "4/20/2026 8:30",
				"to_time": "4/20/2026 11:00",
			},
		)
		normalize_doc_datetimes(doc)
		row = doc.time_logs[0]
		self.assertEqual(str(row.from_time), "2026-04-20 08:30:00")
		self.assertEqual(str(row.to_time), "2026-04-20 11:00:00")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=False,
	)
	def test_normalize_runs_when_jalali_disabled_gregorian_preference(self, _enabled):
		row = frappe._dict(
			doctype="Job Card Time Log",
			from_time="20-04-2026 08:30:00",
			to_time="20-04-2026 11:00:00",
			completed_qty="5,625.000000C",
		)
		normalize_doc_datetimes(row)
		self.assertEqual(str(row.from_time), "2026-04-20 08:30:00")
		self.assertEqual(str(row.to_time), "2026-04-20 11:00:00")
		self.assertEqual(row.completed_qty, 5625.0)

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_time_fields_are_not_modified_on_validate(self, _enabled):
		row = frappe._dict(doctype="Purchase Receipt", name="MAT-PRE-2026-00075", posting_time="Invalid date")
		normalize_doc_datetimes(row)
		self.assertNotEqual(row.posting_time, "Invalid date")
		self.assertIn(str(row.posting_time), ("1:29:23", "01:29:23"))

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_dd_mm_yyyy_user_display_coerces_on_validate(self, _enabled):
		row = frappe._dict(
			doctype="Job Card Time Log",
			from_time="20-04-2026 08:30:00",
			to_time="20-04-2026 11:00:00",
		)
		_coerce_field(row, "from_time", "Datetime")
		_coerce_field(row, "to_time", "Datetime")
		self.assertEqual(str(row.from_time), "2026-04-20 08:30:00")
		self.assertEqual(str(row.to_time), "2026-04-20 11:00:00")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	def test_csv_completed_qty_with_suffix_sanitizes(self, _enabled):
		row = frappe._dict(doctype="Job Card Time Log", completed_qty="5,625.000000C")
		from persian_calendar.jalali_support.datetime_normalizer import _sanitize_numeric_field

		_sanitize_numeric_field(row, "completed_qty", "Float")
		self.assertEqual(row.completed_qty, 5625.0)
