# Release Notes — persian_calendar 1.9.0

**Date:** 2026-08-04  
**Platform validated:** Frappe **16.29.0** · ERPNext **16.30.0** · HRMS **16.14.0** (optional)

---

## Highlights

- Fixes blank/white **Job Card** (and any Datetime-heavy form) when **Display Calendar = Gregorian**.
- Root cause: Frappe ≥16.29 `ControlDatetime.set_formatted_input` calls `this.sync_datepicker_state`, which was missing on `JalaliControlDatetime` (inherits via `ControlDate`, not `ControlDatetime`).

---

## Symptom

- Route: Job Card form
- Profile: Display Calendar = Gregorian
- Browser: Unhandled Promise Rejection — `TypeError: this.sync_datepicker_state is not a function`
- Result: blank page

Jalali Display Calendar was unaffected (uses a different `set_formatted_input` path).

---

## Fix

`JalaliControlDatetime` now delegates Frappe `ControlDatetime`-only methods that Gregorian mode needs when calling into the captured upstream prototype:

- `sync_datepicker_state` (critical)
- `get_start_date`, `set_description`, `get_user_time_zone`, `set_datepicker`, `get_model_value`

No ERPNext/Frappe source edits. No Business Calendar changes. Storage remains Gregorian.

---

## Upgrade notes

1. Update to **1.9.0**.
2. `bench build --app persian_calendar`
3. `bench --site <site> clear-cache`
4. Hard-refresh the browser (stale `jalali_support.bundle.*.js` will keep the bug).
5. Open Job Card with Display Calendar = Gregorian and confirm the form renders.

---

## Compatibility

| Component | Validated |
|-----------|-----------|
| persian_calendar | **1.9.0** |
| Frappe | **16.29.0** |
| ERPNext | **16.30.0** |

`sync_datepicker_state` was introduced in Frappe 16.29 (`fix(datetime): synchronize picker state on form refresh`).

---

## Tests

- Source invariant: `jalali_support/test_gregorian_datetime_control.py`
- Cypress: `cypress/integration/gregorian_job_card_datetime.js` (when desk is available)
- Full app suite + `release_check`

---

## Unchanged

- Business Calendar / `BusinessPeriodEngine`
- `toshamshi` / `toshamsi`
- Jalali Display Calendar picker behaviour
- Gregorian storage semantics
