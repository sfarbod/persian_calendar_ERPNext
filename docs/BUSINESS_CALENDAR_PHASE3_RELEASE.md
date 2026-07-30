# Business Calendar — Phase 3 Final Release Readiness

Stabilization report after Phases 0 → 3d-2. **No new Business Calendar features** in this phase.

| Field | Value |
|-------|--------|
| Status | **Ready with caveats** |
| Platform validated | Frappe 16.28 / ERPNext 16.29 / Python ≥ 3.10 |
| Framework tests | **211** (all passed at hardening) |
| Architecture | Frozen — `docs/ARCHITECTURE_BUSINESS_CALENDAR.md` |
| Developer Guide | `docs/BUSINESS_CALENDAR_DEVELOPER_GUIDE.md` |

---

## 1. Architecture status

Three-layer model unchanged: Storage (Gregorian) → Display (user UI) → Business Calendar (Company).

`BusinessPeriodEngine` remains the only canonical period-list generator for Jalali business periods. Gregorian paths delegate to captured ERPNext originals. Display Calendar is not used for business math.

---

## 2. Implemented modules

| Module | Mechanism |
|--------|-----------|
| Company Business Calendar field | Custom field + resolver |
| CalendarEngine / providers | Core |
| BusinessPeriodEngine + labels | Core |
| Assets / depreciation | DocType overrides + narrow disposal patch |
| Financial Statements `get_period_list` | Central applicator |
| Budget periods | `override_doctype_class` |
| Monthly Distribution | Class override + free-function patches |
| Trends `get_period_date_ranges` | Central applicator |
| Budget Variance `execute` | Central applicator |
| Sales / Purchase Analytics | Shared `Analytics` method patches |
| Stock Analytics | Free-function patches |
| Production / WO / Job Card Summary | Identity-rebind of Stock helpers only |

---

## 3. Deferred modules (explicit non-goals)

Forecast redesign, Issue Analytics, core MRP/MPS, HRMS payroll/attendance period reports (Vehicle Expenses chart done in 6A), Subscription / Auto Repeat / Maintenance, Trends presentation-label cleanup (Phase 6), historical auto-migration.

---

## 4. Known limitations

| Item | Notes |
|------|--------|
| Console bootstrap | Call `apply_calendar_patches()` explicitly |
| Dual FS `get_period_list` | Display formatters may wrap before BC adapter; **boundaries** OK, **labels** may follow Display |
| Trends column headers | May still use Gregorian `%b` while ranges are Jalali-correct |
| Weekly analytics | Always stock ISO weeks — no Jalali week semantics |
| Stale budget helper | Not hooked to Budget validate |
| Asset disposal patch | Outside central applicator (intentional) |

---

## 5. Technical debt

- Budget Variance dual path (month-name stock keys vs Jalali date ranges).
- Sales/Stock `_snap_jalali_start` jdatetime quarter/half floor (small; engine still owns generation).
- Unwired `validate_stale_budget_calendar` / incomplete consolidated FS mixed-calendar enforcement.
- Asset disposal not restored by `reset_calendar_patches_for_tests`.
- Type-hint density uneven across older vs newer adapters.

---

## 6. Presentation debt

- Trends / related Gregorian abbreviation headers.
- FS Display-label wrapper interaction (above).
- WO / Job Card chart labels use period keys when Jalali (acceptable helper-only coverage).

---

## 7. Performance observations

| Area | Finding | Action |
|------|---------|--------|
| BusinessPeriodEngine | O(periods); small | None |
| Sales Analytics | Periods cached on Analytics; BC resolve may repeat per method | Acceptable |
| Stock Analytics | BC + periods cached on filters; linear SLE→period map | None |
| Budget | Single generate | None |
| Trends | Single generate | None |
| BVR | Monthly generate per overlapping distribution; actuals O(txns×periods) | Documented; no premature optimize |

No measurable regression introduced in Phase 3 Final (no functional changes).

---

## 8. Test matrix summary

