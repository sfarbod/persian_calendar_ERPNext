# HRMS Business Calendar (Phase 6A)

**Status:** Implemented (Vehicle Expenses chart only)  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0** · HRMS **16.14.0**  
**Adapter:** `persian_calendar.calendar.integrations.vehicle_expenses`  
**Optional app:** Soft-skips when HRMS is not installed

Display Calendar for HRMS forms/lists/reports inherits the global desk layer.
This document covers the **audit**, **Business Calendar** scope, and intentional
skips.

---

## 1. Audit summary (HRMS 16.14.0)

**27** standard Script Reports under `hrms/hr/report` and `hrms/payroll/report`.

| Class | Count | Meaning |
|-------|------:|---------|
| **A — Display Calendar only** | Most | Typed Date/Datetime columns/filters; no Monthly/Quarterly period list |
| **B — Business Calendar candidate** | **1** | Groups expenses into Monthly periods via `get_period_list` |
| **C — Not applicable / Deferred** | Rest | Day grids, payroll month Select (1–12), Payroll Period DocType, DOB month |

### B — Implemented

| Report | Path | Why |
|--------|------|-----|
| **Vehicle Expenses** | `hrms.hr.report.vehicle_expenses.vehicle_expenses` | Chart calls `get_period_list(..., "Monthly")` without `company` |

### A — Display only (inherit global desk; no adapter)

Examples: Employee Leave Balance, Leave Ledger, Employee Advance Summary,
Unpaid Expense Claim, Shift Attendance, Employee Exits, Appraisal Overview,
Recruitment Analytics, Project Profitability, Bank Remittance, Salary Register,
Income Tax / PF / PT deduction reports, etc.

Standard Date/Datetime fieldtypes already pass through
`jalali_support.bundle.js` formatters. No HRMS-specific display adapters.

### C — Deferred (not BusinessPeriodEngine lists)

| Report | Reason |
|--------|--------|
| **Monthly Attendance Sheet** | Day-of-month grid for one payroll month; not a period-list chart |
| **Employee Birthday** | DOB month Select / Gregorian month filter |
| **Payroll month+year reports** | Integer month `1–12` + year Select (Salary Register filters, etc.) |
| **Payroll Period–bound reports** | Domain Payroll Period DocType, not Company Business Calendar FY |
| **Employee Analytics / Accrued Earnings** | Aggregation without FS-style Monthly/Quarterly period engines |

Do **not** patch these as speculative Business Calendar consumers.

---

## 2. Vehicle Expenses — upstream architecture

```text
execute(filters)
  → get_columns()
  → get_vehicle_log_data(filters)   # Vehicle Log.date between range
  → get_chart_data(data, filters)   # get_period_list Monthly (no company)
  → (columns, data, None, chart)
```

| Item | Value |
|------|--------|
| Source DocTypes | Vehicle, Vehicle Log, Vehicle Service |
| Business date | `Vehicle Log.date` |
| Metrics | Fuel expense (`qty × price`), service expense (sum of child rows) |
| Chart | Line; Monthly buckets |
| Company (upstream) | **None** on chart `get_period_list` |
| Table | Raw log rows (Display Calendar for Date column) |

---

## 3. Adapter design

| Mode | Behaviour |
|------|-----------|
| Gregorian company / missing company | Captured stock `get_chart_data` |
| Jalali company | Same chart loop; `get_period_list(..., company=filters.company)` |

- Reuses Financial Statements Business Calendar (`BusinessPeriodEngine`).
- **No** independent Jalali arithmetic.
- JS injects optional **Company** filter for chart BC resolution only.
- Data query is **not** filtered by company (upstream behaviour preserved).

Contract: `hrms.vehicle_expenses.get_chart_data` (`optional=True`).

---

## 4. Display findings

| Surface | Finding |
|---------|---------|
| HRMS forms / lists | Global Display Calendar |
| Vehicle Expenses Date column | Display Calendar |
| Payroll month Select (1–12) | Remains Gregorian UI labels (not Date fields) |
| CRM-style bypass | **None** found — no duplicate display adapters |

---

## 5. Contracts / diagnostics / registry

| Artifact | Entry |
|----------|--------|
| Contract | `hrms.vehicle_expenses.get_chart_data` |
| Registry | `HRMS Vehicle Expenses` → `implemented` |
| Registry | `HRMS Display Calendar` → `display_covered` |
| Registry | `HRMS Payroll / Attendance period reports` → `deferred` |
| Diagnostics | Validates `get_chart_data` adapter when HRMS importable |
| Soft-skip | `_apply_vehicle_expenses_patch` returns `APPLIED` if HRMS missing |

---

## 6. Tests

`persian_calendar/calendar/integrations/test_vehicle_expenses.py`

- Patch lifecycle / idempotency / soft-skip
- Gregorian delegation / missing company
- Esfand ↔ Farvardin boundary allocation
- Chart label consistency with FS period list
- Company switching
- Contract + registry inventory

---

## 7. Known limitations

1. Company filter does not restrict Vehicle Log rows (upstream has no company).
2. Only Monthly chart periods (upstream fixed periodicity).
3. Payroll / attendance period semantics remain deferred.
4. Without HRMS installed, Phase 6A patch is a no-op (by design).

---

## Related

- [`ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) — Compatibility Matrix
- [`BUSINESS_CALENDAR_DEVELOPER_GUIDE.md`](BUSINESS_CALENDAR_DEVELOPER_GUIDE.md) — Recipe N
- [`UPGRADE_GUIDE.md`](UPGRADE_GUIDE.md)
- [`CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md`](CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md) — similar Gregorian-delegate pattern
