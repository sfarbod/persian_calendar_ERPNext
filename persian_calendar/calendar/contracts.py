"""Declarative ERPNext API contracts for Business Calendar monkey patches.

Phase 4a — when upstream signatures or import paths change, contract checks
fail fast with a human-readable message instead of silently mis-bucketing
business periods.

Validated against ERPNext **16.29.0** / Frappe **16.28.0**.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Sentinel for required parameters (no default)
_REQUIRED = object()


@dataclass(frozen=True)
class ParamSpec:
	name: str
	default: Any = _REQUIRED  # _REQUIRED or concrete default


@dataclass(frozen=True)
class CallableContract:
	"""Expected shape of one patched (or observed) ERPNext callable."""

	id: str
	module: str
	attr: str
	params: tuple[ParamSpec, ...]
	class_name: str | None = None
	# Optional return annotation (stringified). Empty means "no annotation required".
	return_annotation: str | None = None
	notes: str = ""
	# If True, prefer PatchState captured original when patches are applied.
	prefer_captured_original: bool = True
	# PatchState attribute holding the original (when prefer_captured_original).
	original_state_attr: str | None = None


@dataclass
class ContractFailure:
	contract_id: str
	message: str


@dataclass
class ContractResult:
	failures: list[ContractFailure] = field(default_factory=list)

	@property
	def ok(self) -> bool:
		return not self.failures


# ---------------------------------------------------------------------------
# Contracts — ERPNext 16.29.0
# ---------------------------------------------------------------------------

CONTRACTS: tuple[CallableContract, ...] = (
	# Financial Statements
	CallableContract(
		id="fs.get_period_list",
		module="erpnext.accounts.report.financial_statements",
		attr="get_period_list",
		params=(
			ParamSpec("from_fiscal_year"),
			ParamSpec("to_fiscal_year"),
			ParamSpec("period_start_date"),
			ParamSpec("period_end_date"),
			ParamSpec("filter_based_on"),
			ParamSpec("periodicity"),
			ParamSpec("accumulated_values", False),
			ParamSpec("company", None),
			ParamSpec("reset_period_on_fy_change", True),
			ParamSpec("ignore_fiscal_year", False),
		),
		original_state_attr="original_get_period_list",
		notes="Returns list of period dicts with from_date/to_date/key/label.",
	),
	# Trends
	CallableContract(
		id="trends.get_period_date_ranges",
		module="erpnext.controllers.trends",
		attr="get_period_date_ranges",
		params=(
			ParamSpec("period"),
			ParamSpec("fiscal_year", None),
			ParamSpec("year_start_date", None),
		),
		original_state_attr="original_get_period_date_ranges",
		notes="Different contract from stock_analytics.get_period_date_ranges.",
	),
	# Monthly Distribution
	CallableContract(
		id="md.get_periodwise_distribution_data",
		module="erpnext.accounts.doctype.monthly_distribution.monthly_distribution",
		attr="get_periodwise_distribution_data",
		params=(
			ParamSpec("distribution_id"),
			ParamSpec("period_list"),
			ParamSpec("periodicity"),
		),
		original_state_attr="original_get_periodwise_distribution_data",
	),
	CallableContract(
		id="md.get_percentage",
		module="erpnext.accounts.doctype.monthly_distribution.monthly_distribution",
		attr="get_percentage",
		params=(
			ParamSpec("doc"),
			ParamSpec("start_date"),
			ParamSpec("period"),
		),
		original_state_attr="original_get_percentage",
	),
	# Budget Variance
	CallableContract(
		id="bvr.execute",
		module="erpnext.accounts.report.budget_variance_report.budget_variance_report",
		attr="execute",
		params=(ParamSpec("filters", None),),
		original_state_attr="original_budget_variance_execute",
	),
	# Sales Analytics (class methods)
	CallableContract(
		id="sa.Analytics.get_period_date_ranges",
		module="erpnext.selling.report.sales_analytics.sales_analytics",
		attr="get_period_date_ranges",
		class_name="Analytics",
		params=(ParamSpec("self"),),
		original_state_attr="original_sa_get_period_date_ranges",
	),
	CallableContract(
		id="sa.Analytics.get_period",
		module="erpnext.selling.report.sales_analytics.sales_analytics",
		attr="get_period",
		class_name="Analytics",
		params=(ParamSpec("self"), ParamSpec("posting_date")),
		original_state_attr="original_sa_get_period",
	),
	CallableContract(
		id="sa.Analytics.get_columns",
		module="erpnext.selling.report.sales_analytics.sales_analytics",
		attr="get_columns",
		class_name="Analytics",
		params=(ParamSpec("self"),),
		original_state_attr="original_sa_get_columns",
	),
	CallableContract(
		id="sa.Analytics.get_chart_data",
		module="erpnext.selling.report.sales_analytics.sales_analytics",
		attr="get_chart_data",
		class_name="Analytics",
		params=(ParamSpec("self"),),
		original_state_attr="original_sa_get_chart_data",
	),
	CallableContract(
		id="sa.Analytics.update_company_list_for_parent_company",
		module="erpnext.selling.report.sales_analytics.sales_analytics",
		attr="update_company_list_for_parent_company",
		class_name="Analytics",
		params=(ParamSpec("self"),),
		original_state_attr="original_sa_update_company_list",
	),
	# Stock Analytics
	CallableContract(
		id="stk.get_period_date_ranges",
		module="erpnext.stock.report.stock_analytics.stock_analytics",
		attr="get_period_date_ranges",
		params=(ParamSpec("filters"),),
		original_state_attr="original_stk_get_period_date_ranges",
		notes="Returns list[[start, end], ...] — not the Trends end-date list.",
	),
	CallableContract(
		id="stk.get_period",
		module="erpnext.stock.report.stock_analytics.stock_analytics",
		attr="get_period",
		params=(ParamSpec("posting_date"), ParamSpec("filters")),
		original_state_attr="original_stk_get_period",
	),
	CallableContract(
		id="stk.get_period_columns",
		module="erpnext.stock.report.stock_analytics.stock_analytics",
		attr="get_period_columns",
		params=(ParamSpec("filters"),),
		original_state_attr="original_stk_get_period_columns",
	),
	CallableContract(
		id="stk.round_down_to_nearest_frequency",
		module="erpnext.stock.report.stock_analytics.stock_analytics",
		attr="round_down_to_nearest_frequency",
		params=(ParamSpec("date"), ParamSpec("frequency")),
		return_annotation="datetime.datetime",
		original_state_attr="original_stk_round_down",
		notes="Captured but NOT replaced on the module (Gregorian delegation safety).",
	),
	# Budget DocType method (override_doctype_class entry — not free-function patch)
	CallableContract(
		id="budget.Budget.get_budget_periods",
		module="erpnext.accounts.doctype.budget.budget",
		attr="get_budget_periods",
		class_name="Budget",
		params=(ParamSpec("self"),),
		prefer_captured_original=False,
		notes="Patched via override_doctype_class → PersianCalendarBudget.",
	),
)


def _annotation_str(annotation: Any) -> str | None:
	if annotation is inspect.Parameter.empty or annotation is inspect.Signature.empty:
		return None
	if isinstance(annotation, str):
		return annotation
	mod = getattr(annotation, "__module__", None)
	qual = getattr(annotation, "__qualname__", None) or getattr(annotation, "__name__", None)
	if mod and qual and mod != "builtins":
		return f"{mod}.{qual}"
	return qual or str(annotation)


def resolve_callable(contract: CallableContract) -> Callable[..., Any]:
	"""Resolve the callable to validate (prefer captured stock original)."""
	if contract.prefer_captured_original and contract.original_state_attr:
		from persian_calendar.calendar.patches import get_patch_state

		state = get_patch_state()
		captured = getattr(state, contract.original_state_attr, None)
		if captured is not None:
			return captured

	mod = importlib.import_module(contract.module)
	if contract.class_name:
		cls = getattr(mod, contract.class_name, None)
		if cls is None:
			raise AttributeError(
				f"ERPNext contract {contract.id}: module {contract.module!r} has no "
				f"class {contract.class_name!r}. Upstream refactor broke the patch target."
			)
		fn = getattr(cls, contract.attr, None)
		if fn is None:
			raise AttributeError(
				f"ERPNext contract {contract.id}: {contract.class_name}.{contract.attr} "
				f"missing on {contract.module}."
			)
		# Unbind if needed — inspect.signature works on functions and methods
		return fn

	fn = getattr(mod, contract.attr, None)
	if fn is None:
		raise AttributeError(
			f"ERPNext contract {contract.id}: {contract.module}.{contract.attr} is missing. "
			"Upstream removed or renamed the patch target."
		)
	return fn


def check_callable_contract(contract: CallableContract, fn: Callable[..., Any] | None = None) -> list[str]:
	"""Return human-readable failure messages (empty = pass)."""
	errors: list[str] = []
	try:
		fn = fn if fn is not None else resolve_callable(contract)
	except Exception as exc:
		return [str(exc)]

	if not callable(fn):
		return [f"{contract.id}: target exists but is not callable ({type(fn)!r})."]

	sig = inspect.signature(fn)
	actual_params = list(sig.parameters.values())
	expected = contract.params

	if len(actual_params) != len(expected):
		errors.append(
			f"{contract.id}: parameter count changed — expected "
			f"{len(expected)} ({', '.join(p.name for p in expected)}), got "
			f"{len(actual_params)} ({', '.join(p.name for p in actual_params)}). "
			"Update the Business Calendar adapter and this contract before upgrading."
		)
		return errors

	for exp, act in zip(expected, actual_params, strict=True):
		if act.name != exp.name:
			errors.append(
				f"{contract.id}: parameter renamed — expected {exp.name!r}, got {act.name!r}. "
				"Adapters binding by position/name may break."
			)
		if exp.default is _REQUIRED:
			if act.default is not inspect.Parameter.empty:
				errors.append(
					f"{contract.id}: parameter {exp.name!r} gained a default ({act.default!r}); "
					"was required in ERPNext 16.29.0 contract."
				)
		else:
			if act.default is inspect.Parameter.empty:
				errors.append(
					f"{contract.id}: parameter {exp.name!r} lost its default " f"(expected {exp.default!r})."
				)
			elif act.default != exp.default:
				errors.append(
					f"{contract.id}: parameter {exp.name!r} default changed — "
					f"expected {exp.default!r}, got {act.default!r}."
				)

	if contract.return_annotation:
		actual_ret = _annotation_str(sig.return_annotation)
		if actual_ret != contract.return_annotation:
			errors.append(
				f"{contract.id}: return annotation changed — expected "
				f"{contract.return_annotation!r}, got {actual_ret!r}."
			)

	return errors


def validate_all_contracts() -> ContractResult:
	result = ContractResult()
	for contract in CONTRACTS:
		for msg in check_callable_contract(contract):
			result.failures.append(ContractFailure(contract.id, msg))
	return result


def assert_module_class_hierarchy(module: str, class_name: str, expected_bases: tuple[str, ...]) -> list[str]:
	"""Verify class exists and immediate interesting bases match."""
	errors: list[str] = []
	try:
		mod = importlib.import_module(module)
	except ImportError as exc:
		return [f"{module}: cannot import ({exc})."]
	cls = getattr(mod, class_name, None)
	if cls is None:
		return [f"{module}.{class_name}: class missing."]
	base_names = tuple(b.__name__ for b in cls.__mro__[1:3])
	if base_names[: len(expected_bases)] != expected_bases:
		errors.append(
			f"{module}.{class_name}: unexpected MRO near top — expected bases "
			f"{expected_bases}, got {base_names}. override_doctype_class may need review."
		)
	return errors
