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
