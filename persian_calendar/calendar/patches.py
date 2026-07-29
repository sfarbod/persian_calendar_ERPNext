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
	from persian_calendar.calendar.integrations import trends as trends_adapter_mod

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

	fs_adapter_mod._original_get_period_list = None
	md_adapter_mod._original_get_periodwise_distribution_data = None
	md_adapter_mod._original_get_percentage = None
	trends_adapter_mod._original_get_period_date_ranges = None
	bvr_adapter_mod._original_execute = None
	_state = PatchState()


def apply_calendar_patches() -> PatchStatus:
	"""Apply all Calendar Framework compatibility patches for this process.

	Phase 3a: Financial Statements ``get_period_list``.
	Phase 3b: Monthly Distribution ``get_periodwise_distribution_data`` / ``get_percentage``.
	Phase 3c: Trends ``get_period_date_ranges`` + Budget Variance ``execute``.

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
	current = getattr(mod, attr_name, None)
	if current is None:
		return False
	if current is original:
		setattr(mod, attr_name, adapter)
		return True
	return False


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
