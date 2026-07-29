"""Business Calendar self-diagnostics and release validation (Phase 4a).

Usage::

    bench --site <site> execute persian_calendar.calendar.diagnostics.run
    bench --site <site> execute persian_calendar.calendar.diagnostics.release_check

These commands apply patches if needed, then report compatibility, contracts,
registry, and import-graph health. They do not change business behaviour.
"""

from __future__ import annotations

import ast
import importlib
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from persian_calendar.calendar.compatibility import (
	CompatibilityStatus,
	compatibility_as_dict,
	detect_compatibility,
)
from persian_calendar.calendar.contracts import (
	CONTRACTS,
	assert_module_class_hierarchy,
	validate_all_contracts,
)
from persian_calendar.calendar.patches import (
	BVR_MODULE_PATH,
	FS_MODULE_PATH,
	GET_PERIOD_LIST_CONSUMERS,
	MD_MODULE_PATH,
	MD_PERIODWISE_CONSUMERS,
	SALES_ANALYTICS_MODULE_PATH,
	STOCK_ANALYTICS_MODULE_PATH,
	STOCK_ANALYTICS_PERIOD_CONSUMERS,
	TRENDS_MODULE_PATH,
	TRENDS_PERIOD_RANGES_CONSUMERS,
	PatchStatus,
	apply_calendar_patches,
	get_patch_state,
)


class ReleaseLevel(str, Enum):
	PASS = "PASS"
	WARNING = "WARNING"
	FAIL = "FAIL"


DEFERRED_MODULES = (
	"Forecast redesign (Phase 3e)",
	"CRM Pipeline Analytics",
	"Issue Analytics",
	"Core MRP / MPS",
	"HRMS",
	"Trends presentation-label cleanup (Phase 6)",
	"Subscription / Auto Repeat / Maintenance",
)

TECHNICAL_DEBT = (
	"Budget Variance dual path (month-name stock keys vs Jalali date ranges)",
	"Display formatters may wrap FS get_period_list before BC adapter (labels)",
	"validate_stale_budget_calendar helper not wired to Budget validate",
	"Asset disposal patch outside apply_calendar_patches / test reset",
	"Sales/Stock quarter-half first-day snap still uses small jdatetime helper",
	"toshamshi: out-of-range month/day strings may overflow via jdatetime (not rejected)",
	"toshamshi: years 1601–1699 treated as Gregorian (heuristic gap)",
	"CRM: Sales Pipeline month labels English Gregorian (BC deferred); Appointment email uses format_datetime",
)

UPGRADE_RISKS = (
	"Free-function signature drift on FS / Trends / MD / BVR / Sales / Stock",
	"Direct-import consumer list growth without registry update",
	"Same-named get_period_date_ranges (Trends vs Stock vs Sales) confused in registries",
	"Stock round_down module-global coupling if someone patches it",
)


@dataclass
class CheckItem:
	name: str
	level: ReleaseLevel
	detail: str


@dataclass
class DiagnosticReport:
	compatibility: dict[str, Any]
	patch_status: str
	patch_details: dict[str, Any]
	contract_failures: list[str] = field(default_factory=list)
	registry_issues: list[str] = field(default_factory=list)
	import_issues: list[str] = field(default_factory=list)
	hierarchy_issues: list[str] = field(default_factory=list)
	conversion_issues: list[str] = field(default_factory=list)
	checks: list[CheckItem] = field(default_factory=list)

	@property
	def level(self) -> ReleaseLevel:
		if any(c.level == ReleaseLevel.FAIL for c in self.checks):
			return ReleaseLevel.FAIL
		if any(c.level == ReleaseLevel.WARNING for c in self.checks):
			return ReleaseLevel.WARNING
		return ReleaseLevel.PASS


def _ensure_patches() -> PatchStatus:
	return apply_calendar_patches()


