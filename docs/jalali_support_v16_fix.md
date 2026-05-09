# Jalali support on Frappe / ERPNext v16 — technical note

This document describes the **minimal safe fix** for Persian Calendar (`persian_calendar` / `jalali_support`) on **v16**, focusing on export stability and keeping Jalali **UI-first**.

## Root cause of HTTP 500 on export (Excel)

Frappe v16’s `frappe.utils.xlsxutils.make_xlsx()` accepts keyword arguments such as **`header_index`** and **`has_filters`** (used by Query Report export and Auto Email Report XLSX).

The app previously replaced `make_xlsx` with a thin wrapper that only accepted `(data, sheet_name, wb, column_widths)`. When the core called:

```python
make_xlsx(data, sheet_name, column_widths=..., header_index=..., has_filters=...)
```

Python raised **`TypeError: unexpected keyword argument 'header_index'`**, which surfaced as **HTTP 500** during Excel export.

**Fix:** Do **not** monkey-patch `make_xlsx`. Optionally **`importlib.reload(frappe.utils.xlsxutils)`** on requests when a legacy `_jalali_patched` flag is still present on long-lived workers after upgrading the app.

## Why Python `formatdate` / `format_datetime` / `format_value` monkey patches were removed

Replacing `frappe.utils.formatdate`, `format_datetime`, and `frappe.utils.formatters.format_value` globally affected:

- Server-side formatting used by **exports**, **reports**, **Print**, and other code paths that expect **Gregorian / ISO** semantics for stored data.

That conflicted with the requirement that **database values and APIs remain Gregorian**. Those monkey patches were removed; Jalali display is handled primarily in **desk JavaScript** (`jalali_support/formatters.js`, `persian_calendar.js`, Jalali datepicker).

## Current architecture: UI Jalali, backend Gregorian

| Layer | Behaviour |
|--------|-----------|
| **Browser (desk)** | Jalali calendar picker; `frappe.datetime` / `frappe.form.formatters` wrappers show Jalali when effective calendar is Jalali; **`user_to_str`** converts typed Jalali strings back to Gregorian before requests where applicable. |
| **Server** | Stock Frappe formatting for dates in Python — **Gregorian / ISO** for exports and APIs. |
| **Exports (CSV/XLSX)** | Native `make_xlsx` / export code paths; **Gregorian** cell values and typed `datetime.date` / `datetime.datetime` as Frappe expects. |
| **Filters** | Client sends **Gregorian** date strings when conversion helpers are active (`user_to_str` path); stored filters remain compatible with the ORM. |

## Hooks (`hooks.py`)

There is **no** eager `import persian_calendar.jalali_support.formatters` at module load solely to activate monkey patches. `before_request` still calls:

- `setup_jalali_formatters` — legacy xlsx cleanup + optional ERPNext **`get_period_list`** label patch only.
- `setup_fiscal_year_override` — Fiscal Year validation override (applied once per process).

## Test checklist

After `bench build --app persian_calendar`, `bench --site <site> clear-cache`, and `bench restart`:

1. Enable Jalali in **Jalali Settings**; set user calendar to Jalali if testing full UI.
2. Open desk — **browser console** should be free of Jalali helper **`ReferenceError`** spam.
3. **Query Report** → **Export → Excel** — succeeds (**HTTP 200**), dates are Gregorian in the file.
4. **List view** → **Export** — succeeds.
5. **Report Builder** export — succeeds.
6. **Auto Email Report** with **XLSX** — succeeds if configured.
7. Smoke-test **date filters** on a list/report — filters still apply correctly (Gregorian in requests).

## Known remaining risk: `get_period_list` label patch

When ERPNext is installed, `persian_calendar.jalali_support.formatters.patch_get_period_list()` may replace **`erpnext.accounts.report.financial_statements.get_period_list`** once per process to show **Jalali month labels** on financial statement period columns.

- **Scope:** Report **labels / presentation**, not raw numeric export columns from GL.
- **Risk:** Any ERPNext upgrade that changes that module’s API could require revisiting the patch; it is isolated to this app.

---

*Last updated for Frappe/ERPNext v16 compatibility work.*
