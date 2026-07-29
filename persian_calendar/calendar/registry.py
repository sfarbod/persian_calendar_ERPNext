"""Integrated Business Calendar module registry (Phase 4b).

Single source of truth for what is patched, rebound, documented, and tested.
Does not change runtime patch application — ``apply_calendar_patches`` remains
the lifecycle entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ModuleStatus = Literal["implemented", "deferred", "helper_rebind_only"]


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
		patch_targets=("erpnext.controllers.trends.get_period_date_ranges",),
		consumers=("erpnext.accounts.report.budget_variance_report.budget_variance_report",),
		supported_periods=("Monthly", "Quarterly", "Half-Yearly", "Yearly"),
		documentation="docs/budget_variance_trends.md",
		compatibility_note="Contract: trends.get_period_date_ranges — NOT Stock/Sales",
		diagnostics_ids=("trends.get_period_date_ranges",),
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
		notes="Deferred: core MRP/MPS",
	),
	IntegratedModule(
		name="Work Order Summary",
		status="helper_rebind_only",
		patch_targets=(),
		documentation="docs/stock_analytics.md",
		mechanism="Identity rebind of Stock period helpers",
	),
	IntegratedModule(
		name="Job Card Summary",
		status="helper_rebind_only",
		patch_targets=(),
		documentation="docs/stock_analytics.md",
		mechanism="Identity rebind of Stock period helpers",
	),
	IntegratedModule(
		name="CRM Pipeline Analytics",
		status="deferred",
		patch_targets=(),
		notes="Explicit non-goal until a dedicated phase",
	),
	IntegratedModule(
		name="Issue Analytics",
		status="deferred",
		patch_targets=(),
	),
	IntegratedModule(
		name="HRMS",
		status="deferred",
		patch_targets=(),
	),
	IntegratedModule(
		name="MRP / MPS",
		status="deferred",
		patch_targets=(),
		notes="Manufacturing helper rebinds are not MRP",
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