def validate_public_conversion_api() -> list[str]:
	"""Ensure canonical toshamshi / toshamsi remain available for Print Formats.

	A missing conversion function is a FAIL-class issue: Jinja Print Formats and
	third-party callers (e.g. erpnext_extensions) depend on it.
	"""
	issues: list[str] = []

	try:
		jalali = importlib.import_module("persian_calendar.utils.jalali")
	except ImportError as exc:
		return [f"persian_calendar.utils.jalali unavailable: {exc}"]

	try:
		api = importlib.import_module("persian_calendar.api")
	except ImportError as exc:
		return [f"persian_calendar.api unavailable: {exc}"]

	for mod_name, mod, attr in (
		("utils.jalali", jalali, "toshamshi"),
		("utils.jalali", jalali, "toshamsi"),
		("api", api, "toshamshi"),
		("api", api, "toshamsi"),
	):
		fn = getattr(mod, attr, None)
		if fn is None:
			issues.append(
				f"{mod_name}.{attr} is missing — Print Formats / Jinja may break. "
				"Restore the canonical conversion export."
			)
		elif not callable(fn):
			issues.append(f"{mod_name}.{attr} exists but is not callable ({type(fn)!r}).")

	if hasattr(jalali, "toshamshi") and hasattr(jalali, "toshamsi"):
		if jalali.toshamsi is not jalali.toshamshi:
			issues.append(
				"utils.jalali.toshamsi is not an identity alias of toshamshi "
				"(duplicate conversion algorithm risk)."
			)
	if hasattr(api, "toshamshi") and hasattr(api, "toshamsi"):
		if api.toshamsi is not api.toshamshi:
			issues.append("api.toshamsi is not an identity alias of api.toshamshi.")
		if hasattr(jalali, "toshamshi") and api.toshamshi is not jalali.toshamshi:
			issues.append(
				"api.toshamshi is not the same callable as utils.jalali.toshamshi "
				"(duplicate implementation)."
			)

	# Lightweight independence: conversion module must not pull BusinessPeriodEngine
	try:
		path = Path(jalali.__file__).resolve()
		tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		forbidden = {"BusinessPeriodEngine", "BusinessPeriod", "get_business_calendar_for_company"}
		for node in ast.walk(tree):
			if isinstance(node, ast.ImportFrom):
				for alias in node.names:
					if alias.name in forbidden:
						issues.append(
							f"utils.jalali imports {alias.name} — conversion must stay "
							"independent of Business Calendar engines."
						)
			elif isinstance(node, ast.Import):
				for alias in node.names:
					if "period_engine" in (alias.name or ""):
						issues.append("utils.jalali imports period_engine — forbidden coupling.")
	except (OSError, SyntaxError) as exc:
		issues.append(f"Could not AST-scan utils.jalali for BC coupling: {exc}")

	# Jinja hook must still point at the jalali module (exposes all public functions)
	try:
		import frappe

		if getattr(frappe.local, "site", None):
			hooks = frappe.get_hooks("jinja") or {}
			methods = hooks.get("methods") or []
			if "persian_calendar.utils.jalali" not in methods:
				issues.append(
					"hooks.jinja.methods no longer includes persian_calendar.utils.jalali — "
					"Print Format Jinja helpers unavailable."
				)
			else:
				from frappe.utils.jinja import get_jinja_hooks

				method_dict, _filters = get_jinja_hooks()
				method_dict = method_dict or {}
				for name in ("toshamshi", "toshamsi"):
					if name not in method_dict:
						issues.append(
							f"Jinja method {name!r} not exposed from persian_calendar.utils.jalali. "
							"Print Formats using {{{{ {name}(...) }}}} will fail."
						)
					elif method_dict.get("toshamshi") is not None and name == "toshamsi":
						if method_dict.get("toshamsi") is not method_dict.get("toshamshi"):
							issues.append("Jinja toshamsi is not the same callable as toshamshi.")
	except Exception as exc:  # pragma: no cover - site-less environments
		issues.append(f"Jinja registration check skipped/failed: {exc}")

	return issues


