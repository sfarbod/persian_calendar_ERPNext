# Persian Calendar 2.0.2 — List View Jalali Export

**Release type:** Patch (correctness / feature completion)

**Focus:** Make **Export dates as Jalali** available on every standard List View
**Export Data** dialog, using the same conversion helpers and terminology as the
existing Data Export page.

## Validated matrix

| Component | Validated |
|-----------|-----------|
| Frappe | 16.31.0 |
| ERPNext | 16.32.0 |
| persian_calendar | **2.0.2** |

## Root cause / limitation (pre-2.0.2)

The Data Export page path already worked (`export_data` + `DataExporter.add_data_row`).

List View uses a **different** stack:

```text
BulkOperations.export
  → frappe.require("data_import_tools.bundle.js")
  → frappe.data_import.DataExporter
  → open_url_post(...download_template)
  → data_import.Exporter
```

Earlier JS attempted to patch `DataExporter` on desk load, but the class is only
defined after the lazy bundle loads — so the patch never ran. It also called
`dialog.add_field(...)`, which **does not exist** on Frappe `Dialog`.

Separately, the Python `Exporter.__init__` wrapper set `export_dates_as_jalali`
**after** stock `__init__`, but `data_import.Exporter` builds all rows during
`__init__`. The flag was therefore always unset while converting.

## Architecture (2.0.2)

```text
UI: Export Data dialog checkbox  OR  Data Export form checkbox
        | export_dates_as_jalali = 0|1  (per export only)
        v
download_template  /  export_data   (whitelisted, permissions unchanged)
        v
Exporter / DataExporter.add_data_row
        | fieldtype Date / Datetime only (meta-driven)
        v
convert_export_value → gregorian_to_jalali_for_export / toshamshi
        v
CSV / Excel
```

Gregorian default: unchecked → stock Frappe output. No silent global conversion.

## Extension points

| Layer | Upstream | Persian Calendar |
|-------|----------|------------------|
| JS dialog | `frappe.data_import.DataExporter.make_dialog` | Temporary `Dialog` subclass injects Check field after Export Type; hook `frappe.require` for `data_import_tools.bundle.js` |
| JS POST | `DataExporter.export_records` → `open_url_post` | Wrap `open_url_post` for that call to append `export_dates_as_jalali` |
| JS Data Export | Form + `open_url_post` | Existing checkbox / Custom Field + flag inject for `export_data` |
| Python List | `data_import.download_template`, `Exporter` | Patched whitelist + `__init__`/`add_data_row` |
| Python Data Export | `data_export.exporter.export_data`, `DataExporter` | Existing patches (flag set before init) |
| Helpers | — | `persian_calendar.utils.data_io.convert_export_value` |

### Upgrade safety

- Does **not** copy Frappe's `make_dialog` body.
- If Frappe renames the bundle or `DataExporter`, the require hook no-ops safely;
  Data Export page path remains intact.
- `download_template` mirrors current Frappe v16 signature (`order_by` via List
  user settings). Signature drift fails contract-style usage; re-align the wrapper.

## Conversion rules

| Fieldtype | ON | OFF / other types |
|-----------|----|-------------------|
| Date | Jalali `YYYY-MM-DD` (e.g. `2026-09-06` → `1405-06-15`) | unchanged |
| Datetime | Jalali date + preserved time (microseconds stripped) | unchanged |
| Data/Link/… | never converted (even if value looks like a date) | unchanged |
| Empty / null | unchanged | unchanged |
| Child table Date/Datetime | converted when fieldtype matches | unchanged |

## Migration

None. Rebuild desk assets after upgrade:

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
```

## Manual check

List View (Purchase Invoice, Sales Invoice, Payment Entry, Employee) → Export →
check **Export dates as Jalali** → Date/Datetime Jalali; other fields and filters
unchanged. Data → Data Export still works with the same label.
