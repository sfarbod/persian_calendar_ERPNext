# Budget Variance & Trends — Business Calendar Integration (Phase 3c / 2.0.1)

## Goals

Make ERPNext **Budget Variance** and the shared Trends helpers
`erpnext.controllers.trends.get_period_date_ranges` and
`period_wise_columns_query` use the **Company Business Calendar**, while
Gregorian companies keep exact stock ERPNext behavior.

**2.0.1:** Jalali Trends reports use Jalali period **labels** as well as Jalali
`BETWEEN` boundaries (fixes Purchase/Sales Invoice Trends showing `Mar`/`Apr`
while aggregating on Farvardin/Ordibehesht ranges).

Out of scope: Issue Analytics / Ticket Analytics / Customer Acquisition (Gregorian
`months[date.month]` / `%Y-%m` — deferred), Forecast redesign, MRP, Subscription,
UI/datepicker work.

## Architecture

```text
CalendarEngine
    ↓
BusinessPeriodEngine          ← canonical period boundaries
    ↓
trends.get_period_date_ranges adapter
trends.period_wise_columns_query adapter   ← 2.0.1 column labels
budget_variance.execute adapter
    ↓
ERPNext consumers (BVR, all * Trends reports via get_columns/get_data)
```

Single applicator: `persian_calendar.calendar.patches.apply_calendar_patches()`.

## Installed Trends contract (ERPNext v16.29+)

```python
get_period_date_ranges(period, fiscal_year=None, year_start_date=None)
    → list[[start_date, end_date], ...]

period_wise_columns_query(filters, trans)
    → (period_columns, period_select_sql)
```

| Aspect | Stock behavior |
|--------|----------------|
| Periodicities | Monthly, Quarterly, Half-Yearly, Yearly |
| Inputs | Fiscal Year name (loads start/end) or `year_start_date` |
| Boundaries | Inclusive Gregorian dates via `relativedelta` |
| Labels | Stock: `strftime("%b")` on range start; Jalali adapter: Persian month names |
| Company | **Not in stock signature**; adapter accepts `company=` / uses filters |
| Accumulated | Not handled here — consumers accumulate themselves |

### Direct-import inventory

| Module | Import |
|--------|--------|
| `budget_variance_report.py` | `from erpnext.controllers.trends import get_period_date_ranges` |
| Same-module | `period_wise_columns_query`, `get_period_month_ranges` |
| Purchase/Sales Invoice Trends, Order/Quotation/Receipt/DN Trends | `get_columns`, `get_data` |

**Not** the same function: `stock_analytics.get_period_date_ranges`,
`sales_analytics` / `issue_analytics` methods — separate contracts.

Trends report modules import `get_columns` / `get_data` only; they pick up the
patched module attributes automatically.

## Company / Business Calendar resolution (Trends)

1. Explicit `company=` keyword (adapter extension; stock callers omit it)
2. `filters.company` in `period_wise_columns_query` (2.0.1 — preferred for Trends)
3. `frappe.local.form_dict.company` (report filters)
4. Fiscal Year Company links — **reject mixed Business Calendars**
5. User default company → Global Defaults
6. Else Gregorian safe default

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
boundaries. The helper is covered by tests but is **not** wired into Budget
validate/save (Phase 3 Final documentation correction). If invoked, it warns
only and does not mutate stored dates.

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
