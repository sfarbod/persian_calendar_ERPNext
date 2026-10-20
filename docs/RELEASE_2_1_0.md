# Persian Calendar 2.1.0 — Frappe 16.52 Import/Export Compatibility

**Release type:** Minor (compatibility repair)

**Focus:** Restore Jalali Data Import / Data Export / List View Export after
Frappe **16.52.0** / ERPNext **16.51.1** upstream API changes that broke
Persian Calendar **2.0.2** patches (HTTP 500 on List View export).

## Validated matrix

| Component | Validated |
|-----------|-----------|
| Frappe | 16.52.0 |
| ERPNext | 16.51.1 |
| persian_calendar | **2.1.0** |
| Site | `development.localhost` |

## Root causes

### HTTP 500 — List View Export / `download_template`

Frappe 16.52 changed:

```text
Exporter.add_data_row(doctype, parentfield, doc, rows, row_idx)
  →
Exporter.add_data_row(table_fieldname, doc, rows, row_idx)
```

Call sites now use `add_data_row(None, doc, rows, 0)` for parent rows.

Persian Calendar 2.0.2 wrapped the **old** five-argument form. At runtime:

```text
TypeError: add_data_row() missing 1 required positional argument: 'row_idx'
```

Origin: Persian Calendar monkey patch (not Frappe core).

### Related upstream changes (non-breaking for PC when patched correctly)

| Surface | Change in 16.52 | PC impact |
|---------|-----------------|-----------|
| `Exporter.__init__` | Import provider / provider tables | Tolerated; we only wrap init + add_data_row |
| `DataExporter` (JS) | Extra ctor args (`hide_blank_template`, `provider_schema`); MultiCheck groups | Dialog field inject still works |
| `download_template` | Still whitelisted; still builds `Exporter` | Flag pass-through unchanged |
| `data_export.DataExporter.add_data_row` | Signature unchanged | Data Export page OK |
| `Importer.before_import` / `Row.parse_value` | Provider setup in before_import | Jalali import wrap still valid |
| Bundle | `data_import_tools.bundle.js` | Lazy require hook still valid |

## Compatibility matrix (PC customizations)

| Customization | Status on 16.52 | Fix in 2.1.0 |
|---------------|-----------------|--------------|
| `data_import.Exporter.add_data_row` wrap | Broken (500) | Signature detection `v1652` / `legacy` |
| `data_import.Exporter.__init__` jalali flag | OK if add_data_row fixed | Stock methods reloaded from source |
| `download_template` whitelist | Worked once Exporter fixed | Versioned rebind |
| `data_export.export_data` / `DataExporter` | OK | Stock reload + version marker |
| `Importer` Jalali parse flag | OK | Version marker |
| List View JS checkbox | OK (lazy require) | Docs only |

## Conversion behavior (unchanged contract)

- Metadata-driven `Date` / `Datetime` only (incl. child tables)
- Jalali ON → `convert_export_value` / `toshamshi`
- Jalali OFF → stock Gregorian
- No regex on finished files
- Import: `import_dates_from_jalali` → Gregorian Python date/datetime before stock parse

## Upgrade / deploy

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
# Restart web/workers so Python patches reload
bench restart
```

No schema migration.

## Remaining limitations / notes

- Browser Desk click-through for Export dialog was **API-validated**; full Cypress
  Desk UI pass is recommended on staging (NOT fully automated here).
- Ambiguous locale-formatted Gregorian strings (e.g. `10.04.2026`) may parse
  incorrectly depending on Frappe `getdate` / locale — pre-existing, not introduced
  by this release.
- Import provider tables (new Frappe feature) inherit fieldtype conversion when
  Date/Datetime columns are present in the export field list.

## Test coverage

- `test_list_export_jalali` — List View / download_template Jalali ON/OFF, CSV/XLSX
- `test_data_export_jalali` — Data Export page path
- `test_frappe_io_compat` — signature, idempotent apply, import flag, smoke download
- `utils.test_data_io` — conversion helpers
