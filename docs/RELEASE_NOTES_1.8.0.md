# Release Notes — ERPNext Extensions 1.8.0

**Package:** `persian_calendar` **1.8.0**  
**Codename:** Business Calendar Framework (Release Candidate)  
**Date:** 2026-07-30  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0** · HRMS **16.14.0** (optional)

---

## Highlights

- End-to-end **Company Business Calendar** for accounting and analytics periods.
- **Jalali** period lists from a single **BusinessPeriodEngine** — no duplicate Jalali math in reports.
- **Gregorian** companies keep stock ERPNext behaviour via captured originals.
- Desk **Display Calendar** remains separate (presentation only).
- Upgrade safety: contracts, registry, diagnostics, `release_check`.

---

## Business Calendar Framework

| Layer | Role |
|-------|------|
| Storage | Always Gregorian / ISO in DB and APIs |
| Display Calendar | User/desk presentation (datepicker, formatters) |
| Business Calendar | Per-Company `Gregorian` \| `Jalali` |
| CalendarEngine | Provider resolver only |
| BusinessPeriodEngine | Canonical Monthly / Quarterly / Half-Yearly / Yearly generator |
| period_labels | Presentation labels — never allocation keys |

---

## Display Calendar

- Global desk Jalali support via `jalali_support.bundle.js` + datetime normalizer.
- **CRM** and **HRMS** forms/lists/report Date fields inherit global coverage (verified; no domain display adapters).
- Explicit print/email: `{{ toshamshi(doc.field) }}` / `toshamsi` alias.

---

## Financial Reports

- Profit & Loss, Balance Sheet, Cash Flow and other `get_period_list` consumers.
- Budget periods, Monthly Distribution, Trends, Budget Variance.

---

## Stock

- Stock Analytics (Weekly → stock; M/Q/H/Y → engine when Jalali).
- Delivery Note Trends / Purchase Receipt Trends via Trends controller.

---

## Manufacturing

- Production Analytics, Work Order Summary, Job Card Summary via Stock Analytics helper identity rebind.
- Phase 6B audit: no further adapters required for non-deferred reports.

---

## CRM

- Display Calendar: Outcome A (global).
- Sales Pipeline Analytics: Monthly/Quarterly Business Calendar on `Opportunity.expected_closing`.

---

## HRMS

- Display Calendar: global inheritance.
- Vehicle Expenses chart: Jalali periods when Company is set (optional app soft-skip).

---

## Framework / Diagnostics

- `apply_calendar_patches()` — FS, MD, Trends, BVR, Sales, Stock, SPA, Vehicle Expenses.
- 20 API contracts (HRMS optional).
- `bench execute persian_calendar.calendar.diagnostics.release_check` → **PASS** on validated bench.

---

## Upgrade Notes

1. Update app to **1.8.0**; migrate site if needed.
2. Configure **Company.business_calendar**.
3. `bench build --app persian_calendar` and clear cache.
4. Run `release_check`; resolve any FAIL before production.
5. After ERPNext upgrades, follow [`UPGRADE_GUIDE.md`](UPGRADE_GUIDE.md).

---

## Known Limitations

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md). Summary:

- Exponential Smoothing Forecasting (no `company` on `get_period_list`) — Forecast deferred.
- MRP Report planning buckets — not BusinessPeriodEngine.
- Payroll month Select (1–12) — Gregorian UI labels.
- Trends column presentation labels may still use Gregorian `%b` in places.
- Three pre-existing Display/coercion unit tests fail on the validation bench (not Business Calendar arithmetic).

---

## Compatibility

| Component | Version |
|-----------|---------|
| persian_calendar | **1.8.0** |
| Frappe | 16.28.0 (validated) |
| ERPNext | 16.29.0 (validated) |
| HRMS | 16.14.0 (optional) |
| Python | ≥ 3.10 |

Full matrix: [`COMPATIBILITY_MATRIX_1.8.0.md`](COMPATIBILITY_MATRIX_1.8.0.md).

---

## Developer Notes

- Prefer `override_doctype_class`; free-function patches only via `apply_calendar_patches`.
- Never patch `frappe.utils.formatdate` / `format_datetime` globally.
- Never key on translated month names.
- Extension recipe: [`BUSINESS_CALENDAR_DEVELOPER_GUIDE.md`](BUSINESS_CALENDAR_DEVELOPER_GUIDE.md) · [`SDK.md`](SDK.md).
- Changelog: [`../CHANGELOG.md`](../CHANGELOG.md).
