# Budget Variance & Trends — Business Calendar Integration (Phase 3c)

## Goals

Make ERPNext **Budget Variance** and the shared Trends period helper
`erpnext.controllers.trends.get_period_date_ranges` use the **Company Business
Calendar**, while Gregorian companies keep exact stock ERPNext behavior.

Out of scope for this phase: Sales / Purchase / Stock Analytics, Forecast redesign,
MRP, HRMS, Subscription, UI/datepicker work.

## Architecture

```text
CalendarEngine
    ↓
BusinessPeriodEngine          ← canonical period boundaries
    ↓
trends.get_period_date_ranges adapter
budget_variance.execute adapter
    ↓
ERPNext consumers (BVR, Trends reports via in-module calls)
```

Single applicator: `persian_calendar.calendar.patches.apply_calendar_patches()`.

## Installed Trends contract (ERPNext v16.29)

```python
get_period_date_ranges(period, fiscal_year=None, year_start_date=None)
    → list[[start_date, end_date], ...]
```

| Aspect | Stock behavior |
|--------|----------------|
| Periodicities | Monthly, Quarterly, Half-Yearly, Yearly |
| Inputs | Fiscal Year name (loads start/end) or `year_start_date` |
| Boundaries | Inclusive Gregorian dates via `relativedelta` |
| Labels | Not returned — callers use `strftime` / `formatdate` |
| Company | **Not in signature** |
| Accumulated | Not handled here — consumers accumulate themselves |

### Direct-import inventory

| Module | Import |
|--------|--------|
| `budget_variance_report.py` | `from erpnext.controllers.trends import get_period_date_ranges` |
| Same-module | `period_wise_columns_query`, `get_period_month_ranges` |

**Not** the same function: `stock_analytics.get_period_date_ranges`,
`sales_analytics` / `issue_analytics` methods — left untouched.

Trends report modules import `get_columns` / `get_data` only; they pick up the
patched module attribute automatically.

## Company / Business Calendar resolution (Trends)

1. Explicit `company=` keyword (adapter extension; stock callers omit it)
2. `frappe.local.form_dict.company` (report filters)
3. Fiscal Year Company links — **reject mixed Business Calendars**
4. User default company → Global Defaults
5. Else Gregorian safe default

Display Calendar is never consulted.

## Gregorian delegation

When Business Calendar is Gregorian, the adapter calls the **captured** stock
`get_period_date_ranges` / Budget Variance `execute`. No duplicated Gregorian math.

## Jalali Trends periods

`BusinessPeriodEngine.generate(..., provider=Jalali)`:

| Periodicity | Mapping |
|-------------|---------|
| Monthly | Farvardin–Esfand |
| Quarterly | Q1 Far–Khor … Q4 Dey–Esfand |
| Half-Yearly | H1 Far–Shahrivar; H2 Mehr–Esfand |
| Yearly | Full fiscal / date range |

Returned dates are Gregorian storage dates. Periods stay inside the FY range.

## Budget Variance call graph (stock)

```text
execute
  → validate_filters
  → get_budget_dimensions / get_budget_records
  → build_budget_map
       → get_budget_distributions
       → get_months_in_range (Gregorian add_months)
       → key by strftime("%B") + fiscal_year
       → get_actual_transactions (MONTHNAME)
  → get_periods → get_period_date_ranges
  → build_report_data (sum months in each period)
```

### Why Trends patch alone is insufficient

Even with Jalali period ranges, stock still allocates Budget / Actual by
**English month names**. Phase 3c therefore also replaces `execute` for Jalali
companies via the same central applicator.

### Jalali BVR path

- Periods: `BusinessPeriodEngine` + `format_period_label` (presentation only)
- Budget: match stored Budget Distribution by **date containment / business-month flatten**
- Actuals: GL `posting_date` inclusive within `[from_date, to_date]`
- Cumulative: sum in business-period order (no January reset)

## Stored Budget Distribution matching

Preferred keys: company context + budget document + `start_date` / `end_date`.

Never match by English month name, Jalali label, or translated text.

Integrity checks:

- Duplicate exact `(start, end)` → throw
- Overlapping ranges → throw
- Missing report period → amount `0` (not reassigned elsewhere)

## Periodicity mismatch policy

| Stored | Report | Behavior |
|--------|--------|----------|
| Finer (e.g. Monthly) | Coarser (Quarterly) | Aggregate by inclusion |
| Coarser (Quarterly) | Finer (Monthly) | Equal split across business months in the stored span (stock flatten-then-regroup) |
| Mixed Budget docs | Any | Each Budget’s rows allocated independently by dates |

Gregorian companies retain stock ERPNext behavior unchanged.

## Actual GL boundaries

Jalali only changes period window dates. Unchanged: GL storage, dimensions,
debit/credit, cancellation, currency, precision, permissions.

Inclusive: first day and last day of the period are included; day before / after
are not (unless they fall in another report period).

## Historical document policy

| Status | Behavior |
|--------|----------|
| Submitted | Stored Budget Distribution rows are authoritative; not rewritten |
| Draft | Stock save may regenerate under current Business Calendar (Phase 3b) |
| Amended | Follows stock amendment; regenerate/validate as appropriate |
| Company calendar change | Does **not** migrate historical submitted rows |

`validate_stale_budget_calendar` may warn when Jalali BC sees non–month-start
stored dates; it does not mutate data.

## Mixed-calendar safety

- Fiscal Year linked to companies with different Business Calendars → clear error
- Report always requires `company` for BVR (stock); calendar from that company
- Do not silently normalize historical submitted rows to the current calendar

## Extension & patch mechanisms

| Target | Mechanism |
|--------|-----------|
| `trends.get_period_date_ranges` | `apply_calendar_patches` — capture, replace, identity-rebind known consumers |
| `budget_variance_report.execute` | Same applicator — capture + replace module `execute` |

No `frappe.utils` monkey patches. No ERPNext source edits.

## Examples

### Gregorian monthly Budget Variance

Company BC = Gregorian → stock `execute` → English month keys → stock totals.

### Jalali monthly Budget Variance

Company BC = Jalali → adapter periods Farvardin–Esfand → BD rows matched by
Gregorian storage dates of those months → GL by `posting_date`.

### Monthly Budget → quarterly report

Three Farvardin–Khordad monthly BD amounts sum into Q1.

### Submitted historical Budget after calendar change

Submitted rows keep old boundaries; report matches those dates. Amend/regenerate
to obtain new calendar periods.

## Known limitations

- Trends **report column labels** (`get_mon` / `%b`) may still show Gregorian
  abbreviations even when date ranges are Jalali — only ranges are patched.
  Budget Variance Jalali path uses `period_labels`.
- Sales / Purchase / Stock Analytics period engines are separate (Phase 3d).
- `bench execute` / console must call `apply_calendar_patches()` explicitly.

## Files

- `persian_calendar/calendar/integrations/trends.py`
- `persian_calendar/calendar/integrations/budget_variance.py`
- `persian_calendar/calendar/patches.py` (Trends + BVR targets)
- `persian_calendar/calendar/integrations/test_trends.py`
- `persian_calendar/calendar/integrations/test_budget_variance.py`
- `docs/budget_business_calendar.md` (Phase 3b; see also)
