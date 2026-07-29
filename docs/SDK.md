# Business Calendar Framework — Extension SDK (Phase 4b)

How to extend the framework with a new ERPNext adapter **without** changing
`BusinessPeriodEngine` semantics or adding CRM/HRMS/MRP.

| Stable import | `persian_calendar.api` |
|---------------|------------------------|
| Architecture  | `docs/ARCHITECTURE_BUSINESS_CALENDAR.md` |
| Upgrade       | `docs/UPGRADE_GUIDE.md` |
| API reference | `docs/API_REFERENCE.md` |
| CRM Display | `docs/CRM_DISPLAY_CALENDAR.md` (Phase 5A-2 — no BC adapters) |
| CRM Pipeline BC | `docs/CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md` (Phase 5A-3) |
| Conversion | `docs/TOSHAMSHI.md` |

---

## 1. Public vs internal

**Public** (import from `persian_calendar.api`):

- `CalendarEngine`, `CalendarProvider`
- `BusinessPeriod`, `BusinessPeriodEngine`, `format_period_label`
- Resolve helpers (`get_business_calendar_for_company`, constants)
- `apply_calendar_patches`, `PatchStatus`, `get_patch_state`
- Compatibility / diagnostics (`detect_compatibility`, `run_diagnostics`, `release_check`)
- Registry (`INTEGRATED_MODULES`, `registry_as_dict`)
- Adapter helpers (`build_jalali_periods`, `should_use_jalali_engine`, …)
- Patch SDK (`capture_original`, `install_adapter`, `rebind_consumers`)
- Display conversion: `toshamshi`, `toshamsi` (alias) — see [`TOSHAMSHI.md`](TOSHAMSHI.md)

**Internal** (do not depend on in app code):

- `persian_calendar.calendar.integrations.*` adapters (implementation)
- `adapter_template.py` (docs-as-code only)
- Private `_` helpers inside adapters
- Display Calendar / `jalali_support.formatters` (Desk presentation layer; distinct from `toshamshi`)

---

## 2. Integrate a new module

1. **Audit** installed ERPNext source (call graph, signatures, importers).
2. **Decide** override_doctype_class vs free-function patch (see Architecture decision tree).
3. **Declare** `CallableContract` rows in `calendar/contracts.py`.
4. **Register** an `IntegratedModule` in `calendar/registry.py`.
5. **Implement** a thin adapter using `persian_calendar.api` helpers.
6. **Wire** capture + install + rebind inside `apply_calendar_patches`.
7. **Test** Gregorian parity, Jalali periods, lifecycle, Display independence.
8. **Document** a module note + Compatibility Matrix row.
9. **Run** `diagnostics.release_check`.

Skeleton: `persian_calendar/calendar/adapter_template.py`.

Required pieces for every adapter:

| Piece | Role |
|-------|------|
| Target function | Exact ERPNext callable |
| Gregorian delegate | Captured original |
| Engine call | `BusinessPeriodEngine` for Jalali |
| Result mapper | Stock return shape (report-specific) |
| Consumer list | Identity rebind (if any) |
| Documentation | Module note + registry |

---

## 3. Writing an adapter (pattern)

```python
from persian_calendar.api import (
    build_jalali_periods,
    get_business_calendar_for_company,
    should_use_jalali_engine,
)

_ALLOWED = frozenset({"Monthly", "Quarterly", "Yearly"})
_original = None

def adapted(filters):
    if not should_use_jalali_engine(
        company=filters.get("company"),
        rang=filters.get("range"),
        allowed_ranges=_ALLOWED,
        get_bc=get_business_calendar_for_company,  # patchable in tests
    ):
        return _original(filters)
    periods = build_jalali_periods(
        filters.from_date, filters.to_date, filters.range, filters.company
    )
    return [[bp.from_date, bp.to_date] for bp in periods]  # map to stock shape
```

Rules:

- Weekly → always stock when the report exposes Weekly.
- Same-named helpers in Trends / Sales / Stock are **different contracts**.
- Labels never become business keys — use `BusinessPeriod.key`.
- Never patch `frappe.utils`.

---

## 4. Register diagnostics & contracts

```text
contracts.py   → CallableContract (signature lock)
registry.py    → IntegratedModule (human inventory)
patches.py     → apply_calendar_patches wiring
diagnostics.py → release_check consumes contracts + registry health
```

Add contract tests expectations in `test_contracts.py` catalog if you introduce a new required id.

---

## 5. Compatibility exposure

```python
from persian_calendar.api import detect_compatibility, release_check

detect_compatibility()  # SUPPORTED / PARTIALLY_VERIFIED / UNKNOWN_VERSION
release_check()         # PASS / WARNING / FAIL
```

Advance the validated matrix only after intentional re-audit (see Upgrade Guide).

---

## 6. Documentation updates on each integration

- Architecture Compatibility Matrix
- Developer Guide recipe (if new pattern)
- Module note under `docs/`
- Registry row
- Upgrade Guide checklist item if new patch target

---

## 7. Self-validation

```bash
bench --site <site> run-tests --app persian_calendar \
  --module persian_calendar.calendar.test_sdk
bench --site <site> execute persian_calendar.calendar.diagnostics.release_check
```

`test_sdk` asserts adapters import shared helpers and the public API exports remain stable.
