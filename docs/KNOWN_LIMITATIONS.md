# Known Limitations — persian_calendar 1.8.0

Real, current limitations only. Completed features are not listed here.

---

## Business Calendar (deferred domains)

| Area | Limitation |
|------|------------|
| **Exponential Smoothing Forecasting** | Calls `get_period_list` **without** `company`, so Financial Statements Business Calendar always takes the Gregorian path. Module is rebound as a consumer; Jalali activation needs Forecast Phase 3e (pass `company`). |
| **MRP Report planning buckets** | Daily / Weekly / Monthly columns use Gregorian `get_first_day` / `add_months` — planning calendar, not `BusinessPeriodEngine`. |
| **Issue Analytics** | Not integrated. |
| **Customer Acquisition** Business Calendar | Not integrated. |
| **Subscription / Auto Repeat / Maintenance** | Out of scope. |
| **HRMS payroll / attendance period reports** | Month Select `1–12`, day grids, Payroll Period DocType — not period-list analytics. |
| **Trends presentation labels** | Period **boundaries** may be Jalali-aware while some column headers still use Gregorian `%b` / `get_mon`. |

---

## Display / conversion

| Area | Limitation |
|------|------------|
| **Payroll month selector** | Integer months 1–12 remain Gregorian UI labels (not Date fields). |
| **Appointment email** | Uses unpatched `format_datetime` (Gregorian) in stock CRM path. |
| **First Response chart** | Axis may show raw ISO dates (not Display Calendar labels). |
| **Standard Print `formatdate`** | Use explicit `toshamshi` / `toshamsi` for Jalali in Print Formats. |
| **toshamshi heuristics** | Out-of-range month/day strings may overflow via jdatetime; years 1601–1699 treated as Gregorian. |

---

## Framework / upgrade debt

| Area | Limitation |
|------|------------|
| **Budget Variance dual path** | Stock English month-name keys vs Jalali date-range compatibility policy. |
| **Display vs BC `get_period_list` wrap order** | Display formatters may wrap FS `get_period_list` before the BC adapter (labels). |
| **Asset disposal patch** | Outside central `apply_calendar_patches` / test reset (intentional narrow Phase 2 patch). |
| **Weekly analytics** | Jalali Weekly is not defined — Stock/Sales Weekly always delegates to stock. |
| **Console bootstrap** | Interactive console must call `apply_calendar_patches()` manually. |
| **Historical migration** | Changing Company Business Calendar does not rewrite submitted Budget / schedule history. |

---

## Test debt (resolved in post-RC)

Display/coercion unit expectations that failed on the 1.8.0 RC bench were
**incorrect tests**, not Business Calendar regressions:

1. `test_jalali_datetime_to_gregorian` / `test_toshamshi_roundtrip_display` used
   an outdated mapping (`1405-02-01 ↔ 2026-04-20`). Independent `jdatetime`
   confirms `1405-02-01 → 2026-04-21` and `2026-04-20 → 1405-01-31`.
2. `test_time_fields_are_not_modified_on_validate` hard-coded a site Purchase
   Receipt name and wall-clock time; without that fixture the normalizer
   correctly falls back to `00:00:00`. Replaced with mocked `frappe.db.get_value`
   cases.

No Display Calendar or coercion **implementation** change was required.

---

## Related

- [`RELEASE_NOTES_1.8.0.md`](RELEASE_NOTES_1.8.0.md)
- [`COMPATIBILITY_MATRIX_1.8.0.md`](COMPATIBILITY_MATRIX_1.8.0.md)
- [`UPGRADE_GUIDE.md`](UPGRADE_GUIDE.md)
