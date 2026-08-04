"""Gregorian Display Calendar — ControlDatetime sync_datepicker_state invariant.

Frappe ≥16.29 ControlDatetime.set_formatted_input calls this.sync_datepicker_state.
JalaliControlDatetime inherits through ControlDate, so Gregorian delegation must
explicitly expose ControlDatetime-only methods. Missing sync_datepicker_state
blanked Job Card (and any Datetime-heavy form) for Gregorian Display Calendar users.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


_PC_JS = (
	Path(__file__).resolve().parents[1]
	/ "public"
	/ "js"
	/ "jalali_support"
	/ "persian_calendar.js"
)


class TestGregorianDatetimeControlInvariant(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.source = _PC_JS.read_text(encoding="utf-8")

	def test_jalali_control_datetime_defines_sync_datepicker_state(self):
		# Class body must own the method (not only comments).
		cls_match = re.search(
			r"class\s+JalaliControlDatetime\s+extends\s+JalaliControlDate\s*\{(?P<body>.*?)\n\s*frappe\.ui\.form\.ControlDatetime\s*=",
			self.source,
			re.S,
		)
		self.assertIsNotNone(cls_match, "JalaliControlDatetime class not found")
		body = cls_match.group("body")
		self.assertIn("sync_datepicker_state(", body)
		self.assertIn(
			"BaseControlDatetime.prototype.sync_datepicker_state",
			body,
			"Must delegate to captured Frappe ControlDatetime implementation",
		)

	def test_upstream_frappe_still_calls_sync_datepicker_state(self):
		"""Guard: if upstream removes the call, this regression may be obsolete."""
		bench_apps = Path(__file__).resolve().parents[3]
		frappe_dt = (
			bench_apps
			/ "frappe"
			/ "frappe"
			/ "public"
			/ "js"
			/ "frappe"
			/ "form"
			/ "controls"
			/ "datetime.js"
		)
		if not frappe_dt.is_file():
			self.skipTest("Frappe datetime.js not found beside app")
		text = frappe_dt.read_text(encoding="utf-8")
		self.assertIn("sync_datepicker_state(", text)
		self.assertIn("this.sync_datepicker_state(", text)

	def test_job_card_time_log_uses_datetime_fields(self):
		"""Document why Job Card exposes the Gregorian Datetime bug first."""
		bench_apps = Path(__file__).resolve().parents[3]
		jc_json = (
			bench_apps
			/ "erpnext"
			/ "erpnext"
			/ "manufacturing"
			/ "doctype"
			/ "job_card_time_log"
			/ "job_card_time_log.json"
		)
		if not jc_json.is_file():
			self.skipTest("ERPNext Job Card Time Log JSON not found")
		text = jc_json.read_text(encoding="utf-8")
		self.assertIn('"from_time"', text)
		self.assertIn('"to_time"', text)
		self.assertIn('"Datetime"', text)
