# Persian Calendar 2.0.1 — Jalali Periodic / Trend Reports

**Release type:** Patch (correctness)

**Focus:** Periodic and trend reports that aggregate by Monthly / Quarterly /
Half-Yearly / Yearly under Company **Business Calendar = Jalali**. Aggregation
must use real Jalali period boundaries on Gregorian DB dates — never cosmetic
renames of Gregorian month buckets.

## Validated matrix

| Component | Validated on bench |
|-----------|-------------------|
| Frappe | 16.31.0 |
| ERPNext | 16.32.0 |
| HRMS | 16.16.0 |
| persian_calendar | **2.0.1** |
| Site | `restore-espad.localhost` (full app set) + `development.localhost` (tests) |

## Root cause — Purchase Invoice Trends

Shared engine: `erpnext.controllers.trends`.

| Layer | Pre-2.0.1 (Jalali BC) | 2.0.1 |
|-------|----------------------|-------|
| Period ranges | Already Jalali via `get_period_date_ranges` adapter (2.0.0 / 1.8) | Unchanged |
| SQL allocation | `SUM(IF(date BETWEEN sd AND ed, …))` on those ranges | Unchanged |
| Column labels | Stock `get_mon(dt) = strftime("%b")` → `Mar`, `Apr`, … | Jalali names via `period_wise_columns_query` adapter |

So values were often in the correct Farvardin/Ordibehesht buckets while columns
still showed Gregorian abbreviations — confusing and easy to misread as “Gregorian
months renamed.”

**Forbidden (not done):** `Mar → Farvardin` label map without changing bounds.

## Fix

- Patch `erpnext.controllers.trends.period_wise_columns_query`
- Jalali: pass `company=` into `get_period_date_ranges`; labels via
  `format_trends_column_label` (Farvardin…Esfand / Farvardin-Khordad / …)
- Gregorian: delegate to captured stock function (upstream parity)
- Same single-query `IF BETWEEN` strategy — no N×period queries

Affects all seven Trends reports that share `get_columns` / `get_data`:

1. Purchase Invoice Trends  
2. Sales Invoice Trends  
3. Purchase Order Trends  
4. Sales Order Trends  
5. Quotation Trends  
6. Purchase Receipt Trends  
7. Delivery Note Trends  

## Weekly semantics

Trends does **not** expose Weekly. Weekly ranges in Sales/Stock Analytics remain
upstream Gregorian week math (`weekly_always_stock=True`). Business Calendar does
**not** redefine ISO weeks in 2.0.1.

## Performance

Representative live PIT (`اسپاد فارمد دارو`, FY 1405, Monthly, Item): **~0.1s**,
331 rows — same architecture as stock (one SQL with conditional sums).

## Migration

None. No schema changes. No monkey-patch of `formatdate` / `make_xlsx`.

## Known limitations (deferred)

| Report / path | Class | Why deferred |
|---------------|-------|--------------|
| Issue Analytics | A | Own `months[date.month-1]` grouping — not Trends |
| Helpdesk Ticket Analytics | A | Same pattern as Issue Analytics |
| Customer Acquisition and Loyalty (Monthly) | A | `%Y-%m` Gregorian keys |
| Sales Forecast / exponential smoothing | C/E | Planning; not BC reporting |
| MRP / maintenance schedules | E | Operational Gregorian dates |
| Loan repayment / interest schedules | E | Financial schedules ≠ report periods |
| Ageing buckets (0–30 days) | F | Duration, not calendar months |

## Periodic-report audit matrix (summary)

| App | Module | Report | Periods | Grouping | Jalali OK? | Fix | Adapter | Tests |
|-----|--------|--------|---------|----------|------------|-----|---------|-------|
| ERPNext | Accounts | Purchase Invoice Trends | M/Q/H/Y | Trends BETWEEN | Yes (2.0.1) | Labels+company | trends.period_wise_columns_query | test_trends |
| ERPNext | Accounts | Sales Invoice Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Buying | Purchase Order Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Selling | Sales Order Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Selling | Quotation Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Stock | Purchase Receipt Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Stock | Delivery Note Trends | M/Q/H/Y | Trends | Yes | shared | same | same |
| ERPNext | Accounts | Budget Variance | M/Q/H/Y | Trends+BVR | Yes (prior) | — | bvr.execute | prior |
| ERPNext | Accounts | P&L / BS / CF / … | M/Q/H/Y | get_period_list | Yes (prior) | — | FS | prior |
| ERPNext | Selling | Sales Analytics | M/Q/Y/W | SA adapter | Yes (prior) | — | sa.* | prior |
| ERPNext | Buying | Purchase Analytics | M/Q/Y/W | SA shared | Yes (prior) | — | sa.* | prior |
| ERPNext | Stock | Stock Analytics | M/Q/H/Y/W | STK adapter | Yes (prior) | — | stk.* | prior |
| ERPNext | Mfg | Production / WO / JC Summary | via STK | STK rebind | Yes (prior) | — | stk.* | prior |
| ERPNext | Assets | Fixed Asset Register chart | M/Q/… | FS + FAR | Yes (2.0.0) | no regress | far.prepare_chart_data | prior |
| ERPNext | CRM | Sales Pipeline Analytics | M/Q/… | SPA | Yes (prior) | — | spa.execute | prior |
| HRMS | HR | Vehicle Expenses chart | via FS | VE | Yes (prior) | — | ve | prior |
| ERPNext | Support | Issue Analytics | M/… | Gregorian month | **No** | deferred | — | — |
| Helpdesk | — | Ticket Analytics | M/… | Gregorian month | **No** | deferred | — | — |
| ERPNext | Selling | Customer Acquisition Monthly | M | `%Y-%m` | **No** | deferred | — | — |
| Lending | — | repayment / accrual | — | schedules | N/A (E) | unchanged | — | — |
| Insights/LMS/Wiki/Raven/DMS | — | misc charts | varies | mostly C/D/F | audited sample | unchanged unless Class A | — | — |

**Inspected code paths:** 40+ report/controller modules across ERPNext, HRMS,
Helpdesk, Lending, Payments, Insights, erpnext_extensions (filename + `periodicity` /
`MONTH(` / `get_period*` / Trends consumers). Exact automated suite count is in
release validation below.

## Acceptance — live (`restore-espad.localhost`)

Company `اسپاد فارمد دارو`, FY `1405`, Monthly Purchase Invoice Trends:

```text
Farvardin, Ordibehesht, Khordad, Tir, Mordad, Shahrivar,
Mehr, Aban, Azar, Dey, Bahman, Esfand
```

Sales Invoice Trends: same labels. Quarterly / Half-Yearly / Yearly: Jalali span
labels / FY name. FAR `prepare_chart_data` still patched.