def validate_patch_registry() -> list[str]:
	"""Verify registered patch targets exist and point at adapters after apply."""
	issues: list[str] = []
	_ensure_patches()
	state = get_patch_state()

	if state.status != PatchStatus.APPLIED:
		issues.append(
			f"PatchStatus is {state.status.value!r} (expected 'applied'). " f"last_error={state.last_error!r}"
		)

	# Expected registrations — no duplicates in registries
	for name, registry in (
		("GET_PERIOD_LIST_CONSUMERS", GET_PERIOD_LIST_CONSUMERS),
		("MD_PERIODWISE_CONSUMERS", MD_PERIODWISE_CONSUMERS),
		("TRENDS_PERIOD_RANGES_CONSUMERS", TRENDS_PERIOD_RANGES_CONSUMERS),
		("STOCK_ANALYTICS_PERIOD_CONSUMERS", STOCK_ANALYTICS_PERIOD_CONSUMERS),
	):
		if len(registry) != len(set(registry)):
			issues.append(f"{name} has duplicate entries.")

	# Source modules must be importable and hold adapters (or stock round_down)
	checks = [
		(FS_MODULE_PATH, "get_period_list", "adapter_get_period_list", True),
		(
			MD_MODULE_PATH,
			"get_periodwise_distribution_data",
			"adapter_get_periodwise_distribution_data",
			True,
		),
		(MD_MODULE_PATH, "get_percentage", "adapter_get_percentage", True),
		(TRENDS_MODULE_PATH, "get_period_date_ranges", "adapter_get_period_date_ranges", True),
		(BVR_MODULE_PATH, "execute", "adapter_budget_variance_execute", True),
		(STOCK_ANALYTICS_MODULE_PATH, "get_period_date_ranges", "adapter_stk_get_period_date_ranges", True),
		(STOCK_ANALYTICS_MODULE_PATH, "get_period", "adapter_stk_get_period", True),
		(STOCK_ANALYTICS_MODULE_PATH, "get_period_columns", "adapter_stk_get_period_columns", True),
	]
	for mod_path, attr, adapter_attr, must_be_adapter in checks:
		try:
			mod = importlib.import_module(mod_path)
		except ImportError as exc:
			issues.append(f"Registered patch source unavailable: {mod_path} ({exc})")
			continue
		current = getattr(mod, attr, None)
		adapter = getattr(state, adapter_attr, None)
		original_map = {
			"adapter_get_period_list": "original_get_period_list",
			"adapter_get_periodwise_distribution_data": "original_get_periodwise_distribution_data",
			"adapter_get_percentage": "original_get_percentage",
			"adapter_get_period_date_ranges": "original_get_period_date_ranges",
			"adapter_budget_variance_execute": "original_budget_variance_execute",
			"adapter_stk_get_period_date_ranges": "original_stk_get_period_date_ranges",
			"adapter_stk_get_period": "original_stk_get_period",
			"adapter_stk_get_period_columns": "original_stk_get_period_columns",
		}
		original = getattr(state, original_map[adapter_attr], None)
		if original is None:
			issues.append(f"{mod_path}.{attr}: original was never captured.")
		elif original is adapter:
			issues.append(f"{mod_path}.{attr}: original incorrectly equals adapter (capture bug).")
		if must_be_adapter and adapter is not None and current is not adapter:
			issues.append(
				f"{mod_path}.{attr}: module attribute is not the registered adapter "
				"(patch not applied or overwritten)."
			)

	# Stock round_down must remain the captured original (not adapted)
	try:
		stk = importlib.import_module(STOCK_ANALYTICS_MODULE_PATH)
		rd = getattr(stk, "round_down_to_nearest_frequency", None)
		if state.original_stk_round_down is not None and rd is not state.original_stk_round_down:
			issues.append(
				"stock_analytics.round_down_to_nearest_frequency was replaced — "
				"Gregorian delegation via module globals may be poisoned."
			)
	except ImportError as exc:
		issues.append(f"Stock Analytics unavailable while checking round_down: {exc}")

	# Sales Analytics class methods
	try:
		sa = importlib.import_module(SALES_ANALYTICS_MODULE_PATH)
		cls = getattr(sa, "Analytics", None)
		if cls is None:
			issues.append(f"{SALES_ANALYTICS_MODULE_PATH}: Analytics class missing.")
		elif not state.sales_analytics_patched:
			issues.append("Sales Analytics patch flag is False.")
		else:
			from persian_calendar.calendar.integrations import sales_analytics as sa_ad

			for method, adapter_fn, orig_attr in (
				(
					"get_period_date_ranges",
					sa_ad.get_period_date_ranges,
					"original_sa_get_period_date_ranges",
				),
				("get_period", sa_ad.get_period, "original_sa_get_period"),
				("get_columns", sa_ad.get_columns, "original_sa_get_columns"),
				("get_chart_data", sa_ad.get_chart_data, "original_sa_get_chart_data"),
			):
				if getattr(cls, method) is not adapter_fn:
					issues.append(f"Analytics.{method} is not the sales_analytics adapter.")
				if getattr(state, orig_attr) is adapter_fn:
					issues.append(f"Analytics.{method}: captured original equals adapter.")
	except ImportError as exc:
		issues.append(f"Sales Analytics unavailable: {exc}")

	# Dead registration: every CONTRACT module path should be reachable
	seen_modules = {c.module for c in CONTRACTS}
	expected_sources = {
		FS_MODULE_PATH,
		MD_MODULE_PATH,
		TRENDS_MODULE_PATH,
		BVR_MODULE_PATH,
		SALES_ANALYTICS_MODULE_PATH,
		STOCK_ANALYTICS_MODULE_PATH,
		"erpnext.accounts.doctype.budget.budget",
	}
	missing = expected_sources - seen_modules
	if missing:
		issues.append(f"Contract catalog missing source modules: {sorted(missing)}")

	return issues


