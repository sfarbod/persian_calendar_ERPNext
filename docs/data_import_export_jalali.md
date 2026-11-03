# Jalali dates in Data Export, List Export, Report Export, and Data Import

The **persian_calendar** app adds optional checkboxes on Frappe **Data Export**,
**List View → Export Data**, **Query / Script / Report View Export**, and
**Data Import** to convert dates only in the file (database values stay
Gregorian).

> **Frappe 16.52+:** Persian Calendar **2.1.0** adapts to the renamed
> `Exporter.add_data_row(table_fieldname, doc, rows, row_idx)` API. Upgrade to
> 2.1.0 (or later) before using List View Export with Jalali on Frappe ≥16.52.
> See [`RELEASE_2_1_0.md`](RELEASE_2_1_0.md).
>
> **Report export:** Persian Calendar **2.1.1** adds the same checkbox to report
> export dialogs. See [`RELEASE_2_1_1.md`](RELEASE_2_1_1.md).

## Setup

After install or upgrade:

```bash
bench --site <site> migrate   # creates Custom Fields (after_migrate hook)
bench build --app persian_calendar
bench --site <site> clear-cache
```

Verify custom fields:

```python
frappe.db.get_value("Custom Field", {"dt": "Data Export", "fieldname": "export_dates_as_jalali"})
frappe.db.get_value("Custom Field", {"dt": "Data Import", "fieldname": "import_dates_from_jalali"})
```

If the Custom Field is missing on **Data Export**, the desk script injects a
checkbox next to **File Type**.

Custom fields:

| DocType | Field | Label |
|---------|--------|--------|
| Data Export | `export_dates_as_jalali` | Export dates as Jalali |
| Data Import | `import_dates_from_jalali` | Import dates from Jalali |

## Data Export (page)

1. Open **Data Export**.
2. Select DocType and fields (parent and child tables).
3. Check **Export dates as Jalali**.
4. Export CSV or Excel.

## List View → Export Data (v2.0.2)

1. Open any DocType List View (e.g. Purchase Invoice).
2. Select records or rely on filters via Export Type.
3. **Actions → Export** (or Export from the menu).
4. In the **Export Data** dialog, check **Export dates as Jalali** (after Export Type).
5. Choose fields and export CSV or Excel.

Same flag name and conversion rules as the Data Export page. Unchecked = stock
Frappe Gregorian output. Conversion is **fieldtype-driven** (`Date` / `Datetime`
only), including child-table columns.

## Report Export (v2.1.1)

1. Open any Query Report or Script Report (e.g. **General Ledger**, **Stock Ledger**).
2. Set filters and run the report.
3. Click **Export**.
4. Check **Export dates as Jalali**.
5. Download CSV or Excel.

Same label and per-export semantics as Data / List export. Conversion uses report
column `fieldtype` metadata (`Date` / `Datetime` only) and strict ISO / date
objects — ambiguous locale strings are left unchanged. Report calculations and
desk result caches are not modified.

Report View (Report Builder) export uses the same dialog and flag.

## Conversion rules

When checked:

- **Date:** `2026-05-13` → `1405-02-23`
- **Datetime:** `2026-03-18 13:36:04.446274` → `1404-12-27 13:36:04` (microseconds stripped)

When unchecked, behaviour is standard Frappe/ERPNext.

## Data Import

1. Open **Data Import** for a DocType.
2. Check **Import dates from Jalali**.
3. Upload a CSV/Excel file with Jalali dates in Date/Datetime columns.
4. Run import.

## Technical notes

| Path | Upstream | Patch |
|------|----------|-------|
| Data Export page | `data_export.exporter.export_data` | `jalali_support.data_import_export` |
| List View dialog | `data_import.DataExporter` + `download_template` | JS: `public/js/jalali_support/data_import_export.js`; Python: same module |
| Query / Script / Report View export | `query_report._export_query`, `reportview._export_query`, `report_utils.get_export_dialog` | Python: `jalali_support.report_export`; JS: `public/js/jalali_support/report_export.js` |
| Helpers | — | `utils.data_io.convert_export_value` / `convert_import_value` |

- No regex post-processing of CSV text
- No `new Date(jalaliString)` on the server; uses `jdatetime` / `toshamshi`
- Year heuristics: Jalali ~1200–1600, Gregorian ≥1700
- See [`docs/RELEASE_2_0_2.md`](RELEASE_2_0_2.md) for List View extension points

## Tests

```bash
bench --site <site> run-tests --app persian_calendar --module persian_calendar.jalali_support.test_data_export_jalali
bench --site <site> run-tests --app persian_calendar --module persian_calendar.jalali_support.test_list_export_jalali
bench --site <site> run-tests --app persian_calendar --module persian_calendar.utils.test_data_io
```
