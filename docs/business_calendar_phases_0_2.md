# Business Calendar — Architecture & Migration Notes (Phases 0–2)

## What was implemented

### Phase 0 — Calendar Framework Core
- `persian_calendar/calendar/` with Engine, Provider interface, Gregorian & Jalali providers
- Public I/O: Gregorian `date` / ISO strings only
- `LastDayPolicy.CLAMP_DAY` (default) and `PRESERVE_MONTH_END`
- Stable `Period` keys (`2026-03`, `1405-01`, …) — not display strings

### Phase 1 — Company Business Calendar
- Custom Field `Company.business_calendar` (Select: Gregorian / Jalali, default **Gregorian**)
- Resolver: `CalendarEngine.for_company(company)` — never uses User Display preference
- Created on install/migrate; fixture included

### Phase 2 — Asset Depreciation
- `override_doctype_class` for Asset Depreciation Schedule, Asset, Asset Shift Allocation
- Narrow patch of `disposal_was_made_on_original_schedule_date` only
- Booked rows (`journal_entry` set) preserved by stock `clear()` behaviour

## Migration / backward compatibility

- Existing companies behave as **Gregorian** (default / empty field)
- No automatic enablement of Jalali Business Calendar
- No regeneration of existing schedules on migrate
- Submitted / booked depreciation rows are not silently rewritten
- Display Calendar (UI) unchanged in this phase

## Out of scope (not implemented)

Date Picker, Vue/Desk UI, Budget, FS, Forecast, MRP, HRMS, Subscription, Auto Repeat, Deferred Revenue, Payment Terms.
