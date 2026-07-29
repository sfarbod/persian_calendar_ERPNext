"""Stable public API for the Business Calendar Framework (Phase 4b).

Import from ``persian_calendar.api`` in application code and future adapters.
Internal packages under ``persian_calendar.calendar.integrations`` remain
implementation details unless listed here.

Public surface is intentionally small. Prefer these entry points over deep
imports so upgrades can preserve compatibility.
"""

from __future__ import annotations

from persian_calendar.calendar.adapter_helpers import (
	build_jalali_periods,
	lookup_period_key,
	period_bounds_index,
	report_locale,
	resolve_business_calendar,
	should_use_jalali_engine,
	snap_jalali_range_start,
)
from persian_calendar.calendar.compatibility import (
	VALIDATED_ERPNEXT,
	VALIDATED_FRAPPE,
	CompatibilityStatus,
	detect_compatibility,
)
from persian_calendar.calendar.diagnostics import (
	ReleaseLevel,
	release_check,
	report_as_dict,
)
from persian_calendar.calendar.diagnostics import (
	run as run_diagnostics,
)
from persian_calendar.calendar.engine import CalendarEngine
from persian_calendar.calendar.patch_sdk import (
	capture_original,
	install_adapter,
	rebind_consumers,
)
from persian_calendar.calendar.patches import (
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
)
from persian_calendar.calendar.period_engine import BusinessPeriod, BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label
from persian_calendar.calendar.provider import CalendarProvider
from persian_calendar.calendar.registry import (
	INTEGRATED_MODULES,
	implemented_modules,
	registry_as_dict,
)
from persian_calendar.calendar.resolve import (
	BUSINESS_CALENDAR_GREGORIAN,
	BUSINESS_CALENDAR_JALALI,
	VALID_BUSINESS_CALENDARS,
	clear_business_calendar_cache,
	get_business_calendar_for_company,
	normalize_business_calendar,
)

__all__ = [
	"BUSINESS_CALENDAR_GREGORIAN",
	"BUSINESS_CALENDAR_JALALI",
	"INTEGRATED_MODULES",
	"VALIDATED_ERPNEXT",
	"VALIDATED_FRAPPE",
	"VALID_BUSINESS_CALENDARS",
	"BusinessPeriod",
	"BusinessPeriodEngine",
	"CalendarEngine",
	"CalendarProvider",
	"CompatibilityStatus",
	"PatchStatus",
	"ReleaseLevel",
	"apply_calendar_patches",
	"build_jalali_periods",
	"capture_original",
	"clear_business_calendar_cache",
	"detect_compatibility",
	"format_period_label",
	"get_business_calendar_for_company",
	"get_patch_state",
	"implemented_modules",
	"install_adapter",
	"lookup_period_key",
	"normalize_business_calendar",
	"period_bounds_index",
	"rebind_consumers",
	"registry_as_dict",
	"release_check",
	"report_as_dict",
	"report_locale",
	"resolve_business_calendar",
	"run_diagnostics",
	"should_use_jalali_engine",
	"snap_jalali_range_start",
]
