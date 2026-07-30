# Sales & Purchase Analytics — Business Calendar (Phase 3d-1)

## Verified ERPNext v16.29 call graph

```text
sales_analytics.execute(filters)
  → Analytics(filters)                 # __init__ calls get_period_date_ranges()
  → Analytics.run()
       → update_company_list_for_parent_company()  # optional subsidiary expand
       → get_columns() / get_data() / get_chart_data()
            → get_period(end_date | posting_date)

purchase_analytics.execute(filters)
  → Analytics(filters).run()           # same class object
```

**Half-Yearly:** not present in Sales Analytics JS range options (Weekly / Monthly / Quarterly / Yearly only).

## Extension

| Item | Value |
|------|--------|
| Module | `persian_calendar/calendar/integrations/sales_analytics.py` |
| Mechanism | Class-method replacement on `Analytics` via `apply_calendar_patches()` |
| Not Trends | Independent of `controllers.trends.get_period_date_ranges` |
| Not Stock | Stock Analytics free functions untouched |

## Policies

| Case | Behavior |
|------|----------|
| Gregorian BC | Captured ERPNext originals |
| Weekly (any BC) | Captured ERPNext originals (no Jalali weeks) |
| Jalali Monthly / Quarterly / Yearly | `BusinessPeriodEngine` |
| Bucket identity | `BusinessPeriod.key` |
| Column fieldname | `frappe.scrub(key)` |
| Display label | `format_period_label` |
| Chart values | Read `fieldname` (stock `scrub(label)` is unsafe when label ≠ key) |
| Mixed subsidiary calendars | Validation error |

## Related / deferred

- Stock Analytics + manufacturing helper rebinds: Phase 3d-2 (`docs/stock_analytics.md`)
- Deferred: CRM Pipeline, Issue Analytics, Trends presentation labels, core MRP/MPS
