# Release Candidate Report — 1.8.0

**Product:** ERPNext Extensions / `persian_calendar`  
**Version:** **1.8.0**  
**Date:** 2026-07-30  
**Phase:** 7 — Release Candidate (no new features)

---

## 1. Framework status

| Check | Result |
|-------|--------|
| Storage Gregorian | Pass |
| Display ≠ Business | Pass |
| BusinessPeriodEngine canonical | Pass |
| CalendarEngine resolver-only | Pass |
| Approved patch surface | Pass |
| `release_check` | **PASS** |
| Contracts (20) | **PASS** |
| Compatibility (Frappe 16.28 / ERPNext 16.29) | **SUPPORTED** |

---

## 2. Global audit summary

### Implemented integrations

Financial Statements · Assets · Budget · Monthly Distribution · Trends · Budget Variance · Sales Analytics · Purchase Analytics · Stock Analytics · Production / WO / JC (rebind) · CRM Pipeline · HRMS Vehicle Expenses · toshamshi API · Display Calendar (global + CRM/HRMS verified)

### Deferred

Forecast (Exponential Smoothing) · MRP/MPS · Issue Analytics · HRMS payroll/attendance periods · Customer Acquisition · Subscription/Auto Repeat/Maintenance · Trends presentation labels

### Orphans / dead code

- No orphan adapters under `integrations/`.
- `adapter_template.py` is intentional scaffold (not loaded).
- `business_calendar_phases_0_2.md` retained as history.

### Duplicate helpers

- Shared logic centralized in `adapter_helpers.py` (Phase 4b).
- Same-named `get_period_date_ranges` kept on **separate** modules (Trends vs Stock vs Sales) by design.

---

## 3. Test summary (validation bench)

| Metric | Value |
|--------|------:|
| Tests run | **367** (307 + 60 category split; +1 vs RC after Time-field unit split) |
| Passed | **367** |
| Failed | **0** (Display/coercion test debt resolved post-RC — incorrect expectations) |
| Skipped | **0** observed |

| Area (approx.) | Tests |
|----------------|------:|
| Framework engine / providers / resolve | 77 |
| Lifecycle / contracts / SDK | 41 |
| toshamshi / jalali utils | 39 |
| Trends / Budget Variance | 37 |
| Stock (+ MFG rebind coverage) | 30 |
| Budget / Monthly Distribution | 24 |
| Sales Analytics | 19 |
| CRM Display | 19 |
| CRM Pipeline BC | 14 |
| HRMS Vehicle Expenses | 12 |
| Assets | 10 |
| Display preference / normalizer / I-O | ~29 |

Business Calendar arithmetic suites and `release_check` / contracts: **green**.

---

## 4. Contract summary

20 contracts; all resolve on validated ERPNext 16.29. Optional: `hrms.vehicle_expenses.get_chart_data`.

---

## 5. Diagnostics summary

`persian_calendar.calendar.diagnostics.run` / `release_check`:

- compatibility PASS  
- patches applied  
- contracts OK  
- registry healthy  
- import graph OK  
- hierarchies OK  
- conversion_api OK  

---

## 6. Documentation summary

| Artifact | Path |
|----------|------|
| Changelog | `CHANGELOG.md` |
| Release Notes | `docs/RELEASE_NOTES_1.8.0.md` |
| Compatibility Matrix | `docs/COMPATIBILITY_MATRIX_1.8.0.md` |
| Known Limitations | `docs/KNOWN_LIMITATIONS.md` |
| Architecture | `docs/ARCHITECTURE_BUSINESS_CALENDAR.md` |
| Developer Guide | `docs/BUSINESS_CALENDAR_DEVELOPER_GUIDE.md` |
| Upgrade Guide | `docs/UPGRADE_GUIDE.md` |
| SDK / API | `docs/SDK.md`, `docs/API_REFERENCE.md` |

---

## 7. Upgrade safety

- Version bump **1.7.0 → 1.8.0** (`persian_calendar/__init__.py`; dynamic via flit).
- Post-upgrade: migrate, set Company Business Calendar, build assets, `release_check`.
- ERPNext upgrades require contract / consumer re-audit (`UPGRADE_GUIDE.md`).

---

## 8. Release readiness

| Criterion | Met |
|-----------|-----|
| No failing diagnostics | Yes |
| No failing contracts | Yes |
| No failing release_check | Yes |
| Documentation complete | Yes |
| Version 1.8.0 | Yes |
| CHANGELOG | Yes |
| Release Notes | Yes |
| Compatibility Matrix | Yes |
| Registry complete | Yes |
| No new BC features in Phase 7 | Yes |

**Verdict:** Release Candidate **ready** (with documented Display/coercion test debt and deferred domains).
