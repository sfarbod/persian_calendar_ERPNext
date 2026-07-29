"""Central Calendar Framework compatibility patch applicator.

BusinessPeriodEngine owns period arithmetic. This module only attaches
ERPNext v16 compatibility boundaries so stock free functions can consume
the framework without editing ERPNext source.

Lifecycle: register thin wrappers on before_request, before_job, and
before_tests. There is no supported Frappe hook for ``bench execute`` /
console — call :func:`apply_calendar_patches` explicitly in those contexts.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from types import ModuleType
from typing import Any

logger = logging.getLogger("persian_calendar.calendar.patches")


class PatchStatus(str, Enum):
	NOT_ATTEMPTED = "not_attempted"
	APPLIED = "applied"
	SOURCE_UNAVAILABLE = "source_unavailable"
	PARTIAL_REBIND = "partial_rebind"
	FAILED = "failed"


# Verified ERPNext v16 modules that do:
#   from erpnext.accounts.report.financial_statements import get_period_list
GET_PERIOD_LIST_CONSUMERS: tuple[str, ...] = (
	"erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement",
	"erpnext.accounts.report.balance_sheet.balance_sheet",
	"erpnext.accounts.report.cash_flow.cash_flow",
	"erpnext.accounts.report.gross_and_net_profit_report.gross_and_net_profit_report",
	"erpnext.accounts.report.financial_ratios.financial_ratios",
	"erpnext.accounts.report.deferred_revenue_and_expense.deferred_revenue_and_expense",
	"erpnext.accounts.doctype.financial_report_template.financial_report_engine",
	"erpnext.manufacturing.report.exponential_smoothing_forecasting.exponential_smoothing_forecasting",
	"erpnext.assets.report.fixed_asset_register.fixed_asset_register",
	"erpnext.selling.report.sales_partner_target_variance_based_on_item_group.item_group_wise_sales_target_variance",
	# Test module — rebound when loaded so ERPNext suite sees the adapter
	"erpnext.accounts.report.profit_and_loss_statement.test_profit_and_loss_statement",
)

FS_MODULE_PATH = "erpnext.accounts.report.financial_statements"
MD_MODULE_PATH = "erpnext.accounts.doctype.monthly_distribution.monthly_distribution"
TRENDS_MODULE_PATH = "erpnext.controllers.trends"
BVR_MODULE_PATH = "erpnext.accounts.report.budget_variance_report.budget_variance_report"
SPA_MODULE_PATH = "erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics"
SALES_ANALYTICS_MODULE_PATH = "erpnext.selling.report.sales_analytics.sales_analytics"
STOCK_ANALYTICS_MODULE_PATH = "erpnext.stock.report.stock_analytics.stock_analytics"

# Verified importers of get_periodwise_distribution_data
MD_PERIODWISE_CONSUMERS: tuple[str, ...] = (
	"erpnext.selling.report.sales_partner_target_variance_based_on_item_group.item_group_wise_sales_target_variance",
)

# Verified direct importers of trends.get_period_date_ranges (ERPNext v16.29).
# Same-module callers (period_wise_columns_query, get_period_month_ranges) need no rebind.
# Do NOT include stock_analytics / sales_analytics — those define their own functions.
TRENDS_PERIOD_RANGES_CONSUMERS: tuple[str, ...] = (
	"erpnext.accounts.report.budget_variance_report.budget_variance_report",
)

# Verified direct importers of stock_analytics period helpers (ERPNext v16.29).
# warehouse_wise_item_balance_age_and_value imports data helpers only — not rebound.
STOCK_ANALYTICS_PERIOD_CONSUMERS: tuple[str, ...] = (
	"erpnext.manufacturing.report.production_analytics.production_analytics",
	"erpnext.manufacturing.report.work_order_summary.work_order_summary",
	"erpnext.manufacturing.report.job_card_summary.job_card_summary",
)

# Attributes rebound on known Stock Analytics consumers (identity match only).
STOCK_ANALYTICS_REBIND_ATTRS: tuple[str, ...] = (
	"get_period_date_ranges",
	"get_period",
	"get_period_columns",
)


@dataclass
class PatchState:
	"""Process-local status for Calendar Framework compatibility patches."""

	status: PatchStatus = PatchStatus.NOT_ATTEMPTED
	# Financial Statements get_period_list
	original_get_period_list: Callable[..., Any] | None = None
	adapter_get_period_list: Callable[..., Any] | None = None
	rebound_modules: list[str] = field(default_factory=list)
	# Monthly Distribution free functions
	original_get_periodwise_distribution_data: Callable[..., Any] | None = None
	adapter_get_periodwise_distribution_data: Callable[..., Any] | None = None
	original_get_percentage: Callable[..., Any] | None = None
	adapter_get_percentage: Callable[..., Any] | None = None
	md_rebound_modules: list[str] = field(default_factory=list)
	# Trends get_period_date_ranges
	original_get_period_date_ranges: Callable[..., Any] | None = None
	adapter_get_period_date_ranges: Callable[..., Any] | None = None
	trends_rebound_modules: list[str] = field(default_factory=list)
	# Budget Variance report execute
	original_budget_variance_execute: Callable[..., Any] | None = None
	adapter_budget_variance_execute: Callable[..., Any] | None = None
	# Sales Pipeline Analytics execute (CRM)
	original_sales_pipeline_execute: Callable[..., Any] | None = None
	adapter_sales_pipeline_execute: Callable[..., Any] | None = None
	sales_pipeline_patched: bool = False
	# Sales / Purchase Analytics (shared Analytics class methods)
	original_sa_get_period_date_ranges: Callable[..., Any] | None = None
	original_sa_get_period: Callable[..., Any] | None = None
	original_sa_get_columns: Callable[..., Any] | None = None
	original_sa_get_chart_data: Callable[..., Any] | None = None
	original_sa_update_company_list: Callable[..., Any] | None = None
	sales_analytics_patched: bool = False
	# Stock Analytics free functions (+ manufacturing identity rebinds)
	original_stk_get_period_date_ranges: Callable[..., Any] | None = None
	original_stk_get_period: Callable[..., Any] | None = None
	original_stk_get_period_columns: Callable[..., Any] | None = None
	original_stk_round_down: Callable[..., Any] | None = None
	adapter_stk_get_period_date_ranges: Callable[..., Any] | None = None
	adapter_stk_get_period: Callable[..., Any] | None = None
	adapter_stk_get_period_columns: Callable[..., Any] | None = None
	stock_analytics_patched: bool = False
	stk_rebound_modules: list[str] = field(default_factory=list)
	last_error: str | None = None


_state = PatchState()


def get_patch_state() -> PatchState:
	"""Return the process-local patch state (for diagnostics and tests)."""
	return _state


def reset_calendar_patches_for_tests() -> None:
	"""Restore stock functions and clear process state (tests only)."""
	global _state
	if _state.original_get_period_list is not None:
		fs_mod = sys.modules.get(FS_MODULE_PATH)
		if fs_mod is not None and _state.adapter_get_period_list is not None:
			if getattr(fs_mod, "get_period_list", None) is _state.adapter_get_period_list:
				fs_mod.get_period_list = _state.original_get_period_list
			_restore_attr_consumers(
				_state.original_get_period_list,
				_state.adapter_get_period_list,
				"get_period_list",
				GET_PERIOD_LIST_CONSUMERS,
			)
	if _state.original_get_periodwise_distribution_data is not None:
		md_mod = sys.modules.get(MD_MODULE_PATH)
		if md_mod is not None and _state.adapter_get_periodwise_distribution_data is not None:
			if (
				getattr(md_mod, "get_periodwise_distribution_data", None)
				is _state.adapter_get_periodwise_distribution_data
			):
				md_mod.get_periodwise_distribution_data = _state.original_get_periodwise_distribution_data
			if (
				_state.adapter_get_percentage is not None
				and getattr(md_mod, "get_percentage", None) is _state.adapter_get_percentage
			):
				md_mod.get_percentage = _state.original_get_percentage
			_restore_attr_consumers(
				_state.original_get_periodwise_distribution_data,
				_state.adapter_get_periodwise_distribution_data,
				"get_periodwise_distribution_data",
				MD_PERIODWISE_CONSUMERS,
			)
	from persian_calendar.calendar.integrations import budget_variance as bvr_adapter_mod
	from persian_calendar.calendar.integrations import financial_statements as fs_adapter_mod
	from persian_calendar.calendar.integrations import monthly_distribution as md_adapter_mod
	from persian_calendar.calendar.integrations import sales_analytics as sa_adapter_mod
	from persian_calendar.calendar.integrations import sales_pipeline_analytics as spa_adapter_mod
	from persian_calendar.calendar.integrations import stock_analytics as stk_adapter_mod
	from persian_calendar.calendar.integrations import trends as trends_adapter_mod

	if _state.sales_analytics_patched and _state.original_sa_get_period_date_ranges is not None:
		sa_mod = sys.modules.get(SALES_ANALYTICS_MODULE_PATH)
		if sa_mod is not None and hasattr(sa_mod, "Analytics"):
			cls = sa_mod.Analytics
			if cls.get_period_date_ranges is sa_adapter_mod.get_period_date_ranges:
				cls.get_period_date_ranges = _state.original_sa_get_period_date_ranges
				cls.get_period = _state.original_sa_get_period
				cls.get_columns = _state.original_sa_get_columns
				cls.get_chart_data = _state.original_sa_get_chart_data
				cls.update_company_list_for_parent_company = _state.original_sa_update_company_list

	if _state.stock_analytics_patched and _state.original_stk_get_period_date_ranges is not None:
		stk_mod = sys.modules.get(STOCK_ANALYTICS_MODULE_PATH)
		if stk_mod is not None and _state.adapter_stk_get_period_date_ranges is not None:
			if getattr(stk_mod, "get_period_date_ranges", None) is _state.adapter_stk_get_period_date_ranges:
				stk_mod.get_period_date_ranges = _state.original_stk_get_period_date_ranges
				stk_mod.get_period = _state.original_stk_get_period
				stk_mod.get_period_columns = _state.original_stk_get_period_columns
			for attr, original, adapter in (
				(
					"get_period_date_ranges",
					_state.original_stk_get_period_date_ranges,
					_state.adapter_stk_get_period_date_ranges,
				),
				("get_period", _state.original_stk_get_period, _state.adapter_stk_get_period),
				(
					"get_period_columns",
					_state.original_stk_get_period_columns,
					_state.adapter_stk_get_period_columns,
				),
			):
				_restore_attr_consumers(original, adapter, attr, STOCK_ANALYTICS_PERIOD_CONSUMERS)

	if _state.original_get_period_date_ranges is not None:
		trends_mod = sys.modules.get(TRENDS_MODULE_PATH)
		if trends_mod is not None and _state.adapter_get_period_date_ranges is not None:
			if getattr(trends_mod, "get_period_date_ranges", None) is _state.adapter_get_period_date_ranges:
				trends_mod.get_period_date_ranges = _state.original_get_period_date_ranges
			_restore_attr_consumers(
				_state.original_get_period_date_ranges,
				_state.adapter_get_period_date_ranges,
				"get_period_date_ranges",
				TRENDS_PERIOD_RANGES_CONSUMERS,
			)

	if _state.original_budget_variance_execute is not None:
		bvr_mod = sys.modules.get(BVR_MODULE_PATH)
		if bvr_mod is not None and _state.adapter_budget_variance_execute is not None:
			if getattr(bvr_mod, "execute", None) is _state.adapter_budget_variance_execute:
				bvr_mod.execute = _state.original_budget_variance_execute

	if _state.original_sales_pipeline_execute is not None:
		spa_mod = sys.modules.get(SPA_MODULE_PATH)
		if spa_mod is not None and _state.adapter_sales_pipeline_execute is not None:
			if getattr(spa_mod, "execute", None) is _state.adapter_sales_pipeline_execute:
				spa_mod.execute = _state.original_sales_pipeline_execute

	fs_adapter_mod._original_get_period_list = None
	md_adapter_mod._original_get_periodwise_distribution_data = None
	md_adapter_mod._original_get_percentage = None
	trends_adapter_mod._original_get_period_date_ranges = None
	bvr_adapter_mod._original_execute = None
	spa_adapter_mod._original_execute = None
	sa_adapter_mod._original_get_period_date_ranges = None
	sa_adapter_mod._original_get_period = None
	sa_adapter_mod._original_get_columns = None
	sa_adapter_mod._original_get_chart_data = None
	sa_adapter_mod._original_update_company_list = None
	stk_adapter_mod._original_get_period_date_ranges = None
	stk_adapter_mod._original_get_period = None
	stk_adapter_mod._original_get_period_columns = None
	stk_adapter_mod._original_round_down = None
	_state = PatchState()


def apply_calendar_patches() -> PatchStatus:
	"""Apply all Calendar Framework compatibility patches for this process.

	Phase 3a: Financial Statements ``get_period_list``.
	Phase 3b: Monthly Distribution ``get_periodwise_distribution_data`` / ``get_percentage``.
	Phase 3c: Trends ``get_period_date_ranges`` + Budget Variance ``execute``.
	Phase 3d-1: Sales / Purchase Analytics ``Analytics`` methods.
	Phase 3d-2: Stock Analytics free functions + manufacturing rebinds.
	Phase 5A-3: Sales Pipeline Analytics ``execute``.

	Registered free-function / method targets (in order):
	FS ``get_period_list`` → MD periodwise/% → Trends ``get_period_date_ranges``
	→ BVR ``execute`` → Sales Analytics methods → Stock Analytics helpers
	→ Sales Pipeline Analytics ``execute``.

	Idempotent when already successfully applied. Retries after
	``SOURCE_UNAVAILABLE``, ``PARTIAL_REBIND``, or ``FAILED``.
	"""
	fs_status = _apply_get_period_list_patch()
	if fs_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		return fs_status

	md_status = _apply_monthly_distribution_patch()
	if md_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = md_status
		return md_status

	trends_status = _apply_trends_patch()
	if trends_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = trends_status
		return trends_status

	bvr_status = _apply_budget_variance_patch()
	if bvr_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = bvr_status
		return bvr_status

	sa_status = _apply_sales_analytics_patch()
	if sa_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = sa_status
		return sa_status

	stk_status = _apply_stock_analytics_patch()
	if stk_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = stk_status
		return stk_status

	spa_status = _apply_sales_pipeline_patch()
	if spa_status in (PatchStatus.FAILED, PatchStatus.SOURCE_UNAVAILABLE, PatchStatus.PARTIAL_REBIND):
		_state.status = spa_status
		return spa_status

	_state.status = PatchStatus.APPLIED
	_state.last_error = None
	return PatchStatus.APPLIED


def _apply_get_period_list_patch() -> PatchStatus:
	global _state

	from persian_calendar.calendar.integrations.financial_statements import get_period_list as adapter

	if (
		_state.status == PatchStatus.APPLIED
		and _state.original_get_period_list is not None
		and _state.adapter_get_period_list is adapter
	):
		fs_mod = sys.modules.get(FS_MODULE_PATH)
		if fs_mod is not None and getattr(fs_mod, "get_period_list", None) is adapter:
			# Re-run rebind in case new consumers were imported after apply
			rebound = _rebind_get_period_list_consumers(_state.original_get_period_list, adapter)
			for name in rebound:
				if name not in _state.rebound_modules:
					_state.rebound_modules.append(name)
			return PatchStatus.APPLIED

	try:
		import erpnext.accounts.report.financial_statements as fs_mod
	except ImportError as exc:
		_state.status = PatchStatus.SOURCE_UNAVAILABLE
		_state.last_error = f"ERPNext financial_statements unavailable: {exc}"
		logger.warning(_state.last_error)
		return _state.status

	current = fs_mod.get_period_list

	# Capture the real stock function exactly once — never capture the adapter.
	if _state.original_get_period_list is None:
		if current is adapter:
			_state.status = PatchStatus.FAILED
			_state.last_error = (
				"get_period_list is already the adapter but original was never captured; "
				"cannot safely patch"
			)
			logger.error(_state.last_error)
			return _state.status
		# Observability: Display-layer formatters may wrap get_period_list before
		# this applicator runs (hooks order). Capturing that wrapper is safe for
		# boundaries but may still rewrite labels from Display Calendar on the
		# Gregorian BC path — see Architecture Known Limitations.
		if getattr(current, "__name__", "") == "get_period_list_jalali":
			logger.warning(
				"Calendar FS patch: capturing Display-label get_period_list wrapper "
				"as original (formatters ran first); period boundaries remain stock/"
				"BC-adapter owned, labels may follow Display Calendar"
			)
		_state.original_get_period_list = current

	original = _state.original_get_period_list
	_state.adapter_get_period_list = adapter

	# Wire original into the adapter module so Gregorian path does not recurse.
	from persian_calendar.calendar.integrations import financial_statements as fs_adapter_mod

	fs_adapter_mod.set_original_get_period_list(original)

	if current is not adapter:
		fs_mod.get_period_list = adapter

	rebound = _rebind_get_period_list_consumers(original, adapter)
	_state.rebound_modules = list(dict.fromkeys(_state.rebound_modules + rebound))

	# Verify known loaded consumers no longer hold the stock function
	still_stock = _loaded_known_consumers_still_on_original(
		original, "get_period_list", GET_PERIOD_LIST_CONSUMERS
	)
	if still_stock:
		_state.status = PatchStatus.PARTIAL_REBIND
		_state.last_error = f"Failed to rebind get_period_list consumers: {', '.join(still_stock)}"
		logger.error(_state.last_error)
		return _state.status

	if rebound:
		logger.info("Calendar get_period_list patch applied; rebound: %s", ", ".join(rebound))
	else:
		logger.info("Calendar get_period_list patch applied (no preloaded consumers to rebind)")
	return PatchStatus.APPLIED


def _apply_monthly_distribution_patch() -> PatchStatus:
	"""Patch Monthly Distribution free functions used by sales target reports."""
	global _state

	from persian_calendar.calendar.integrations.monthly_distribution import (
		get_percentage as md_get_percentage,
	)
	from persian_calendar.calendar.integrations.monthly_distribution import (
		get_periodwise_distribution_data as md_periodwise,
	)
	from persian_calendar.calendar.integrations.monthly_distribution import set_original_md_functions

	if (
		_state.original_get_periodwise_distribution_data is not None
		and _state.adapter_get_periodwise_distribution_data is md_periodwise
	):
		md_mod = sys.modules.get(MD_MODULE_PATH)
		if md_mod is not None and getattr(md_mod, "get_periodwise_distribution_data", None) is md_periodwise:
			rebound = _rebind_named_consumers(
				_state.original_get_periodwise_distribution_data,
				md_periodwise,
				"get_periodwise_distribution_data",
				MD_PERIODWISE_CONSUMERS,
				MD_MODULE_PATH,
			)
			for name in rebound:
				if name not in _state.md_rebound_modules:
					_state.md_rebound_modules.append(name)
			return PatchStatus.APPLIED

	try:
		import erpnext.accounts.doctype.monthly_distribution.monthly_distribution as md_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext monthly_distribution unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	current_pw = md_mod.get_periodwise_distribution_data
	current_pct = md_mod.get_percentage

	if _state.original_get_periodwise_distribution_data is None:
		if current_pw is md_periodwise:
			_state.last_error = (
				"get_periodwise_distribution_data is already the adapter but original " "was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_get_periodwise_distribution_data = current_pw
		_state.original_get_percentage = current_pct

	original_pw = _state.original_get_periodwise_distribution_data
	original_pct = _state.original_get_percentage
	_state.adapter_get_periodwise_distribution_data = md_periodwise
	_state.adapter_get_percentage = md_get_percentage

	set_original_md_functions(original_pw, original_pct)

	if current_pw is not md_periodwise:
		md_mod.get_periodwise_distribution_data = md_periodwise
	if current_pct is not md_get_percentage:
		md_mod.get_percentage = md_get_percentage

	rebound = _rebind_named_consumers(
		original_pw,
		md_periodwise,
		"get_periodwise_distribution_data",
		MD_PERIODWISE_CONSUMERS,
		MD_MODULE_PATH,
	)
	_state.md_rebound_modules = list(dict.fromkeys(_state.md_rebound_modules + rebound))

	still = _loaded_known_consumers_still_on_original(
		original_pw, "get_periodwise_distribution_data", MD_PERIODWISE_CONSUMERS
	)
	if still:
		_state.last_error = f"Failed to rebind MD consumers: {', '.join(still)}"
		logger.error(_state.last_error)
		return PatchStatus.PARTIAL_REBIND

	if rebound:
		logger.info("Calendar MD patch applied; rebound: %s", ", ".join(rebound))
	else:
		logger.info("Calendar MD patch applied (no preloaded consumers to rebind)")
	return PatchStatus.APPLIED


def _apply_trends_patch() -> PatchStatus:
	"""Patch ``erpnext.controllers.trends.get_period_date_ranges``."""
	global _state

	from persian_calendar.calendar.integrations.trends import (
		get_period_date_ranges as adapter,
	)
	from persian_calendar.calendar.integrations.trends import (
		set_original_get_period_date_ranges,
	)

	if (
		_state.original_get_period_date_ranges is not None
		and _state.adapter_get_period_date_ranges is adapter
	):
		trends_mod = sys.modules.get(TRENDS_MODULE_PATH)
		if trends_mod is not None and getattr(trends_mod, "get_period_date_ranges", None) is adapter:
			rebound = _rebind_named_consumers(
				_state.original_get_period_date_ranges,
				adapter,
				"get_period_date_ranges",
				TRENDS_PERIOD_RANGES_CONSUMERS,
				TRENDS_MODULE_PATH,
			)
			for name in rebound:
				if name not in _state.trends_rebound_modules:
					_state.trends_rebound_modules.append(name)
			return PatchStatus.APPLIED

	try:
		import erpnext.controllers.trends as trends_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext trends unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	current = trends_mod.get_period_date_ranges

	if _state.original_get_period_date_ranges is None:
		if current is adapter:
			_state.last_error = (
				"get_period_date_ranges is already the adapter but original was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_get_period_date_ranges = current

	original = _state.original_get_period_date_ranges
	_state.adapter_get_period_date_ranges = adapter
	set_original_get_period_date_ranges(original)

	if current is not adapter:
		trends_mod.get_period_date_ranges = adapter

	rebound = _rebind_named_consumers(
		original,
		adapter,
		"get_period_date_ranges",
		TRENDS_PERIOD_RANGES_CONSUMERS,
		TRENDS_MODULE_PATH,
	)
	_state.trends_rebound_modules = list(dict.fromkeys(_state.trends_rebound_modules + rebound))

	still = _loaded_known_consumers_still_on_original(
		original, "get_period_date_ranges", TRENDS_PERIOD_RANGES_CONSUMERS
	)
	if still:
		_state.last_error = f"Failed to rebind Trends consumers: {', '.join(still)}"
		logger.error(_state.last_error)
		return PatchStatus.PARTIAL_REBIND

	if rebound:
		logger.info("Calendar Trends patch applied; rebound: %s", ", ".join(rebound))
	else:
		logger.info("Calendar Trends patch applied (no preloaded consumers to rebind)")
	return PatchStatus.APPLIED


def _apply_budget_variance_patch() -> PatchStatus:
	"""Patch Budget Variance ``execute`` — Trends ranges alone cannot fix month-name keys."""
	global _state

	from persian_calendar.calendar.integrations.budget_variance import execute as adapter
	from persian_calendar.calendar.integrations.budget_variance import (
		set_original_budget_variance_execute,
	)

	if (
		_state.original_budget_variance_execute is not None
		and _state.adapter_budget_variance_execute is adapter
	):
		bvr_mod = sys.modules.get(BVR_MODULE_PATH)
		if bvr_mod is not None and getattr(bvr_mod, "execute", None) is adapter:
			return PatchStatus.APPLIED

	try:
		import erpnext.accounts.report.budget_variance_report.budget_variance_report as bvr_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext budget_variance_report unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	current = bvr_mod.execute

	if _state.original_budget_variance_execute is None:
		if current is adapter:
			_state.last_error = (
				"budget_variance execute is already the adapter but original was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_budget_variance_execute = current

	original = _state.original_budget_variance_execute
	_state.adapter_budget_variance_execute = adapter
	set_original_budget_variance_execute(original)

	if current is not adapter:
		bvr_mod.execute = adapter

	logger.info("Calendar Budget Variance execute patch applied")
	return PatchStatus.APPLIED


def _apply_sales_analytics_patch() -> PatchStatus:
	"""Patch shared Sales Analytics ``Analytics`` methods (covers Purchase Analytics)."""
	global _state

	from persian_calendar.calendar.integrations import sales_analytics as sa_adapter
	from persian_calendar.calendar.integrations.sales_analytics import (
		set_original_sales_analytics_methods,
	)

	if _state.sales_analytics_patched and _state.original_sa_get_period_date_ranges is not None:
		sa_mod = sys.modules.get(SALES_ANALYTICS_MODULE_PATH)
		if sa_mod is not None and getattr(sa_mod.Analytics, "get_period_date_ranges", None) is (
			sa_adapter.get_period_date_ranges
		):
			return PatchStatus.APPLIED

	try:
		import erpnext.selling.report.sales_analytics.sales_analytics as sa_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext sales_analytics unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	cls = sa_mod.Analytics
	current_ranges = cls.get_period_date_ranges

	if _state.original_sa_get_period_date_ranges is None:
		if current_ranges is sa_adapter.get_period_date_ranges:
			_state.last_error = (
				"Analytics.get_period_date_ranges is already the adapter but original " "was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_sa_get_period_date_ranges = cls.get_period_date_ranges
		_state.original_sa_get_period = cls.get_period
		_state.original_sa_get_columns = cls.get_columns
		_state.original_sa_get_chart_data = cls.get_chart_data
		_state.original_sa_update_company_list = cls.update_company_list_for_parent_company

	set_original_sales_analytics_methods(
		_state.original_sa_get_period_date_ranges,
		_state.original_sa_get_period,
		_state.original_sa_get_columns,
		_state.original_sa_get_chart_data,
		_state.original_sa_update_company_list,
	)

	cls.get_period_date_ranges = sa_adapter.get_period_date_ranges
	cls.get_period = sa_adapter.get_period
	cls.get_columns = sa_adapter.get_columns
	cls.get_chart_data = sa_adapter.get_chart_data
	cls.update_company_list_for_parent_company = sa_adapter.update_company_list_for_parent_company
	_state.sales_analytics_patched = True

	# Purchase Analytics holds a reference to the Analytics class object — method
	# replacement on the class covers it. No separate free-function rebind.
	logger.info("Calendar Sales/Purchase Analytics Analytics methods patched")
	return PatchStatus.APPLIED


def _apply_stock_analytics_patch() -> PatchStatus:
	"""Patch Stock Analytics free functions and identity-rebind manufacturing importers.

	Target name in diagnostics: ``stock_analytics`` (not Trends, not Sales Analytics).
	``round_down_to_nearest_frequency`` is captured but NOT replaced on the module.
	"""
	global _state

	from persian_calendar.calendar.integrations import stock_analytics as stk_adapter
	from persian_calendar.calendar.integrations.stock_analytics import (
		set_original_stock_analytics_functions,
	)

	if (
		_state.stock_analytics_patched
		and _state.original_stk_get_period_date_ranges is not None
		and _state.adapter_stk_get_period_date_ranges is stk_adapter.get_period_date_ranges
	):
		stk_mod = sys.modules.get(STOCK_ANALYTICS_MODULE_PATH)
		if stk_mod is not None and getattr(stk_mod, "get_period_date_ranges", None) is (
			stk_adapter.get_period_date_ranges
		):
			rebound = _rebind_stock_analytics_consumers()
			for name in rebound:
				if name not in _state.stk_rebound_modules:
					_state.stk_rebound_modules.append(name)
			return PatchStatus.APPLIED

	try:
		import erpnext.stock.report.stock_analytics.stock_analytics as stk_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext stock_analytics unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	current_ranges = stk_mod.get_period_date_ranges

	if _state.original_stk_get_period_date_ranges is None:
		if current_ranges is stk_adapter.get_period_date_ranges:
			_state.last_error = (
				"stock_analytics.get_period_date_ranges is already the adapter but "
				"original was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_stk_get_period_date_ranges = stk_mod.get_period_date_ranges
		_state.original_stk_get_period = stk_mod.get_period
		_state.original_stk_get_period_columns = stk_mod.get_period_columns
		_state.original_stk_round_down = stk_mod.round_down_to_nearest_frequency

	set_original_stock_analytics_functions(
		_state.original_stk_get_period_date_ranges,
		_state.original_stk_get_period,
		_state.original_stk_get_period_columns,
		_state.original_stk_round_down,
	)

	_state.adapter_stk_get_period_date_ranges = stk_adapter.get_period_date_ranges
	_state.adapter_stk_get_period = stk_adapter.get_period
	_state.adapter_stk_get_period_columns = stk_adapter.get_period_columns

	if current_ranges is not stk_adapter.get_period_date_ranges:
		stk_mod.get_period_date_ranges = stk_adapter.get_period_date_ranges
	if stk_mod.get_period is not stk_adapter.get_period:
		stk_mod.get_period = stk_adapter.get_period
	if stk_mod.get_period_columns is not stk_adapter.get_period_columns:
		stk_mod.get_period_columns = stk_adapter.get_period_columns
	# Intentionally leave round_down_to_nearest_frequency as the stock original.

	_state.stock_analytics_patched = True

	rebound = _rebind_stock_analytics_consumers()
	_state.stk_rebound_modules = list(dict.fromkeys(_state.stk_rebound_modules + rebound))

	still = []
	for attr, original in (
		("get_period_date_ranges", _state.original_stk_get_period_date_ranges),
		("get_period", _state.original_stk_get_period),
		("get_period_columns", _state.original_stk_get_period_columns),
	):
		# Only check consumers that actually import this attribute
		for mod_name in STOCK_ANALYTICS_PERIOD_CONSUMERS:
			mod = sys.modules.get(mod_name)
			if mod is None:
				continue
			current = getattr(mod, attr, None)
			if current is None:
				continue
			if current is original:
				still.append(f"{mod_name}.{attr}")

	if still:
		_state.last_error = f"Failed to rebind Stock Analytics consumers: {', '.join(still)}"
		logger.error(_state.last_error)
		return PatchStatus.PARTIAL_REBIND

	if rebound:
		logger.info("Calendar Stock Analytics patch applied; rebound: %s", ", ".join(rebound))
	else:
		logger.info("Calendar Stock Analytics patch applied (no preloaded consumers to rebind)")
	return PatchStatus.APPLIED


def _apply_sales_pipeline_patch() -> PatchStatus:
	"""Patch Sales Pipeline Analytics ``execute`` for Jalali Business Calendar periods."""
	global _state

	from persian_calendar.calendar.integrations.sales_pipeline_analytics import execute as adapter
	from persian_calendar.calendar.integrations.sales_pipeline_analytics import (
		set_original_sales_pipeline_execute,
	)

	if (
		_state.original_sales_pipeline_execute is not None
		and _state.adapter_sales_pipeline_execute is adapter
	):
		spa_mod = sys.modules.get(SPA_MODULE_PATH)
		if spa_mod is not None and getattr(spa_mod, "execute", None) is adapter:
			return PatchStatus.APPLIED

	try:
		import erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics as spa_mod
	except ImportError as exc:
		_state.last_error = f"ERPNext sales_pipeline_analytics unavailable: {exc}"
		logger.warning(_state.last_error)
		return PatchStatus.SOURCE_UNAVAILABLE

	current = spa_mod.execute

	if _state.original_sales_pipeline_execute is None:
		if current is adapter:
			_state.last_error = (
				"sales_pipeline_analytics.execute is already the adapter but "
				"original was never captured"
			)
			logger.error(_state.last_error)
			return PatchStatus.FAILED
		_state.original_sales_pipeline_execute = current

	original = _state.original_sales_pipeline_execute
	_state.adapter_sales_pipeline_execute = adapter
	set_original_sales_pipeline_execute(original)

	if current is not adapter:
		spa_mod.execute = adapter

	_state.sales_pipeline_patched = True
	logger.info("Calendar Sales Pipeline Analytics execute patch applied")
	return PatchStatus.APPLIED


def _rebind_stock_analytics_consumers() -> list[str]:
	"""Identity-rebind known manufacturing importers of Stock Analytics helpers."""
	rebound: list[str] = []
	pairs = (
		(
			"get_period_date_ranges",
			_state.original_stk_get_period_date_ranges,
			_state.adapter_stk_get_period_date_ranges,
		),
		("get_period", _state.original_stk_get_period, _state.adapter_stk_get_period),
		(
			"get_period_columns",
			_state.original_stk_get_period_columns,
			_state.adapter_stk_get_period_columns,
		),
	)
	for mod_name in STOCK_ANALYTICS_PERIOD_CONSUMERS:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		changed = False
		for attr, original, adapter in pairs:
			if original is None or adapter is None:
				continue
			if _rebind_module_attr(mod, original, adapter, attr):
				changed = True
		if changed:
			rebound.append(mod_name)
	return rebound


def _rebind_get_period_list_consumers(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
) -> list[str]:
	return _rebind_named_consumers(
		original, adapter, "get_period_list", GET_PERIOD_LIST_CONSUMERS, FS_MODULE_PATH
	)


def _rebind_named_consumers(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
	attr_name: str,
	known_consumers: tuple[str, ...],
	source_module: str,
) -> list[str]:
	"""Rebind ``attr_name`` only where the attribute is the original stock function."""
	rebound: list[str] = []

	for mod_name in known_consumers:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if _rebind_module_attr(mod, original, adapter, attr_name):
			rebound.append(mod_name)

	for mod_name, mod in list(sys.modules.items()):
		if not mod_name.startswith("erpnext."):
			continue
		if mod_name == source_module:
			continue
		if mod_name in known_consumers:
			continue
		if not isinstance(mod, ModuleType):
			continue
		if _rebind_module_attr(mod, original, adapter, attr_name):
			rebound.append(mod_name)
			logger.info("Rebound unlisted erpnext consumer via identity scan: %s.%s", mod_name, attr_name)

	return rebound


def _rebind_module_attr(
	mod: ModuleType,
	original: Callable[..., Any],
	adapter: Callable[..., Any],
	attr_name: str = "get_period_list",
) -> bool:
	"""Replace ``mod.<attr_name>`` only if it is the original stock function object."""
	from persian_calendar.calendar.patch_sdk import rebind_module_attr

	return rebind_module_attr(mod, original, adapter, attr_name)


def _loaded_known_consumers_still_on_original(
	original: Callable[..., Any],
	attr_name: str,
	known_consumers: tuple[str, ...],
) -> list[str]:
	still = []
	for mod_name in known_consumers:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if getattr(mod, attr_name, None) is original:
			still.append(mod_name)
	return still


def _restore_attr_consumers(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
	attr_name: str,
	known_consumers: tuple[str, ...],
) -> None:
	for mod_name in list(known_consumers) + [n for n in sys.modules if n.startswith("erpnext.")]:
		mod = sys.modules.get(mod_name)
		if mod is None or not isinstance(mod, ModuleType):
			continue
		if getattr(mod, attr_name, None) is adapter:
			setattr(mod, attr_name, original)


# ---------------------------------------------------------------------------
# Thin Frappe hook wrappers — signatures verified against Frappe v16 source
# ---------------------------------------------------------------------------


def before_request_calendar_bootstrap() -> None:
	"""``before_request``: ``frappe.call(task)`` with no extra args (frappe/app.py)."""
	apply_calendar_patches()


def before_job_calendar_bootstrap(method=None, kwargs=None, transaction_type=None, **_extra) -> None:
	"""``before_job``: called with method=, kwargs=, transaction_type= (background_jobs.py)."""
	apply_calendar_patches()


def before_tests_calendar_bootstrap() -> None:
	"""``before_tests``: ``frappe.get_attr(hook)()`` with no args (testing/environment.py)."""
	apply_calendar_patches()
