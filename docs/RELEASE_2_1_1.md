# Persian Calendar 2.1.1 — Report Jalali Export

## Summary

Adds an optional **Export dates as Jalali** checkbox to Frappe **Query Report**,
**Script Report**, and **Report View** export dialogs (CSV / Excel), matching the
existing Data Export and List View Export experience.

- **Jalali is enabled by default** (checkbox checked). Users may uncheck it to
  receive Gregorian dates for that export only.
- When the request omits `export_dates_as_jalali`, report export defaults to Jalali.
  Explicit `0` / `false` preserves Gregorian.
- Conversion is **export-only** — report `run()` results, filters, sort order,
  accounting balances, and stock valuations are never mutated for desk display.
- No Frappe / ERPNext core edits.

## Supported surfaces

| Surface | Upstream | Persian Calendar |
|---------|----------|------------------|
| Query / Script Report export | `frappe.desk.query_report._export_query` | `jalali_support.report_export` |
| Report View / Report Builder export | `frappe.desk.reportview._export_query` | same |
| Export dialog UI | `frappe.report_utils.get_export_dialog` | `public/js/jalali_support/report_export.js` |

## Date detection strategy

1. Report column metadata `fieldtype` ∈ `{Date, Datetime}` (primary).
2. Values converted only when they are Python `date` / `datetime` objects or
   **strict ISO** strings (`YYYY-MM-DD` / `YYYY-MM-DD HH:MM:SS`).
3. Ambiguous forms (`10.04.2026`, `06/09/2026`) are **not** converted.
4. Already-Jalali ISO years (≈1200–1600) pass through without double conversion.
5. Document names, voucher numbers, amounts, quantities, and non-date fieldtypes
   are never converted.

Uses the shared helpers in `persian_calendar.utils.data_io` /
`persian_calendar.utils.jalali` (no second conversion engine).

## CSV / Excel behaviour

| Flag | Date | Datetime |
|------|------|----------|
| ON (default) / absent | `2026-09-06` → `1405-06-15` | `2026-09-06 14:35:12` → `1405-06-15 14:35:12` |
| OFF (`0` / `false`) | Stock Frappe (`formatdate` for CSV; date objects for Excel) | Stock |

Time and seconds are preserved. Empty cells stay empty.

Data Export and List View Export dialogs use the same checked-by-default checkbox
label for consistency. Data Import remains opt-in (`import_dates_from_jalali`
default unchecked).

## Validation notes

Automated tests cover conversion helpers, CSV/XLSX content, idempotent patches,
large result sets, and repeated ON/OFF exports.

Synthetic smoke for accounting / stock column shapes (General Ledger, Accounts
Receivable, Stock Ledger, Trial Balance) confirmed:

- Date columns convert only when Jalali is ON.
- Debit/credit/balance/qty/rate/voucher tokens unchanged.
- Reports without date columns export identically ON vs OFF.

## Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.54.0 (API compatible with ≥16.52) |
| ERPNext | 16.53.0 |
| Persian Calendar | 2.1.1 (from 2.1.0) |

Worker restart (or `before_request`) loads the new Python patches. Rebuild desk
assets after upgrade:

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
```

## Known limitations

- Browser/Desk UI export click-path was **not** automated in this release; verify
  the checkbox manually in Query Report → Export.
- Columns without `Date`/`Datetime` fieldtype metadata are not converted even if
  values look like dates (by design).
- Report filter values printed via “Include filters” are not rewritten to Jalali.
- PDF / Print paths are unchanged (use existing print/template helpers).

## Upgrade from 2.1.0

No migrate/Custom Field changes. Install 2.1.1, rebuild assets, clear cache,
restart workers if needed.