| Module | Tests | G | J | Patch | Display indep. | Mixed co. | Carry / hist. | Perf |
|--------|------:|:-:|:-:|:----:|:--------------:|:---------:|:-------------:|:----:|
| Providers | 41 | ✓ | ✓ | — | — | — | leap | — |
| Period engine | 30 | ✓ | ✓ | — | labels | consol. smoke | — | — |
| Resolver | 6 | ✓ | ✓ | — | ✓ | — | — | — |
| Patches | 14 | ✓ | ✓ | ✓ | — | — | — | — |
| Assets | 10 | ✓ | ✓ | disposal | ✓ | — | — | — |
| Budget | 10 | ✓ | ✓ | — | ✓ | — | — | — |
| Monthly Dist. | 14 | ✓ | ✓ | ✓ | — | — | — | — |
| Trends | 19 | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Budget Variance | 18 | ✓ | ✓ | ✓ | ✓ | — | ✓ | — |
| Sales Analytics | 19 | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Stock Analytics | 30 | ✓ | ✓ | ✓ | ✓ | N/A | carry-fwd | ✓ |

**Missing / deferred scenarios (documented, not blocking):** dedicated FS adapter module tests (covered via patches + engine); wired stale-budget DocType event; full upstream ERPNext suite green on this site; multi-company Stock Analytics (stock UI is single-company).

---

## 9. ERPNext Upgrade Checklist

On every Frappe/ERPNext upgrade:

1. Re-read patched source modules and confirm **signatures** for every applicator target (FS, MD, Trends, BVR, Sales Analytics methods, Stock Analytics helpers).
2. Diff **direct-import consumers** against registries (`GET_PERIOD_LIST_CONSUMERS`, `MD_PERIODWISE_CONSUMERS`, `TRENDS_PERIOD_RANGES_CONSUMERS`, `STOCK_ANALYTICS_PERIOD_CONSUMERS`).
3. Confirm Sales Analytics still shares one `Analytics` class with Purchase Analytics.
4. Confirm Stock Analytics still returns `list[[start,end]]` and that `get_periodic_data` still keys off `get_period`.
5. Confirm `round_down_to_nearest_frequency` is still only used from stock `get_period_date_ranges` (do not patch it).
6. Run all **211** framework modules; treat new failures as regressions unless proven unrelated.
7. Spot-check Gregorian company parity for FS, Trends, Sales, Stock.
8. Spot-check Jalali Monthly Farvardin–Esfand + leap Esfand for engine + Stock carry-forward.
9. Verify hooks still list `before_request_calendar_bootstrap` **after** Display formatters (document label interaction if order changes).
10. Do **not** merge Trends and Stock/Sales same-named helpers into one registry.

### Upgrade risks (by patch)

| Patch | Risk | Private API? |
|-------|------|--------------|
| FS `get_period_list` | Signature / return shape; consumer list growth | Public report helper |
| MD periodwise / % | Key format assumptions | Public |
| Trends ranges | `(period, fiscal_year)` contract | Public |
| BVR `execute` | Report assembly / month-name keys | Report-local |
| Sales `Analytics` methods | Class refactor / chart field lookup | Report class |
| Stock helpers | Carry-forward / fieldname scrub | Report-local |
| Asset disposal boolean | Narrow helper rename | Module function |

---

## 10. Production readiness assessment

**Recommendation: Ready with caveats**

Safe for production on sites that:

- Use Company Business Calendar Gregorian (default) or Jalali for covered accounting/stock analytics modules.
- Accept Trends / FS **presentation** caveats until Phase 6.
- Call `apply_calendar_patches()` in console/automation contexts.
- Re-run the Upgrade Checklist on ERPNext bumps.

Not a substitute for full ERPNext CI green or E2E desk sign-off on every report UI.

---

## 11. Phase 3 Final changes (hardening only)

- Documentation: Architecture applicator table, test counts (211), limitations, debt, stale-helper wording.
- Developer Guide / period-engine applicator tree updated for 3d.
- Stock adapter: use `BUSINESS_CALENDAR_GREGORIAN` constant (no behavior change).
- Patch applicator: warn if Display-label FS wrapper is captured as original (observability only).
- This release report.

**No new ERPNext module integrations. No architecture redesign. No version bump.**

---

## Post–Phase 3 notes

- **Phase 4a** — Upgrade safety (`docs/UPGRADE_GUIDE.md`, contract tests, diagnostics).
- **Phase 4b** — Public SDK (`persian_calendar.api`, `docs/SDK.md`); no business behaviour changes.