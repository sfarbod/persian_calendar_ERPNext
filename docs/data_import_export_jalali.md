# Jalali dates in Data Export and Data Import

The **persian_calendar** app adds optional checkboxes on Frappe **Data Export** and **Data Import** to convert dates only in the file (database values stay Gregorian).

## Setup

After install or upgrade:

```bash
bench --site <site> migrate   # creates Custom Fields (after_migrate hook)
bench --site <site> clear-cache
bench build --app persian_calendar
```

Verify custom fields:

```python
bench --site <site> console
```

```python
frappe.db.get_value("Custom Field", {"dt": "Data Export", "fieldname": "export_dates_as_jalali"})
frappe.db.get_value("Custom Field", {"dt": "Data Import", "fieldname": "import_dates_from_jalali"})
[f.fieldname for f in frappe.get_meta("Data Export").fields]
```

**Note:** `frappe.db.exists("Custom Field", "Data Export-export_dates_as_jalali")` is only valid if that exact document `name` exists; prefer the filter form above.

If the Custom Field is missing on **Data Export**, the desk script injects a checkbox next to **File Type** (Single DocType forms still support Custom Fields after migrate).

Browser console (debug on by default in `data_import_export.js`): look for `[Jalali Data IO] loaded`.

Custom fields are created automatically:

| DocType | Field | Label |
|---------|--------|--------|
| Data Export | `export_dates_as_jalali` | Export dates as Jalali |
| Data Import | `import_dates_from_jalali` | Import dates from Jalali |

## Data Export

1. Open **Data Export** (or use **Export Data** from a list view).
2. Select DocType and fields (parent and child tables).
3. Check **Export dates as Jalali**.
4. Export CSV or Excel.

When checked:

- **Date:** `2026-05-13` → `1405-02-23`
- **Datetime:** `2026-03-18 13:36:04.446274` → `1404-12-27 13:36:04` (microseconds stripped)

When unchecked, behaviour is standard Frappe/ERPNext.

## Data Import

1. Open **Data Import** for a DocType.
2. Check **Import dates from Jalali**.
3. Upload a CSV/Excel file with Jalali dates in Date/Datetime columns.
4. Run import.

When checked:

- **Date:** `1405-02-23` → stored as `2026-05-13`
- **Datetime:** `1404-12-27 13:36:04` → stored as `2026-03-18 13:36:04`

Conversion runs **before** validation and document save. Child table Date/Datetime columns are included.

When unchecked, standard date parsing applies.

## List view “Export Data” dialog

The export dialog includes **Export dates as Jalali** when the desk bundle is loaded. It passes the same flag to the download API as Data Export.

## Technical notes

- Server helpers: `persian_calendar.utils.jalali`, `persian_calendar.utils.data_io`
- Patches (once per worker): `persian_calendar.jalali_support.data_import_export`
- No `new Date(jalaliString)` on the server; uses `jdatetime` and explicit parts
- Year heuristics: Jalali ~1200–1600, Gregorian ≥1700

## Tests

```bash
cd apps/persian_calendar
../env/bin/python -m unittest \
  persian_calendar.utils.test_data_io \
  persian_calendar.utils.test_jalali -v
```

## Console check

```python
from persian_calendar.utils.data_io import convert_export_value, convert_import_value
from datetime import date

convert_export_value("2026-05-13", "Date", True)
convert_import_value("1405-02-23", "Date", True)
```
