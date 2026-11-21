# Persian Calendar 2.1.4 — List View Date Filter Compatibility

## Summary

Fixes Jalali calendar List View date filters after Frappe’s new filter panel
(Frappe ≥16.60 / `#44063`). Gregorian filtering was unaffected; Jalali mode
failed or returned empty/incorrect results (reproduced with Stock Entry
`MAT-STE-2026-37328`).

## Root cause

Frappe 16.60 introduced filter-panel APIs that assume a real air-datepicker:

1. `filter.js` → `destroy_calendar()` calls `field.datepicker.destroy()`.
2. Filter sheet `pick_date_step` applies picks with `field.datepicker.selectDate(dates)`.

Persian Calendar’s Jalali shim exposed `datepicker` without `destroy()`, and
`selectDate` was a no-op. Under Jalali mode that caused:

- Exceptions when recreating filter fields (missing `destroy`).
- Empty filter values when the filter sheet applied a date (`selectDate` no-op).
- Aggressive air-datepicker cleanup also tearing down **DateRange** pickers
  used by the default Date condition (**Between**).

Sending an unconverted Jalali date such as `1405-05-31` to MariaDB matches
**zero** Stock Entry rows (stored dates remain Gregorian, e.g. `2026-08-22`).

## Fix

- Shim `destroy()` safely closes/clears the Jalali picker.
- Shim `selectDate(dates)` converts native `Date` / strings to Gregorian and
  calls `control.set_value(...)`.
- Preserve DateRange and filter-panel air-datepickers during cleanup; run
  cleanup only when Jalali mode is active.
- Normalize Jalali strings in `ControlDateRange` parse/get_value.
- Keep `datepicker_options` on Jalali `ControlDate` for filter-sheet options.

## Upgrade

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
```

No migrate required. Hard-refresh the desk browser session after build.

## Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.60.2 |
| ERPNext | 16.60.0 |

## Known limitations

- DateRange (**Between**) still uses air-datepicker’s Gregorian UI; values are
  stored/queried as Gregorian. Single Date / Datetime filters use the Jalali
  picker. Full Jalali range UI may follow in a later release.
- Desk browser E2E of the filter sheet may still be pending where Computer Use
  permissions are unavailable.