def _ast_imports_attr(path: Path, from_module: str, attr: str) -> bool:
	try:
		tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
	except (OSError, SyntaxError):
		return False
	for node in ast.walk(tree):
		if isinstance(node, ast.ImportFrom) and node.module == from_module:
			if any(a.name == attr for a in node.names):
				return True
	return False


def validate_import_graph() -> list[str]:
	"""Verify known importers still import expected symbols; check identity rebind."""
	issues: list[str] = []
	_ensure_patches()
	state = get_patch_state()

	try:
		erpnext_root = Path(importlib.import_module("erpnext").__file__).resolve().parent
	except ImportError as exc:
		return [f"ERPNext not importable for import-graph validation: {exc}"]

	# Stock Analytics manufacturing consumers
	stk_specs = (
		(
			"erpnext.manufacturing.report.production_analytics.production_analytics",
			STOCK_ANALYTICS_MODULE_PATH,
			("get_period", "get_period_columns", "get_period_date_ranges"),
		),
		(
			"erpnext.manufacturing.report.work_order_summary.work_order_summary",
			STOCK_ANALYTICS_MODULE_PATH,
			("get_period", "get_period_date_ranges"),
		),
		(
			"erpnext.manufacturing.report.job_card_summary.job_card_summary",
			STOCK_ANALYTICS_MODULE_PATH,
			("get_period", "get_period_date_ranges"),
		),
	)
	for consumer, source, attrs in stk_specs:
		py = erpnext_root.joinpath(*consumer.split(".")[1:]).with_suffix(".py")
		if not py.is_file():
			issues.append(
				f"Import path changed or missing: expected file {py} for {consumer}. "
				"Update STOCK_ANALYTICS_PERIOD_CONSUMERS."
			)
			continue
		for attr in attrs:
			if not _ast_imports_attr(py, source, attr):
				issues.append(
					f"{consumer} no longer imports {attr} from {source}. "
					"Identity rebind may be ineffective — update registry and adapter docs."
				)
		# Runtime identity after patch
		try:
			mod = importlib.import_module(consumer)
			from persian_calendar.calendar.integrations import stock_analytics as stk_ad

			adapters = {
				"get_period_date_ranges": stk_ad.get_period_date_ranges,
				"get_period": stk_ad.get_period,
				"get_period_columns": stk_ad.get_period_columns,
			}
			origs = {
				"get_period_date_ranges": state.original_stk_get_period_date_ranges,
				"get_period": state.original_stk_get_period,
				"get_period_columns": state.original_stk_get_period_columns,
			}
			for attr in attrs:
				current = getattr(mod, attr, None)
				if current is origs[attr]:
					issues.append(f"{consumer}.{attr} still bound to captured original (rebind failed).")
				elif current is not adapters[attr]:
					issues.append(
						f"{consumer}.{attr} is neither adapter nor expected binding "
						f"(got {getattr(current, '__module__', type(current))})."
					)
		except ImportError as exc:
			issues.append(f"Cannot import consumer {consumer}: {exc}")

	# Purchase Analytics shares Sales Analytics class
	try:
		sa = importlib.import_module(SALES_ANALYTICS_MODULE_PATH)
		pa = importlib.import_module("erpnext.buying.report.purchase_analytics.purchase_analytics")
		if getattr(pa, "Analytics", None) is not getattr(sa, "Analytics", None):
			issues.append(
				"Purchase Analytics no longer shares sales_analytics.Analytics — "
				"Phase 3d-1 coverage assumption broken."
			)
	except ImportError as exc:
		issues.append(f"Sales/Purchase Analytics import check failed: {exc}")

	# Trends consumer still imports from trends module
	bvr_py = erpnext_root / "accounts/report/budget_variance_report/budget_variance_report.py"
	if bvr_py.is_file() and not _ast_imports_attr(bvr_py, TRENDS_MODULE_PATH, "get_period_date_ranges"):
		issues.append(
			"budget_variance_report no longer imports get_period_date_ranges from " f"{TRENDS_MODULE_PATH}."
		)

	# Registry ↔ filesystem for STOCK consumers
	for name in STOCK_ANALYTICS_PERIOD_CONSUMERS:
		if name not in {s[0] for s in stk_specs}:
			issues.append(f"STOCK_ANALYTICS_PERIOD_CONSUMERS has unvalidated entry: {name}")

	return issues


