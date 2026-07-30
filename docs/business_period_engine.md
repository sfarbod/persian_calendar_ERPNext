# Business Period Engine — Architecture & Extension Guide

## Overview

The Business Period Engine (`persian_calendar.calendar.period_engine`) is the
canonical source of truth for generating business period boundaries in ERPNext.

**BusinessPeriodEngine is the canonical period logic.**  
The runtime patch is only a compatibility boundary for ERPNext v16. It must not
become the location of business-period arithmetic.

## Three-Layer Separation

```
Storage Calendar     → Always Gregorian (DB, API, JSON)
Display Calendar     → Per User (UI, Date Picker, Labels)
Business Calendar    → Per Company (Period boundaries, month arithmetic)
```

## Why a Runtime Compatibility Patch Is Necessary

ERPNext v16 exposes `get_period_list` as a **plain free function** in
`erpnext.accounts.report.financial_statements`. Reports import it directly:

```python
from erpnext.accounts.report.financial_statements import get_period_list
```

Supported Frappe extension points are insufficient for this target:

| Mechanism | Why it does not apply |
|-----------|------------------------|
| `override_doctype_class` | Not a DocType method |
| `override_whitelisted_methods` | Not `@frappe.whitelist()`; reports call it in-process |
| Report / Custom Report override | Does not replace stock module paths used by Desk |
| App startup hook | No first-class `on_app_init` for monkey patches |

Without editing ERPNext source or duplicating every report, a **narrow runtime
replacement** of that free function is currently unavoidable.

## Central Patch Applicator

Module: `persian_calendar.calendar.patches`

```python
from persian_calendar.calendar.patches import apply_calendar_patches

apply_calendar_patches()  # process-local, idempotent, rebinding-aware
```

This is the **single entry point** for Calendar Framework compatibility patches.
Phase 3a applies only the Financial Statements `get_period_list` adapter.
Future consumers (Trends, Analytics, …) must extend this applicator — not invent
new patch philosophies.

### Lifecycle coverage (Frappe v16 — verified from installed source)

| Hook | Signature (verified) | Covers |
|------|----------------------|--------|
| `before_request` | `frappe.call(task)` — no args (`frappe/app.py`) | Desk HTTP, API |
| `before_job` | `method=`, `kwargs=`, `transaction_type=` (`background_jobs.py`) | RQ workers, prepared reports, scheduler jobs |
| `before_tests` | `frappe.get_attr(hook)()` — no args (`testing/environment.py`) | Unit/integration tests for this app |

Gunicorn worker restart clears process state; the first request/job re-applies.

### Limitation: `bench execute` / console

Frappe v16 has **no supported lifecycle hook** for interactive console or
`bench execute`. In those contexts call explicitly:

```python
from persian_calendar.calendar.patches import apply_calendar_patches
apply_calendar_patches()
```

Do not claim automatic coverage for console sessions.

## Import-Binding Risk and Rebinding

Python binds imported names at import time. Replacing only
`financial_statements.get_period_list` does **not** update consumers that
already executed:

```python
from erpnext.accounts.report.financial_statements import get_period_list
```

### Strategy

1. Capture the **exact original stock function object** once (never the adapter).
2. Replace `financial_statements.get_period_list` with the adapter.
3. Rebind known consumers where `module.get_period_list is original` (object identity).
4. Restricted fallback scan of loaded `erpnext.*` modules using identity only.
5. Do not rename-match unrelated functions.
6. Log which modules were rebound.

Known direct importers are listed in `GET_PERIOD_LIST_CONSUMERS` (verified against
installed ERPNext v16). An inventory regression test fails if new importers appear.

## Original Function Capture

Gregorian companies call the **real captured ERPNext function**, not a duplicated
replica. This avoids upgrade drift and recursion:

```text
adapter(company Gregorian) → _original_get_period_list(...)
adapter(company Jalali)    → BusinessPeriodEngine + labels
```

Capture occurs exactly once. Repeated `apply_calendar_patches()` must not replace
the original reference with the adapter.

## Failure and Retry Behavior

| Condition | Status | Behavior |
|-----------|--------|----------|
| ERPNext FS module not importable | `source_unavailable` | Log warning; do not permanently block; later retry allowed |
| Original cannot be captured (adapter already installed without capture) | `failed` | Log error; do not claim success |
| Known loaded consumer still holds stock after rebind | `partial_rebind` | Log error; later retry rebinds again |
| Success | `applied` | Idempotent; may still rebind newly imported consumers |

Principles:

- Do not fail migration for a temporary early-import condition.
- Do not silently allow Jalali financial reports to run with stock Gregorian periods once the adapter is the intended path — Gregorian still uses stock; Jalali uses the engine.
- Unexpected exceptions are not swallowed as “applied”.

## Usage (canonical engine)

```python
from persian_calendar.calendar.period_engine import BusinessPeriodEngine

periods = BusinessPeriodEngine.generate(
    start_date="2026-03-21",
    end_date="2027-03-20",
    periodicity="Monthly",
    company="My Company",
)
```

Labels are presentation-only (`period_labels.format_period_label`).

## Future Adapter Policy

```text
Calendar Framework
  BusinessPeriodEngine          # one engine
  apply_calendar_patches()      # one applicator
    ├── get_period_list (Phase 3a)
    ├── monthly distribution (Phase 3b)
    ├── trends.get_period_date_ranges (Phase 3c)
    ├── budget_variance.execute (Phase 3c)
    ├── sales_analytics Analytics methods (Phase 3d-1)
    ├── stock_analytics helpers + manufacturing rebinds (Phase 3d-2)
    └── ...
hooks: before_request + before_job + before_tests
```

See `docs/budget_variance_trends.md`, `docs/sales_purchase_analytics.md`,
`docs/stock_analytics.md`, and `docs/BUSINESS_CALENDAR_PHASE3_RELEASE.md`.
