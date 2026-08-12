# Persian Calendar 2.0.0 — Business Calendar Compatibility Release

**Release type:** Major (compatibility / architecture)

**Reason for major bump:** Systematic audit and hardening of the Business Calendar
compatibility boundary so **presentation labels are never used as allocation keys**
when Company Business Calendar is Jalali. This changes the internal adapter surface
(new FAR chart adapter, shared period-allocation helpers, extended patch registry)
while preserving Gregorian company parity and Gregorian DB storage.

## Validated matrix (this release)

| Component | Validated on bench |
|-----------|-------------------|
| Frappe | 16.31.0 |
| ERPNext | 16.32.0 |
| HRMS | 16.16.0 |
| persian_calendar | **2.0.0** |

Compatible with the stated target band Frappe ≥16.30 / ERPNext ≥16.31 (Business Calendar
adapters assume ERPNext v16 financial-statement / analytics APIs).

## Architecture rule (2.0.0)

| Concept | Role |
|---------|------|
| Period identity | `period.key` or `(from_date, to_date)` |
| Period boundaries | Gregorian `from_date` / `to_date` (DB storage) |
| Period display label | `period.label` — presentation only |

**Never** allocate, look up, or group rows using `formatdate(..., "MMM YYYY")` matched
against `get_period_list` labels under Jalali BC.

Shared helpers (`persian_calendar.calendar.adapter_helpers`):

- `find_period_for_date(period_list, value_date)`
- `find_period_index_for_date(...)`
- `aggregate_by_period_bounds(...)` — Vehicle Expenses / FAR style

## Confirmed defect fixed — Fixed Asset Register

**Symptom:** Assets workspace → Asset Value Analytics → `KeyError: 'Apr 2026'`.

**Cause:** PC FS `get_period_list` returns Jalali labels (`Farvardin 1405`, …) while stock
`prepare_chart_data` buckets with Gregorian `formatdate(date, "MMM YYYY")`.

**Fix:** Adapter `persian_calendar.calendar.integrations.fixed_asset_register.prepare_chart_data`

- Gregorian company → stock path (parity)
- Jalali company → allocate by `from_date`/`to_date`; emit Jalali labels only for chart axes

Stale chart fixture fields `period_start_date`/`period_end_date` (2020-04-01…2021-03-31) and
dynamic `from_date`/`to_date` remain ERPNext Dashboard Chart configuration noise; they are
**not** the KeyError root cause under Fiscal Year mode.

## Modules audited

| App / Module | Audited | Issue Found | Fix Required | Status |
|---|---|---|---|---|
| PC FS `get_period_list` consumers (P&L, BS, CF, ratios, deferred, template engine, sales partner target, exponential smoothing) | Yes | Label change; consumers use `period.key` / date bounds | No | Unaffected (safe) |
| ERPNext Fixed Asset Register chart | Yes | Label-as-key KeyError | Yes | **Fixed in 2.0.0** |
| ERPNext Asset depreciation (existing PC controllers) | Yes | Month arithmetic (separate) | Already adapted | Unaffected class |
| ERPNext Sales / Purchase Analytics | Yes | Historical scrub(label) | Already adapted | Safe |
| ERPNext Stock Analytics + mfg rebinds | Yes | — | Already adapted | Safe |
| ERPNext Budget Variance | Yes | English month names | Already adapted | Safe |
| ERPNext Sales Pipeline Analytics | Yes | Gregorian SQL months | Already adapted | Safe |
| ERPNext Gross Profit monthly field | Yes | Display field only, no `get_period_list` | No | N/A |
| ERPNext MRP planning labels | Yes | Deferred planning buckets | No | Deferred / N/A |
| HRMS Vehicle Expenses | Yes | Missing `company=` | Already adapted | Safe (reference) |
| HRMS other payroll/attendance | Yes | Not FS period-list label keys | No | Display / deferred |
| Lending / Payments | Yes | No `get_period_list` label-key pattern | No | Not affected |
| Helpdesk ticket_stats | Yes | Gregorian `%b %Y` fill (no FS adapter) | No | Not affected |
| CRM (ERPNext SPA) | Yes | Covered by SPA adapter | Already adapted | Safe |
| Insights / LMS / Wiki / Raven / DMS / Telephony | Yes | No PC period-list coupling | No | Not affected |
| erpnext_extensions | Yes | No FAR/`get_period_list` label-key defects found | No | Not affected |

## Fixes implemented in 2.0.0

1. Shared period-bound allocation helpers
2. Fixed Asset Register `prepare_chart_data` adapter + patch lifecycle
3. Contract `far.prepare_chart_data`, registry + diagnostics wiring
4. Regression tests (helpers + FAR Jalali FY 1405 / Date Range)

## Unaffected / already safe

Classic financial statements, sales/stock analytics adapters, budget variance, sales pipeline,
Vehicle Expenses chart adapter, depreciation schedule controllers.

## Known limitations

- MRP / MPS planning bucket labels remain Gregorian (deferred; not FS `get_period_list`)
- Helpdesk monthly stats remain Gregorian series fill (no Business Calendar adapter)
- Insights date engine not rewritten
- Dashboard Chart static India FY residues in fixtures are cosmetic under Fiscal Year filters

## Upgrade notes (1.9.0 → 2.0.0)

```text
No schema/data migration required.
```

Recommended after upgrade:

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
bench --site <site> migrate   # syncs Installed Application version only
```

Gregorian companies must behave as stock ERPNext. Jalali companies get corrected FAR chart
allocation without changing Asset DocType storage (Gregorian dates).

## Test focus

- Unit: period helpers, FAR patch lifecycle, Jalali FY 1405 asset `2026-04-05`
- Existing: contracts, financial statements, Vehicle Expenses, sales/stock/SPA/BVR
- Manual: `/desk/assets` Asset Value Analytics loads without KeyError
