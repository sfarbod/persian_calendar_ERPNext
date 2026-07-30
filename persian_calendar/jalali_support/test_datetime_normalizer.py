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
	@patch("frappe.db.get_value", return_value="01:29:23")
	def test_time_fields_restore_from_db_on_invalid_value(self, _get_value, _enabled):
		"""Bad Time strings restore from DB when the document has a name (unit: no site fixture)."""
		from persian_calendar.jalali_support.datetime_normalizer import _sanitize_time_field

		row = frappe._dict(
			doctype="Purchase Receipt",
			name="MAT-PRE-TEST-TIME",
			posting_time="Invalid date",
		)
		_sanitize_time_field(row, "posting_time")
		self.assertEqual(str(row.posting_time), "01:29:23")
		_get_value.assert_called_once_with("Purchase Receipt", "MAT-PRE-TEST-TIME", "posting_time")

	@patch(
		"persian_calendar.jalali_support.datetime_normalizer._is_jalali_enabled",
		return_value=True,
	)
	@patch("frappe.db.get_value", return_value=None)
	def test_time_fields_default_midnight_without_db_restore(self, _get_value, _enabled):
		"""When restore is unavailable, invalid Time falls back to midnight (not a throw)."""
		from persian_calendar.jalali_support.datetime_normalizer import _sanitize_time_field

		row = frappe._dict(
			doctype="Purchase Receipt",
			name="MAT-PRE-MISSING",
			posting_time="Invalid date",
		)
		_sanitize_time_field(row, "posting_time")
		self.assertEqual(str(row.posting_time), "00:00:00")

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
