# Display Calendar — Gregorian Datetime control (1.9.0)

## Symptom

Job Card opens as a blank page when **Display Calendar = Gregorian**.

Console:

```text
Unhandled Promise Rejection: TypeError: this.sync_datepicker_state is not a function
```

Call site (Frappe controls bundle / `datetime.js`):

```js
this.sync_datepicker_state(frappe.datetime.user_to_obj(value));
```

## Root cause

1. Frappe **16.29** added `ControlDatetime.sync_datepicker_state` and calls it from
   `ControlDatetime.set_formatted_input` on form refresh (upstream
   `fix(datetime): synchronize picker state on form refresh`).
2. `persian_calendar` replaces controls with:
   - `JalaliControlDate extends ControlDate`
   - `JalaliControlDatetime extends JalaliControlDate` (**not** `ControlDatetime`)
3. In **Gregorian** mode, `JalaliControlDatetime.set_formatted_input` delegates to
   `BaseControlDatetime.prototype.set_formatted_input.call(this, …)`.
4. That upstream method invokes `this.sync_datepicker_state(...)`, but `this` is a
   `JalaliControlDatetime` whose prototype chain never included
   `ControlDatetime.prototype` → **TypeError** → unhandled rejection → blank form.
5. **Jalali** mode does not take that delegation path (uses Jalali display formatting).

## Why Job Card

Job Card **Time Logs** use child **Datetime** fields (`from_time`, `to_time`). Opening
an existing Job Card refreshes many Datetime controls at once, so the bug surfaces
immediately. Any DocType with Datetime fields is vulnerable under Gregorian Display.

## Fix

Delegate missing `ControlDatetime`-only methods on `JalaliControlDatetime`, especially
`sync_datepicker_state`, to the captured `BaseControlDatetime.prototype`.

## Not changed

- Business Calendar / period engine
- Gregorian storage
- Jalali picker implementation
- `toshamshi` / `toshamsi`

## After upgrade

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
# hard refresh browser
```
