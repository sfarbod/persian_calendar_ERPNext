# Stock Analytics — Business Calendar (Phase 3d-2)

## Verified ERPNext v16.29 call graph

```text
stock_analytics.execute(filters)
  → get_period_columns(filters)
       → get_period_date_ranges(filters)   # list[[start, end], ...]
       → get_period(end_date, filters)
  → get_data(filters)
       → get_periodic_data(sle, filters)   # carry-forward by period key
            → get_period_date_ranges / get_period
       → row[scrub(period)] from get_period
  → get_chart_data(period_columns)         # labels only; empty datasets
```

### Direct importers (identity-rebind)

| Module | Imports |
|--------|---------|
| `production_analytics` | `get_period`, `get_period_columns`, `get_period_date_ranges` |
| `work_order_summary` | `get_period`, `get_period_date_ranges` |
| `job_card_summary` | `get_period`, `get_period_date_ranges` |

`warehouse_wise_item_balance_age_and_value` imports data helpers only — not a period consumer.

### Supported periodicities

| Range | Stock Analytics JS | Python increment map | Jalali engine |
|-------|--------------------|----------------------|---------------|
| Weekly | Yes | Yes | **Always stock** (no Jalali weeks) |
| Monthly | Yes | Yes | Yes |
| Quarterly | Yes | Yes | Yes |
| Half-Yearly | **No** (API only) | Yes | Yes |
| Yearly | Yes | Yes (FY snap) | Yes (FY start + engine) |

## Extension

| Item | Value |
|------|--------|
| Module | `persian_calendar/calendar/integrations/stock_analytics.py` |
| Mechanism | Free-function replacement + identity rebind via `apply_calendar_patches()` |
| Patch target name | `stock_analytics` (distinct from Trends and Sales Analytics) |
| Not patched | `round_down_to_nearest_frequency`, `get_periodic_data`, `execute` |
| Not Trends | Independent of `controllers.trends.get_period_date_ranges` |
| Not Sales | Independent of `Analytics` class methods |

### Why `round_down` is not patched

Stock `get_period_date_ranges` looks up `round_down_to_nearest_frequency` via **module globals** at call time. Replacing it would poison Gregorian delegation when the captured original runs. Jalali flooring is done inside the adapter via CalendarEngine / Fiscal Year snap before `BusinessPeriodEngine.generate`.

## Policies

| Case | Behavior |
|------|----------|
| Gregorian BC | Captured ERPNext originals |
| Weekly (any BC) | Captured ERPNext originals |
| Jalali M/Q/H/Y | `BusinessPeriodEngine` |
| Bucket identity | `BusinessPeriod.key` |
| Column fieldname | `frappe.scrub(key)` |
| Display label | `format_period_label` (Stock / Production columns) |
| Carry-forward | Unpatched `get_periodic_data` + stable keys |
| Company | Explicit report `company`; Display Calendar ignored |
| Mixed calendars | N/A for these single-company reports |
| WO / JC chart labels | Use period key strings (helpers only; no separate label patch) |

## Performance

- Resolve Business Calendar **once** per filters object (`_pc_stk_bc_resolved`).
- Generate period list once; map SLE dates against cached bounds.
- Avoid DB calls inside period-mapping loops.

## Explicit non-goals

- Core MRP / MPS / capacity / BOM scheduling (Phase 6B: MRP Report buckets deferred)
- Exponential Smoothing Forecasting Jalali periods (Forecast Phase 3e — pass `company`)
- CRM Pipeline Analytics / Issue Analytics / HRMS
- Trends presentation-label cleanup
- Jalali Weekly semantics

Phase 6B full MFG/Stock inventory:
[`MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md`](MANUFACTURING_STOCK_BUSINESS_CALENDAR_AUDIT.md).

## Tests

`persian_calendar/calendar/integrations/test_stock_analytics.py`
