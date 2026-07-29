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
from dataclasses import dataclass, field
from enum import Enum
from types import ModuleType
from typing import Any, Callable

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


@dataclass
class PatchState:
	"""Process-local status for the get_period_list compatibility patch."""

	status: PatchStatus = PatchStatus.NOT_ATTEMPTED
	original_get_period_list: Callable[..., Any] | None = None
	adapter_get_period_list: Callable[..., Any] | None = None
	rebound_modules: list[str] = field(default_factory=list)
	last_error: str | None = None


_state = PatchState()


def get_patch_state() -> PatchState:
	"""Return the process-local patch state (for diagnostics and tests)."""
	return _state


def reset_calendar_patches_for_tests() -> None:
	"""Restore stock get_period_list and clear process state (tests only)."""
	global _state
	if _state.original_get_period_list is not None:
		fs_mod = sys.modules.get(FS_MODULE_PATH)
		if fs_mod is not None and _state.adapter_get_period_list is not None:
			if getattr(fs_mod, "get_period_list", None) is _state.adapter_get_period_list:
				fs_mod.get_period_list = _state.original_get_period_list
			_restore_consumers_to_original(_state.original_get_period_list, _state.adapter_get_period_list)
	from persian_calendar.calendar.integrations import financial_statements as fs_adapter_mod

	fs_adapter_mod._original_get_period_list = None  # noqa: SLF001 — test reset
	_state = PatchState()


def apply_calendar_patches() -> PatchStatus:
	"""Apply all Calendar Framework compatibility patches for this process.

	Idempotent when already successfully applied. Retries after
	``SOURCE_UNAVAILABLE``, ``PARTIAL_REBIND``, or ``FAILED``.
	"""
	return _apply_get_period_list_patch()


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
	still_stock = _loaded_known_consumers_still_on_original(original)
	if still_stock:
		_state.status = PatchStatus.PARTIAL_REBIND
		_state.last_error = f"Failed to rebind consumers: {', '.join(still_stock)}"
		logger.error(_state.last_error)
		return _state.status

	_state.status = PatchStatus.APPLIED
	_state.last_error = None
	if rebound:
		logger.info(
			"Calendar get_period_list patch applied; rebound: %s",
			", ".join(rebound),
		)
	else:
		logger.info("Calendar get_period_list patch applied (no preloaded consumers to rebind)")
	return _state.status


def _rebind_get_period_list_consumers(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
) -> list[str]:
	"""Rebind ``get_period_list`` only where the attribute is the original stock function."""
	rebound: list[str] = []

	for mod_name in GET_PERIOD_LIST_CONSUMERS:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if _rebind_module_attr(mod, original, adapter):
			rebound.append(mod_name)

	# Restricted fallback: any already-loaded erpnext.* module holding the stock object
	for mod_name, mod in list(sys.modules.items()):
		if not mod_name.startswith("erpnext."):
			continue
		if mod_name == FS_MODULE_PATH:
			continue
		if mod_name in GET_PERIOD_LIST_CONSUMERS:
			continue
		if not isinstance(mod, ModuleType):
			continue
		if _rebind_module_attr(mod, original, adapter):
			rebound.append(mod_name)
			logger.info("Rebound unlisted erpnext consumer via identity scan: %s", mod_name)

	return rebound


def _rebind_module_attr(
	mod: ModuleType,
	original: Callable[..., Any],
	adapter: Callable[..., Any],
) -> bool:
	"""Replace ``mod.get_period_list`` only if it is the original stock function object."""
	current = getattr(mod, "get_period_list", None)
	if current is None:
		return False
	if current is original:
		mod.get_period_list = adapter
		return True
	return False


def _loaded_known_consumers_still_on_original(original: Callable[..., Any]) -> list[str]:
	still = []
	for mod_name in GET_PERIOD_LIST_CONSUMERS:
		mod = sys.modules.get(mod_name)
		if mod is None:
			continue
		if getattr(mod, "get_period_list", None) is original:
			still.append(mod_name)
	return still


def _restore_consumers_to_original(
	original: Callable[..., Any],
	adapter: Callable[..., Any],
) -> None:
	for mod_name in list(GET_PERIOD_LIST_CONSUMERS) + [
		n for n in sys.modules if n.startswith("erpnext.")
	]:
		mod = sys.modules.get(mod_name)
		if mod is None or not isinstance(mod, ModuleType):
			continue
		if getattr(mod, "get_period_list", None) is adapter:
			mod.get_period_list = original


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
