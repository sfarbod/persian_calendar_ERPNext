"""Official adapter template for future Business Calendar integrations.

Copy this module as a starting point. Fill in the TODOs. Do **not** import this
module from production code — it is documentation-as-code.

Checklist (see docs/SDK.md):

1. Audit installed ERPNext source (signatures, consumers).
2. Add ``CallableContract`` entries in ``contracts.py``.
3. Register the module in ``registry.py``.
4. Wire capture + install into ``apply_calendar_patches``.
5. Gregorian → captured original; Jalali → ``BusinessPeriodEngine``.
6. Weekly (if applicable) → always stock.
7. Never use Display Calendar for math.
8. Add focused tests + upgrade guide note.
"""

from __future__ import annotations

# --- TEMPLATE (illustrative; not executed) ---------------------------------
#
# from persian_calendar.api import (
#     BusinessPeriodEngine,
#     CalendarEngine,
#     build_jalali_periods,
#     capture_original,
#     get_business_calendar_for_company,
#     install_adapter,
#     lookup_period_key,
#     period_bounds_index,
#     rebind_consumers,
#     report_locale,
#     should_use_jalali_engine,
# )
#
# TARGET_MODULE = "erpnext.example.report.example_report"
# CONSUMERS: tuple[str, ...] = ()
# _ALLOWED = frozenset({"Monthly", "Quarterly", "Yearly"})
#
# _original = None
#
# def set_original(fn):
#     global _original
#     if _original is None:
#         _original = fn
#
# def adapted_get_period_date_ranges(filters):
#     if _original is None:
#         frappe.throw("Call apply_calendar_patches() first")
#     company = filters.get("company")
#     if not should_use_jalali_engine(
#         company=company,
#         rang=filters.get("range"),
#         allowed_ranges=_ALLOWED,
#         get_bc=get_business_calendar_for_company,
#     ):
#         return _original(filters)
#     periods = build_jalali_periods(
#         filters.from_date, filters.to_date, filters.range, company
#     )
#     # TODO: map BusinessPeriod → stock return shape (THIS IS REPORT-SPECIFIC)
#     return [[bp.from_date, bp.to_date] for bp in periods]
#
# # In patches.apply_calendar_patches:
# #   original = capture_original(TARGET_MODULE, "get_period_date_ranges", adapter=adapted_...)
# #   set_original(original)
# #   install_adapter(TARGET_MODULE, "get_period_date_ranges", adapted_...)
# #   rebind_consumers(original, adapted_..., "get_period_date_ranges", CONSUMERS)

TEMPLATE_STEPS = (
	"Audit ERPNext source for the target callable and direct importers",
	"Declare CallableContract in calendar/contracts.py",
	"Add IntegratedModule row in calendar/registry.py",
	"Implement adapter using persian_calendar.api helpers",
	"Register in apply_calendar_patches (capture once, install, rebind)",
	"Gregorian + Weekly → captured original; Jalali → BusinessPeriodEngine",
	"Add tests (parity, Jalali, lifecycle, Display independence)",
	"Document module note + update Compatibility Matrix",
)

ADAPTER_REQUIRED_PIECES = (
	"Target function / method",
	"Gregorian delegate (captured original)",
	"BusinessPeriodEngine call for Jalali supported periods",
	"Result mapper to stock return shape",
	"Consumer list for identity rebind (if any)",
	"Documentation",
)
