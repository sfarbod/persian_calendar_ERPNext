# Persian Calendar — Cypress E2E

## Prerequisites

- Site with **Frappe**, **ERPNext**, and **persian_calendar** installed
- **Jalali Settings** enabled
- At least one **Job Card** with **Time Logs** rows
- Tests enabled: `bench --site SITE set-config allow_tests true`

## Run

From the Frappe app directory (uses Frappe’s Cypress install):

```bash
cd /workspace/development/frappe-bench/apps/frappe

export CYPRESS_BASE_URL=http://development.localhost:8000
export CYPRESS_ADMIN_PASSWORD=admin

npx cypress run \
  --config-file ../persian_calendar/cypress.config.js \
  --spec ../persian_calendar/cypress/integration/gregorian_stale_jalali_picker.js
```

Interactive:

```bash
npx cypress open --config-file ../persian_calendar/cypress.config.js
```

## Trace during manual/debug runs

In the browser console on Desk:

```javascript
frappe.persian_calendar.runtime.enableTrace();
```

After focusing a grid datetime field:

```javascript
frappe.persian_calendar.runtime.inspectDatetimeInput(
  document.querySelector('.form-grid [data-fieldname="from_time"] input')
);
frappe.persian_calendar.runtime.getDestroyLog();
```

## What the regression spec checks

1. Calendar preference **Jalali** → focus Time Logs `from_time` → Jalali UI may attach.
2. Preference **Gregorian** without `location.reload` → `cur_frm.refresh_fields()`.
3. Focus `from_time` / `to_time` again → no `NaN`, no `Invalid date`, no `data-has-jalali-datepicker`, no `jalaliDatepickerInstance`.
4. Save Job Card → no MySQL “Incorrect datetime value” / NaN in UI.