def build_report() -> DiagnosticReport:
	compat = detect_compatibility()
	compat_dict = compatibility_as_dict(compat)
	status = _ensure_patches()
	state = get_patch_state()

	contracts = validate_all_contracts()
	registry_issues = validate_patch_registry()
	import_issues = validate_import_graph()
	conversion_issues = validate_public_conversion_api()
	hierarchy_issues: list[str] = []
	hierarchy_issues.extend(
		assert_module_class_hierarchy("erpnext.accounts.doctype.budget.budget", "Budget", ("Document",))
	)
	hierarchy_issues.extend(
		assert_module_class_hierarchy(
			"erpnext.accounts.doctype.monthly_distribution.monthly_distribution",
			"MonthlyDistribution",
			("Document",),
		)
	)
	hierarchy_issues.extend(
		assert_module_class_hierarchy(
			"erpnext.selling.report.sales_analytics.sales_analytics",
			"Analytics",
			("object",),
		)
	)

	patch_details = {
		"status": state.status.value,
		"last_error": state.last_error,
		"fs_rebound": list(state.rebound_modules),
		"md_rebound": list(state.md_rebound_modules),
		"trends_rebound": list(state.trends_rebound_modules),
		"stk_rebound": list(state.stk_rebound_modules),
		"sales_analytics_patched": state.sales_analytics_patched,
		"stock_analytics_patched": state.stock_analytics_patched,
		"registered_targets": [c.id for c in CONTRACTS],
	}

	report = DiagnosticReport(
		compatibility=compat_dict,
		patch_status=status.value if isinstance(status, PatchStatus) else str(status),
		patch_details=patch_details,
		contract_failures=[f"{f.contract_id}: {f.message}" for f in contracts.failures],
		registry_issues=registry_issues,
		import_issues=import_issues,
		hierarchy_issues=hierarchy_issues,
		conversion_issues=conversion_issues,
	)

	# Score checks
	if compat.status == CompatibilityStatus.SUPPORTED:
		report.checks.append(
			CheckItem("compatibility", ReleaseLevel.PASS, compat.messages[0] if compat.messages else "OK")
		)
	elif compat.status == CompatibilityStatus.PARTIALLY_VERIFIED:
		report.checks.append(
			CheckItem(
				"compatibility",
				ReleaseLevel.WARNING,
				compat.messages[0] if compat.messages else "Partially verified",
			)
		)
	elif compat.status == CompatibilityStatus.UNKNOWN_VERSION:
		report.checks.append(
			CheckItem(
				"compatibility",
				ReleaseLevel.WARNING,
				compat.messages[0] if compat.messages else "Unknown version",
			)
		)
	else:
		report.checks.append(CheckItem("compatibility", ReleaseLevel.FAIL, "Frappe/ERPNext unavailable"))

	if status == PatchStatus.APPLIED:
		report.checks.append(CheckItem("patches", ReleaseLevel.PASS, "PatchStatus.applied"))
	elif status == PatchStatus.PARTIAL_REBIND:
		report.checks.append(CheckItem("patches", ReleaseLevel.FAIL, f"partial_rebind: {state.last_error}"))
	elif status == PatchStatus.SOURCE_UNAVAILABLE:
		report.checks.append(
			CheckItem("patches", ReleaseLevel.FAIL, f"source_unavailable: {state.last_error}")
		)
	else:
		report.checks.append(CheckItem("patches", ReleaseLevel.FAIL, f"status={status}"))

	if contracts.ok:
		report.checks.append(CheckItem("contracts", ReleaseLevel.PASS, f"{len(CONTRACTS)} contracts OK"))
	else:
		report.checks.append(
			CheckItem(
				"contracts",
				ReleaseLevel.FAIL,
				f"{len(contracts.failures)} contract failure(s)",
			)
		)

	if not registry_issues:
		report.checks.append(CheckItem("registry", ReleaseLevel.PASS, "Registry healthy"))
	else:
		report.checks.append(CheckItem("registry", ReleaseLevel.FAIL, f"{len(registry_issues)} issue(s)"))

	if not import_issues:
		report.checks.append(CheckItem("import_graph", ReleaseLevel.PASS, "Import graph OK"))
	else:
		report.checks.append(CheckItem("import_graph", ReleaseLevel.FAIL, f"{len(import_issues)} issue(s)"))

	if not hierarchy_issues:
		report.checks.append(CheckItem("hierarchies", ReleaseLevel.PASS, "Class hierarchies OK"))
	else:
		report.checks.append(CheckItem("hierarchies", ReleaseLevel.FAIL, f"{len(hierarchy_issues)} issue(s)"))

	if not conversion_issues:
		report.checks.append(
			CheckItem("conversion_api", ReleaseLevel.PASS, "toshamshi/toshamsi public API OK")
		)
	else:
		report.checks.append(
			CheckItem(
				"conversion_api",
				ReleaseLevel.FAIL,
				f"{len(conversion_issues)} conversion API issue(s)",
			)
		)

	return report


