"""Integrated Business Calendar module registry (Phase 4b).

Single source of truth for what is patched, rebound, documented, and tested.
Does not change runtime patch application — ``apply_calendar_patches`` remains
the lifecycle entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ModuleStatus = Literal[
	"implemented",
	"deferred",
	"helper_rebind_only",
	"public_utility",
	"display_covered",
]


@dataclass(frozen=True)
class IntegratedModule:
	"""Descriptor for one Business Calendar integration."""

	name: str
	status: ModuleStatus
	patch_targets: tuple[str, ...]
	consumers: tuple[str, ...] = ()
	supported_periods: tuple[str, ...] = ()
	documentation: str = ""
	compatibility_note: str = ""
	diagnostics_ids: tuple[str, ...] = ()
	mechanism: str = ""
	notes: str = ""


# Registry — keep in sync with patches.py / contracts.py / docs
INTEGRATED_MODULES: tuple[IntegratedModule, ...] = (
	IntegratedModule(
		name="toshamshi / toshamsi conversion",
		status="public_utility",
		patch_targets=(),
		consumers=(
			"Jinja Print Formats (hooks.jinja.methods)",
			"PDF / email Notification Jinja",
			"brace templates (toshamshi only)",
			"persian_calendar.utils.data_io export",
			"erpnext_extensions voucher GL print",
		),
		documentation="docs/TOSHAMSHI.md",
		compatibility_note="Contracts: api.toshamshi, api.toshamsi, utils.jalali.toshamshi",
		diagnostics_ids=("api.toshamshi", "api.toshamsi", "utils.jalali.toshamshi"),
		mechanism="Single implementation in utils.jalali; re-exported via persian_calendar.api; "
		"toshamsi is an identity alias",
		notes="Display/conversion only — not a Business Calendar period engine; "
		"does not consult Display Calendar or Company Business Calendar.",
	),
	IntegratedModule(
		name="Financial Statements",
		status="implemented",
		patch_targets=("erpnext.accounts.report.financial_statements.get_period_list",),
		consumers=(
			"erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement",
			"erpnext.accounts.report.balance_sheet.balance_sheet",
			"erpnext.accounts.report.cash_flow.cash_flow",
			# … full list in patches.GET_PERIOD_LIST_CONSUMERS
		),
		supported_periods=("Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/business_period_engine.md",
		compatibility_note="Contract: fs.get_period_list",
		diagnostics_ids=("fs.get_period_list",),
		mechanism="apply_calendar_patches free-function + identity rebind",
	),
	IntegratedModule(
		name="Assets / Depreciation",
		status="implemented",
		patch_targets=(
			"override_doctype_class:Asset Depreciation Schedule",
			"override_doctype_class:Asset",
			"erpnext.assets.doctype.asset.depreciation.disposal_was_made_on_original_schedule_date",
		),
		documentation="docs/asset_business_calendar_integration.md",
		mechanism="override_doctype_class + narrow disposal patch (outside applicator)",
		notes="Uses CalendarEngine stepping; not BusinessPeriodEngine lists.",
	),
	IntegratedModule(
		name="Budget",
		status="implemented",
		patch_targets=("override_doctype_class:Budget.get_budget_periods",),
		supported_periods=("Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/budget_business_calendar.md",
		compatibility_note="Contract: budget.Budget.get_budget_periods",
		diagnostics_ids=("budget.Budget.get_budget_periods",),
		mechanism="override_doctype_class → PersianCalendarBudget",
	),
	IntegratedModule(
		name="Monthly Distribution",
		status="implemented",
		patch_targets=(
			"erpnext.accounts.doctype.monthly_distribution.monthly_distribution.get_periodwise_distribution_data",
			"erpnext.accounts.doctype.monthly_distribution.monthly_distribution.get_percentage",
		),
		documentation="docs/budget_business_calendar.md",
		compatibility_note="Contracts: md.get_periodwise_distribution_data, md.get_percentage",
		diagnostics_ids=("md.get_periodwise_distribution_data", "md.get_percentage"),
		mechanism="DocType override + free-function patches",
		notes="Calendar-neutral idx slots; not period-list generation.",
	),
	IntegratedModule(
		name="Trends",
		status="implemented",
		patch_targets=(
			"erpnext.controllers.trends.get_period_date_ranges",
			"erpnext.controllers.trends.period_wise_columns_query",
		),
		consumers=(
			"erpnext.accounts.report.budget_variance_report.budget_variance_report",
			"erpnext.accounts.report.purchase_invoice_trends.purchase_invoice_trends",
			"erpnext.accounts.report.sales_invoice_trends.sales_invoice_trends",
			"erpnext.buying.report.purchase_order_trends.purchase_order_trends",
			"erpnext.selling.report.sales_order_trends.sales_order_trends",
			"erpnext.selling.report.quotation_trends.quotation_trends",
			"erpnext.stock.report.purchase_receipt_trends.purchase_receipt_trends",
			"erpnext.stock.report.delivery_note_trends.delivery_note_trends",
		),
		supported_periods=("Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/budget_variance_trends.md",
		compatibility_note="Contracts: trends.get_period_date_ranges, trends.period_wise_columns_query",
		diagnostics_ids=("trends.get_period_date_ranges", "trends.period_wise_columns_query"),
		mechanism="apply_calendar_patches",
	),
	IntegratedModule(
		name="Budget Variance",
		status="implemented",
		patch_targets=("erpnext.accounts.report.budget_variance_report.budget_variance_report.execute",),
		supported_periods=("Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/budget_variance_trends.md",
		compatibility_note="Contract: bvr.execute",
		diagnostics_ids=("bvr.execute",),
		mechanism="execute adapter (Trends ranges alone insufficient)",
	),
	IntegratedModule(
		name="Sales Analytics",
		status="implemented",
		patch_targets=(
			"erpnext.selling.report.sales_analytics.sales_analytics.Analytics.get_period_date_ranges",
			"Analytics.get_period",
			"Analytics.get_columns",
			"Analytics.get_chart_data",
			"Analytics.update_company_list_for_parent_company",
		),
		supported_periods=("Weekly→stock", "Monthly", "Quarterly", "Yearly"),
		documentation="docs/sales_purchase_analytics.md",
		compatibility_note="Contracts: sa.Analytics.*",
		diagnostics_ids=(
			"sa.Analytics.get_period_date_ranges",
			"sa.Analytics.get_period",
			"sa.Analytics.get_columns",
			"sa.Analytics.get_chart_data",
		),
		mechanism="Class-method replacement; covers Purchase Analytics",
	),
	IntegratedModule(
		name="Purchase Analytics",
		status="implemented",
		patch_targets=("shares sales_analytics.Analytics",),
		supported_periods=("Weekly→stock", "Monthly", "Quarterly", "Yearly"),
		documentation="docs/sales_purchase_analytics.md",
		mechanism="Same class object as Sales Analytics — no second patch",
	),
	IntegratedModule(
		name="Stock Analytics",
		status="implemented",
		patch_targets=(
			"erpnext.stock.report.stock_analytics.stock_analytics.get_period_date_ranges",
			"get_period",
			"get_period_columns",
		),
		consumers=(
			"erpnext.manufacturing.report.production_analytics.production_analytics",
			"erpnext.manufacturing.report.work_order_summary.work_order_summary",
			"erpnext.manufacturing.report.job_card_summary.job_card_summary",
		),
		supported_periods=("Weekly→stock", "Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/stock_analytics.md",
		compatibility_note="Contracts: stk.*; round_down captured not replaced",
		diagnostics_ids=(
			"stk.get_period_date_ranges",
			"stk.get_period",
			"stk.get_period_columns",
			"stk.round_down_to_nearest_frequency",
		),
		mechanism="Free-function patches + manufacturing identity rebind",
	),
	IntegratedModule(
		name="Production Analytics",
		status="helper_rebind_only",
		patch_targets=(),
		consumers=("rebinds Stock Analytics helpers",),
		documentation="docs/stock_analytics.md",
		mechanism="Identity rebind only — not core MRP",
		notes="Phase 6B audit: confirmed only Stock period-helper consumer path; see docs/MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md",
	),
	IntegratedModule(
		name="Work Order Summary",
		status="helper_rebind_only",
		patch_targets=(),
		documentation="docs/stock_analytics.md",
		mechanism="Identity rebind of Stock period helpers",
		notes="Phase 6B: no additional adapter required",
	),
	IntegratedModule(
		name="Job Card Summary",
		status="helper_rebind_only",
		patch_targets=(),
		documentation="docs/stock_analytics.md",
		mechanism="Identity rebind of Stock period helpers",
		notes="Phase 6B: no additional adapter required",
	),
	IntegratedModule(
		name="Stock / Manufacturing Display Calendar",
		status="display_covered",
		patch_targets=(),
		documentation="docs/MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md",
		mechanism="Global desk Display Calendar on standard Date/Datetime fields",
		notes="Phase 6B: ledger/balance/ageing/BOM reports inherit Display Calendar; no domain display adapters",
	),
	IntegratedModule(
		name="Exponential Smoothing Forecasting",
		status="deferred",
		patch_targets=(),
		documentation="docs/MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md",
		notes="Uses get_period_list without company (always Gregorian BC). Deferred to Forecast Phase 3e. "
		"Already in GET_PERIOD_LIST_CONSUMERS for rebind.",
	),
	IntegratedModule(
		name="CRM Display Calendar",
		status="display_covered",
		patch_targets=(),
		consumers=(
			"Lead / Opportunity / Appointment / Email Campaign / CRM Note / Contract forms & lists",
			"CRM Query Report Date filters and Date columns",
			"Communication / Event / ToDo in CRM context",
		),
		documentation="docs/CRM_DISPLAY_CALENDAR.md",
		compatibility_note="Inherits global desk Display Calendar; no CRM-specific display adapters",
		diagnostics_ids=(),
		mechanism="jalali_support.bundle.js + datetime_normalizer; explicit toshamshi for print/email",
		notes="Limitations: First Response chart ISO axis; Appointment email format_datetime; "
		"standard print formatdate. Not a Business Calendar integration.",
	),
	IntegratedModule(
		name="CRM Pipeline Analytics",
		status="implemented",
		patch_targets=("erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics.execute",),
		supported_periods=("Monthly", "Quarterly"),
		documentation="docs/CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md",
		compatibility_note="Contract: spa.execute — Business date expected_closing; Company filter",
		diagnostics_ids=("spa.execute",),
		mechanism="Module execute wrap; Gregorian → stock; Jalali → BusinessPeriodEngine allocation",
		notes="Display filters unchanged (5A-2). No Weekly/Half-Yearly/Yearly in upstream UI.",
	),
	IntegratedModule(
		name="HRMS Vehicle Expenses",
		status="implemented",
		patch_targets=("hrms.hr.report.vehicle_expenses.vehicle_expenses.get_chart_data",),
		supported_periods=("Monthly",),
		documentation="docs/HRMS_BUSINESS_CALENDAR.md",
		compatibility_note="Contract: hrms.vehicle_expenses.get_chart_data; reuses FS get_period_list",
		diagnostics_ids=("hrms.vehicle_expenses.get_chart_data",),
		mechanism="get_chart_data wrap + Company filter (JS); pass company into get_period_list",
		notes="Only HRMS report with Monthly period list. Soft-skip if HRMS not installed. "
		"Company filter resolves Business Calendar for chart only; table rows unchanged.",
	),
	IntegratedModule(
		name="Fixed Asset Register",
		status="implemented",
		patch_targets=("erpnext.assets.report.fixed_asset_register.fixed_asset_register.prepare_chart_data",),
		supported_periods=("Monthly",),
		documentation="docs/RELEASE_2_0_0.md",
		compatibility_note="Contract: far.prepare_chart_data — allocate by period bounds",
		diagnostics_ids=("far.prepare_chart_data",),
		mechanism="prepare_chart_data wrap; Gregorian → stock; Jalali → date-bound aggregation",
		notes="Fixes Asset Value Analytics KeyError when FS get_period_list returns Jalali labels.",
	),
	IntegratedModule(
		name="HRMS Display Calendar",
		status="display_covered",
		patch_targets=(),
		documentation="docs/HRMS_BUSINESS_CALENDAR.md",
		mechanism="Global desk Display Calendar on standard Date/Datetime fields",
		notes="No HRMS-specific display adapters. Payroll month Select (1-12) remains Gregorian UI.",
	),
	IntegratedModule(
		name="HRMS Payroll / Attendance period reports",
		status="deferred",
		patch_targets=(),
		documentation="docs/HRMS_BUSINESS_CALENDAR.md",
		notes="Monthly Attendance day-grid; payroll month+year Extract filters; Payroll Period DocType — not BusinessPeriodEngine lists",
	),
	IntegratedModule(
		name="Issue Analytics",
		status="deferred",
		patch_targets=(),
	),
	IntegratedModule(
		name="MRP / MPS",
		status="deferred",
		patch_targets=(),
		documentation="docs/MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md",
		notes="Phase 6B: MRP Report bucket view uses Gregorian get_first_day/add_months planning "
		"columns — not BusinessPeriodEngine. Stock Analytics manufacturing rebinds are not MRP.",
	),
)


def modules_by_status(status: ModuleStatus) -> list[IntegratedModule]:
	return [m for m in INTEGRATED_MODULES if m.status == status]


def implemented_modules() -> list[IntegratedModule]:
	return [m for m in INTEGRATED_MODULES if m.status in ("implemented", "helper_rebind_only")]


def registry_as_dict() -> list[dict]:
	out = []
	for m in INTEGRATED_MODULES:
		out.append(
			{
				"name": m.name,
				"status": m.status,
				"patch_targets": list(m.patch_targets),
				"consumers": list(m.consumers),
				"supported_periods": list(m.supported_periods),
				"documentation": m.documentation,
				"compatibility_note": m.compatibility_note,
				"diagnostics_ids": list(m.diagnostics_ids),
				"mechanism": m.mechanism,
				"notes": m.notes,
			}
		)
	return out
