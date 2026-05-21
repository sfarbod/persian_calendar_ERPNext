# Copyright (c) 2025, Persian Calendar Contributors
"""Desk bootinfo: effective calendar for synchronous JS preference checks."""

from __future__ import annotations

import frappe


def extend_bootinfo(bootinfo):
	try:
		from persian_calendar.jalali_support.doctype.jalali_settings.jalali_settings import (
			JalaliSettings,
		)

		settings = JalaliSettings.get_settings()
		effective = JalaliSettings.get_effective_calendar()
		user_pref = "System Default"
		if frappe.session.user and frappe.session.user != "Guest":
			user_pref = (
				frappe.db.get_value("User", frappe.session.user, "calendar_preference")
				or "System Default"
			)
		bootinfo["persian_calendar"] = {
			"enabled": bool(settings.enabled),
			"calendar_preference": user_pref,
			"default_calendar": settings.default_calendar,
			"display_calendar": effective.get("display_calendar", "Gregorian"),
			"week_start": effective.get("week_start", 6),
			"week_end": effective.get("week_end", 5),
		}
	except Exception:
		bootinfo["persian_calendar"] = {
			"enabled": False,
			"calendar_preference": "System Default",
			"default_calendar": "Jalali",
			"display_calendar": "Gregorian",
			"week_start": 0,
			"week_end": 6,
		}
