# Persian Calendar 2.1.2 — Report Datetime Jalali Export

## Summary

Fixes Jalali conversion for **Datetime** and date+time values in report CSV/XLSX
exports (building on 2.1.1 Jalali-by-default report export).

## Root cause

v2.1.1 converted only columns with explicit `fieldtype` Date/Datetime and only
strict ISO strings **without** timezone suffixes. Gaps:

1. ISO datetimes with `Z` / `±HH:MM` offsets were rejected and left Gregorian.
2. Incomplete report column metadata (`fieldtype` None / Data) with real
   `datetime` objects or ISO values on date-like fieldnames was skipped.
3. Timezone-aware Python `datetime` values needed naive wall-clock normalization
   before conversion.

Stock Ledger’s exported **Date** column is `fieldtype: Datetime` /
`fieldname: date` (from `SLE.posting_datetime`). With the above gaps fixed,
combined date+time cells convert to Jalali while preserving the clock time.
Separate `posting_time` values are time-only and are never converted.

## Behavior

| Kind | Jalali ON | Jalali OFF |
|------|-----------|------------|
| Date | Jalali date | Gregorian |
| Datetime | Jalali date + original time | Gregorian |
| Time-only | Unchanged | Unchanged |
| Already-Jalali ISO | Unchanged | Unchanged |
| Ambiguous locale (`10.04.2026`) | Unchanged | Unchanged |

Default remains Jalali when the export flag is absent (2.1.1). Explicit `0` /
`false` keeps Gregorian.

## Detection strategy (generic)

1. Explicit `Date` / `Datetime` column metadata.
2. Python `date` / `datetime` objects (unless fieldtype is a non-date type such
   as Currency / Time).
3. Strict ISO date/datetime strings (optional fraction + timezone) when metadata
   is Date/Datetime, or when metadata is incomplete and the fieldname is a
   reliable date indicator (`date`, `*_date`, `posting_date`, …).

No Stock Ledger-specific converter.

## Upgrade

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
```

No migrate required. Restart workers if patches do not re-bind.

## Known limitations

- Locale-formatted datetimes (`03.10.2026 07:39:19`) are not converted (ambiguous).
- Desk Export dialog browser verification may still be pending on Stage.
- “Include filters” header values remain Gregorian.