def format_report(report: DiagnosticReport) -> str:
	lines: list[str] = []
	c = report.compatibility
	lines.append("=" * 72)
	lines.append("Persian Calendar — Business Calendar Diagnostics")
	lines.append("=" * 72)
	lines.append(f"Framework version : {c.get('framework_version')}")
	lines.append(f"Frappe version     : {c.get('frappe_version')}")
	lines.append(f"ERPNext version    : {c.get('erpnext_version')}")
	lines.append(f"Python version     : {c.get('python_version')}")
	lines.append(f"Compatibility      : {c.get('status')}")
	for msg in c.get("messages") or []:
		lines.append(f"  · {msg}")
	lines.append(f"PatchStatus        : {report.patch_status}")
	lines.append(f"Sales patched      : {report.patch_details.get('sales_analytics_patched')}")
	lines.append(f"Stock patched      : {report.patch_details.get('stock_analytics_patched')}")
	try:
		from persian_calendar.calendar.registry import implemented_modules

		lines.append(f"Registry modules   : {len(implemented_modules())} implemented/helper")
	except Exception:
		pass
	lines.append("")
	lines.append("Registered contracts:")
	for cid in report.patch_details.get("registered_targets") or []:
		lines.append(f"  - {cid}")
	lines.append("")
	lines.append("Checks:")
	for item in report.checks:
		lines.append(f"  [{item.level.value:7}] {item.name}: {item.detail}")
	if report.contract_failures:
		lines.append("")
		lines.append("Contract failures:")
		for f in report.contract_failures:
			lines.append(f"  ✗ {f}")
	if report.registry_issues:
		lines.append("")
		lines.append("Registry issues:")
		for f in report.registry_issues:
			lines.append(f"  ✗ {f}")
	if report.import_issues:
		lines.append("")
		lines.append("Import-graph issues:")
		for f in report.import_issues:
			lines.append(f"  ✗ {f}")
	if report.hierarchy_issues:
		lines.append("")
		lines.append("Hierarchy issues:")
		for f in report.hierarchy_issues:
			lines.append(f"  ✗ {f}")
	if report.conversion_issues:
		lines.append("")
		lines.append("Conversion API issues (Print Format / Jinja):")
		for f in report.conversion_issues:
			lines.append(f"  ✗ {f}")
	lines.append("")
	lines.append("Deferred modules:")
	for d in DEFERRED_MODULES:
		lines.append(f"  - {d}")
	lines.append("")
	lines.append("Known technical debt:")
	for d in TECHNICAL_DEBT:
		lines.append(f"  - {d}")
	lines.append("")
	lines.append("Known upgrade risks:")
	for d in UPGRADE_RISKS:
		lines.append(f"  - {d}")
	lines.append("")
	lines.append(f"Overall: {report.level.value}")
	lines.append("=" * 72)
	return "\n".join(lines)


