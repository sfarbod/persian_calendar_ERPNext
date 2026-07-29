# Sales Pipeline Analytics — Business Calendar (Phase 5A-3)

**Status:** Implemented  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0**  
**Report:** `erpnext.crm.report.sales_pipeline_analytics.sales_pipeline_analytics`  
**Adapter:** `persian_calendar.calendar.integrations.sales_pipeline_analytics`

Display Calendar coverage for CRM forms/lists/filters remains Phase 5A-2
([`CRM_DISPLAY_CALENDAR.md`](CRM_DISPLAY_CALENDAR.md)). This document covers
**Business Calendar period grouping only**.

---

## 1. Scope

When Company Business Calendar is **Jalali**, Sales Pipeline Analytics Monthly
and Quarterly buckets use `BusinessPeriodEngine` on `Opportunity.expected_closing`.

When Company Business Calendar is **Gregorian** (or company missing), the
captured upstream `execute` runs unchanged.

---

## 2. Upstream report architecture

```text
execute(filters)
  → SalesPipelineAnalytics(filters).run()
       → validate_filters (from_date, to_date required)
       → get_columns → set_range_columns (English %B months or Q1–Q4)
       → get_data → get_fields
            → SQL Month / MonthName / Quarter on expected_closing
       → get_periodic_data / append_data
       → get_chart_data
  → (columns, data, None, chart)
```

| Item | Value |
|------|--------|
| Source DocType | Opportunity |
| Business date | `expected_closing` |
| Metrics | Number = COUNT; Amount = `opportunity_amount` (+ FX to company currency) |
| Dimensions | Owner (`_assign`) or Sales Stage |
| Frequencies (UI) | Monthly, Quarterly only |
| Company | Filter (default user company in JS) |
| Permissions | `ignore_permissions=True` on qb query (upstream) |

---

## 3. Source date field

`expected_closing` (Date). Null closings are excluded by the between-filter and
by allocation (`continue` if missing). Not used: `transaction_date`, `creation`.

---

## 4. Company resolution

`company_from_filters(filters)` → `get_business_calendar_for_company`.

- No guess from Opportunity rows after query.
- Missing company → Gregorian delegation (upstream may still run without company).

---

## 5. Gregorian delegation

`should_use_jalali_engine` false → `return _original_execute(filters)`.

Parity target: columns, rows, chart, validation identical to stock ERPNext.

---

## 6–7. Jalali Monthly / Quarterly

1. `build_jalali_periods(from_date, to_date, range, company, snap=True)`
2. Fetch opportunity rows with Gregorian `expected_closing` (no SQL MONTH/QUARTER)
3. `lookup_period_key` → scrubbed `BusinessPeriod.key` fieldnames
4. Aggregate count/amount; Owner `_assign` expansion mirrors upstream
5. Columns/chart from the same period list + `format_period_label`

Keys examples: `j12_1403`, `j01_1404`, `jq4_1403`, `jq1_1404`.

---

## 8. Query strategy

**Strategy A (chosen):** opportunity-level fetch, Python allocation.

Why not SQL MONTH/QUARTER: wrong Jalali buckets (proven: 2025-03-20 Esfand vs
2025-03-21 Farvardin share Gregorian March / Q1).

Parameterized via `frappe.qb.get_query` + select; no string-interpolated SQL.

Complexity: O(rows + periods) with linear bounds scan (period lists are small).

---

## 9. Metric preservation

| Metric | Upstream | Jalali path |
|--------|----------|-------------|
| Number | `Count(*)` per month/stage | +1 per allocated row |
| Amount | Row amounts × FX then sum | Same FX helpers (`flt` + cache), then sum |
| Probability / weighted | Not in report | — |

---

## 10. Stable keys

| Concept | Source |
|---------|--------|
| Internal key | `BusinessPeriod.key` |
| fieldname | `frappe.scrub(key)` |
| label | `format_period_label` (locale from `frappe.local.lang`) |

Labels are never used as dict keys.

---

## 11. Chart behavior

Labels and dataset values built from the same `period_meta` list as table
columns. Totals sum across pipelines per period.

Jalali chart length equals number of business periods (does not pad to 12 like
upstream Monthly quirk).

---

## 12. Empty periods

All periods in the snapped range appear as columns. Pipelines with any data get
zero-filled missing periods. Pipelines with no matching rows are omitted
(same spirit as upstream occupied pipelines).

---

## 13. Date boundaries

Inclusive `from_date`/`to_date` filter (Gregorian storage). Allocation inclusive
on period `[from_date, to_date]`. Snap floors range start to Jalali period start
before generation; filter still excludes rows before user `from_date`.

Critical proof cases:

- Esfand 30 1403 (`2025-03-20`) → `j12_1403` / `jq4_1403`
- Farvardin 1 1404 (`2025-03-21`) → `j01_1404` / `jq1_1404`

---

## 14. Currency and precision

Amount path: company `default_currency`, `get_exchange_rate`, `flt`, cache key =
from-currency (upstream pattern).

---

## 15. Performance

One opportunity query + in-memory allocation. Period list cached only for the
execute call. No per-period SQL.

---

## 16. Patch lifecycle

- Module: `sales_pipeline_analytics.execute` replaced
- Capture once → `original_sales_pipeline_execute`
- Wired in `apply_calendar_patches` after Stock Analytics
- Idempotent; reset via `reset_calendar_patches_for_tests`
- No identity rebind consumers (report imports `execute` from module at call time via Frappe report runner)

---

## 17. Contracts and diagnostics

- Contract id: `spa.execute`
- Registry: CRM Pipeline Analytics → `implemented`
- `release_check` includes SPA module/adapter health
- Missing execute / signature drift → FAIL

---

## 18. Upgrade risks

| Risk | Detection |
|------|-----------|
| execute renamed / moved | SOURCE_UNAVAILABLE / contract |
| Month/Quarter SQL refactor | Gregorian still delegates; Jalali path independent |
| expected_closing renamed | Runtime/filter failures + contract notes |
| Return tuple shape change | Report UI / tests |
| New frequencies in UI | Not auto-enabled; `_ALLOWED_RANGES` |

---

## 19. Known limitations

- Weekly / Half-Yearly / Yearly not in upstream UI — not implemented
- Jalali Quarterly emits year-qualified keys (`jq1_1404`) instead of collapsing to bare `Q1` (upstream Gregorian quirk)
- Amount multi-assign Owner still expands like upstream (possible double-count)
- No CRM Display changes in this phase

---

## 20. Testing matrix

Module: `persian_calendar.calendar.integrations.test_sales_pipeline_analytics`

Patch lifecycle, Gregorian delegation, Esfand/Farvardin month+quarter proofs,
Jalali M/Q aggregation, empty periods, amount flt, Display independence,
label formatter, `spa.execute` contract.

---

## 21. Examples

Gregorian storage `2025-03-20` / `2025-03-21` with Company Business Calendar =
Jalali → two Monthly columns (Esfand 1403, Farvardin 1404), not one “March”.
