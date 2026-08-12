# Changelog

All notable changes to **persian_calendar** (Persian Calendar / ERPNext Extensions Jalali support) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-08-12

### Added

- Shared period-bound allocation helpers: `find_period_for_date`,
  `find_period_index_for_date`, `aggregate_by_period_bounds`.
- Fixed Asset Register `prepare_chart_data` Business Calendar adapter
  (Jalali → allocate by `from_date`/`to_date`; Gregorian → stock parity).
- Contract `far.prepare_chart_data` and registry/diagnostics coverage.

### Fixed

- **Assets / Asset Value Analytics:** `KeyError: 'Apr 2026'` when Company Business
  Calendar is Jalali. Upstream FAR chart keyed Gregorian `formatdate(..., "MMM YYYY")`
  against Jalali `get_period_list` labels.

### Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.31.0 |
| ERPNext | 16.32.0 |

No schema/data migration required from 1.9.0.

See [`docs/RELEASE_2_0_0.md`](docs/RELEASE_2_0_0.md).

## [1.9.0] — 2026-08-04

### Fixed

- **Gregorian Display Calendar:** Job Card (and other Datetime forms) no longer blank with
  `TypeError: this.sync_datepicker_state is not a function`.
  `JalaliControlDatetime` now delegates Frappe ≥16.29 `ControlDatetime`-only methods
  (`sync_datepicker_state` and related) that Gregorian mode invokes via upstream
  `.call(this)` into the captured prototype.

### Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.29.0 |
| ERPNext | 16.30.0 |

Requires asset rebuild + cache clear after upgrade (`bench build --app persian_calendar`).

### Developer

- Invariant tests for `sync_datepicker_state` on `JalaliControlDatetime`.
- Cypress: `gregorian_job_card_datetime.js`.

See [`docs/RELEASE_NOTES_1.9.0.md`](docs/RELEASE_NOTES_1.9.0.md).

## [1.8.0] — 2026-07-30

Business Calendar Framework release candidate. Storage remains Gregorian; Display Calendar is presentation-only; Company Business Calendar drives period analytics via `BusinessPeriodEngine`.

### Added

- Company **Business Calendar** field and resolution (`Gregorian` / `Jalali`).
- **Calendar providers** + **CalendarEngine** (provider resolver only).
- **BusinessPeriodEngine** — canonical Monthly / Quarterly / Half-Yearly / Yearly period lists.
- **Financial Statements** `get_period_list` adapter + consumer identity rebind.
- **Budget** period generation via DocType override.
- **Monthly Distribution** periodwise / percentage adapters.
- **Trends** `get_period_date_ranges` + **Budget Variance** `execute` adapter.
- **Sales / Purchase Analytics** shared `Analytics` class adapters.
- **Stock Analytics** free-function adapters + manufacturing identity rebinds (Production Analytics, Work Order Summary, Job Card Summary).
- **CRM Sales Pipeline Analytics** Business Calendar allocation on `expected_closing`.
- **HRMS Vehicle Expenses** chart periods via Financial Statements `get_period_list` + Company filter (soft-skip without HRMS).
- Public **`toshamshi` / `toshamsi`** conversion API (Jinja + Python) with contracts.
- Upgrade safety: **contracts**, **registry**, **diagnostics**, **`release_check`**, public **SDK**.
- Desk Display Calendar coverage verified for CRM and HRMS (no domain-specific display adapters).
- Manual date-entry shorthand for Jalali desk inputs (from 1.7.0 line).

### Changed

- Centralized free-function patching through `apply_calendar_patches()` (idempotent lifecycle).
- Gregorian Company Business Calendar **delegates** to captured upstream callables.
- Labels never used as business keys; stable `BusinessPeriod.key` / scrubbed fieldnames.

### Improved

- Developer Guide recipes, Architecture Compatibility Matrix, Upgrade Guide.
- Manufacturing / Stock final audit (Phase 6B) — no speculative adapters.
- Soft-skip optional HRMS contract when the app is not installed.

### Fixed

- Sales Pipeline Jalali Month/Quarter buckets no longer follow Gregorian SQL `MONTH` / `QUARTER`.
- Vehicle Expenses chart can resolve Jalali periods when Company is selected.
- Financial / analytics consumers rebound after early imports.

### Developer

- `persian_calendar.api` surface for patches, resolution, and conversion.
- `docs/SDK.md`, `docs/API_REFERENCE.md`, adapter template (scaffold only).
- Contract catalog: 20 callables (1 optional: HRMS Vehicle Expenses).

### Framework

- Invariants: Storage = Gregorian; Display ≠ Business; single period engine; no `frappe.utils` monkey-patches.

### Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.28.0 |
| ERPNext | 16.29.0 |
| HRMS (optional) | 16.14.0 |
| Python | ≥ 3.10 (validated 3.14.2) |

### Upgrade Notes

1. Install / update app; run `bench migrate` if Company Business Calendar field is new on the site.
2. Set **Company → Business Calendar** (`Jalali` or `Gregorian`).
3. Clear cache / rebuild assets: `bench build --app persian_calendar` && `bench --site <site> clear-cache`.
4. Run `bench --site <site> execute persian_calendar.calendar.diagnostics.release_check` — expect **PASS**.
5. Re-audit patch targets after any ERPNext upgrade (see `docs/UPGRADE_GUIDE.md`).

See also: [`docs/RELEASE_NOTES_1.8.0.md`](docs/RELEASE_NOTES_1.8.0.md), [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).

## [1.7.0] — 2026-07-14

### Added

- Manual Jalali date entry with shorthand formats in the desk datepicker.

### Changed

- Version bump to 1.7.0.

## [1.6.0] — prior

See git tags `v1.6.0` and earlier for historical desk Jalali support releases before the Business Calendar Framework.

[1.8.0]: https://github.com/sfarbod/persian_calendar_erpnext/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/sfarbod/persian_calendar_erpnext/compare/v1.6.0...v1.7.0