def run() -> str:
	"""``bench execute persian_calendar.calendar.diagnostics.run``"""
	report = build_report()
	text = format_report(report)
	print(text)
	return report.level.value


def release_check() -> str:
	"""``bench execute persian_calendar.calendar.diagnostics.release_check``

	Returns ``PASS``, ``WARNING``, or ``FAIL``.
	"""
	report = build_report()
	print(format_report(report))
	print("")
	print(f"RELEASE CHECK: {report.level.value}")
	if report.level == ReleaseLevel.FAIL:
		print("Do not deploy until contract/registry/import failures are resolved.")
	elif report.level == ReleaseLevel.WARNING:
		print("Deploy only after reviewing compatibility warnings and re-running tests.")
	else:
		print("Compatibility guard reports no blocking issues.")
	return report.level.value


def report_as_dict() -> dict[str, Any]:
	"""Machine-readable diagnostic payload (tests / CI)."""
	report = build_report()
	return {
		"level": report.level.value,
		"compatibility": report.compatibility,
		"patch_status": report.patch_status,
		"patch_details": report.patch_details,
		"contract_failures": report.contract_failures,
		"registry_issues": report.registry_issues,
		"import_issues": report.import_issues,
		"hierarchy_issues": report.hierarchy_issues,
		"conversion_issues": report.conversion_issues,
		"checks": [{"name": c.name, "level": c.level.value, "detail": c.detail} for c in report.checks],
		"deferred_modules": list(DEFERRED_MODULES),
		"technical_debt": list(TECHNICAL_DEBT),
		"upgrade_risks": list(UPGRADE_RISKS),
	}
