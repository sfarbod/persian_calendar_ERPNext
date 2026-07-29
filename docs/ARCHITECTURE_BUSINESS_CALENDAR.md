# Business Calendar Framework — Architecture Freeze

**Post Phase 3d Technical Reference** (Phases 0 → 3d-2 inclusive; Phase 3 Final hardening)

| Field | Value |
|-------|--------|
| Status | **Frozen** (official technical architecture reference) |
| Scope | Phases 0 → 3d-2 inclusive |
| App | `persian_calendar` |
| App version (at freeze) | `1.7.0` |
| Document path | `docs/ARCHITECTURE_BUSINESS_CALENDAR.md` |

### Validated platform (development bench at freeze)

| Component | Version | Notes |
|-----------|---------|--------|
| Frappe | **16.28.0** (`version-16`) | Installed on validation bench |
| ERPNext | **16.29.0** (`version-16`) | Source audit and framework tests |
| Python (runtime) | **3.14.2** | Bench `env` interpreter |
| Python (declared) | **≥ 3.10** | `pyproject.toml` `requires-python` |
| `persian_calendar` | **1.7.0** | Branch `develop` |

### Approved commits

| Commit | Summary |
|--------|---------|
| `f81810e` | Phases 0–2: framework, Company Business Calendar, Asset scheduling |
| `f8e4891` | Phase 2.5: framework hardening before wider ERP integration |
| `78b846b` | Phase 3a: Business Period Engine + Financial Statements lifecycle |
| `06ec2b0` | Phase 3b: Budget + Monthly Distribution |
| `b1556bd` | Phase 3c: Budget Variance + Trends |
| `b796e03` | Architecture Freeze document |
| `e23f6e1` | Business Calendar Developer Guide |
| `53d96a9` | Phase 3d-1: Sales + Purchase Analytics |
| `8c34252` | Phase 3d-2: Stock Analytics + manufacturing helper rebinds |

---

## 1. Project Overview

### Original problem

ERPNext stores and computes dates in the **Gregorian** calendar. Iranian companies often need **Jalali (Persian)** business periods: fiscal years that start on Farvardin 1, monthly depreciation on Jalali month ends, and budgets and variance reports aligned to Farvardin–Esfand rather than January–December.

Before the Business Calendar Framework, `persian_calendar` primarily offered **Display Calendar** support (Jalali datepickers and formatters in Desk). That improved presentation but did not change how ERPNext calculated periods, schedules, or report buckets.

### Asset depreciation as the forcing function

Asset Depreciation Schedule advances dates with Gregorian helpers (`add_months`, `get_last_day`, `is_last_day_of_the_month`). For a Jalali company, “last day of month” and “next period” must follow Jalali month length (including leap Esfand). Displaying a Gregorian schedule date as Jalali does not correct incorrect period boundaries. Asset work established that **business arithmetic** and **UI presentation** are separate concerns.

### Why Display Calendar was insufficient

| Display Calendar | Capability | Limitation |
|------------------|------------|------------|
| Per-user preference | Format dates in Desk; drive datepicker UI | Cannot change depreciation steps, fiscal period lists, Budget Distribution rows, or GL period bucketing |
| Presentation only | Localize labels | Must not own fiscal or business semantics |

Using user display preference for business logic would make accounting results **user-dependent**, which is unacceptable.

### Why Business Calendar was introduced

**Business Calendar** is a **per-company** policy selecting which calendar system owns period arithmetic for that company’s business processes, while **storage remains Gregorian/ISO** in the database and API.

### Three calendars and responsibilities

```text
┌─────────────────────┐
│  Storage Calendar   │  Always Gregorian (date / datetime / ISO in DB & API)
└──────────┬──────────┘
           │ never converted for persistence
┌──────────▼──────────┐
│  Display Calendar   │  Per User — UI only (datepicker, formatters)
└──────────┬──────────┘
           │ must not drive business math
┌──────────▼──────────┐
│  Business Calendar  │  Per Company — period semantics & scheduling
└─────────────────────┘
```

| Layer | Scope | Responsibility |
|-------|--------|----------------|
| **Storage Calendar** | System-wide | Persist Gregorian/ISO; Jalali is never the database source of truth |
| **Display Calendar** | User | Present dates; never resolve Business Calendar |
| **Business Calendar** | Company (`Company.business_calendar`) | Period lists, schedule steps, budget periods, report buckets |

Default Business Calendar is **Gregorian**, so existing sites keep stock ERPNext behavior until a company explicitly chooses Jalali.

---

## 2. Current Architecture

### Stack diagram

```text
                    ┌──────────────────────────────┐
                    │     ERPNext consumers        │
                    │ Assets · FS · Budget · MD    │
                    │ BVR · Trends (in-module)     │
                    └──────────────▲───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    override_doctype_class   apply_calendar_patches   thin adapters
              │              (+ asset disposal patch)   │
              │                    │                    │
              │         ┌──────────┴──────────┐         │
              │         │  Patch Applicator   │         │
              │         │ capture · replace   │         │
              │         │ identity rebind     │         │
              │         └──────────▲──────────┘         │
              │                    │                    │
              └──────────┬─────────┴─────────┬──────────┘
                         │                   │
              ┌──────────▼────────┐ ┌────────▼────────────┐
              │ Compatibility     │ │ period_labels       │
              │ adapters          │ │ (presentation only) │
              └──────────▲────────┘ └─────────────────────┘
                         │
              ┌──────────▼────────────────┐
              │   BusinessPeriodEngine    │  ← canonical period lists
              │   BusinessPeriod / Period │
              └──────────▲────────────────┘
                         │
              ┌──────────▼────────────────┐
              │      CalendarEngine       │  façade + company resolve
              └──────────▲────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
┌────────▼──────┐ ┌──────▼──────┐ ┌──────▼────────┐
│CalendarProvider│ │ Gregorian  │ │ Jalali        │
│ (ABC)          │ │ Provider   │ │ Provider      │
└────────────────┘ └────────────┘ └───────────────┘
```

### Layer ownership

| Component | Owns | Must not own |
|-----------|------|----------------|
| **CalendarProvider** | Pure date arithmetic | User prefs, DocTypes, patches, labels |
| **GregorianCalendarProvider** | Stock-compatible Gregorian math | Jalali semantics |
| **JalaliCalendarProvider** | Jalali month/year arithmetic → Gregorian storage dates | Display formatting |
| **CalendarEngine** | Provider selection (`for_company`, `gregorian`, `jalali`) | Report layout, ERPNext patches |
| **BusinessPeriodEngine** | Ordered period lists for a range + periodicity | Consumer-specific column shapes |
| **Period / BusinessPeriod** | Typed boundaries + stable keys | Locale strings as identity |
| **period_labels** | Human-readable labels | Lookup keys / allocation |
| **Adapters** | Map engine output ↔ ERPNext shapes; Gregorian delegation | Competing period engines |
| **Patch applicator** | Capture stock free functions; rebind importers | Business arithmetic |
| **ERPNext consumers** | Domain reports / DocTypes | Inline Jalali math |

### Canonical data flow

```text
CalendarEngine → BusinessPeriodEngine → Compatibility adapters → ERPNext consumers
```

Jalali date arithmetic must not be embedded inside Budget Variance, Trends, or similar consumer modules. Consumers call the engine or an adapter that does.

---

## 3. Implemented Modules

### Phase 0 — Calendar Framework Core

| | |
|--|--|
| **Purpose** | Calendar-system-agnostic arithmetic with Gregorian I/O only |
| **Files** | `persian_calendar/calendar/provider.py`, `providers/gregorian.py`, `providers/jalali.py`, `engine.py`, `types.py`, `resolve.py` |
| **Extension** | Library API only |
| **Business logic** | `LastDayPolicy` (`CLAMP_DAY`, `PRESERVE_MONTH_END`); stable `Period` keys |
| **Public APIs** | `CalendarEngine.for_company` / `for_calendar` / `gregorian` / `jalali`; provider methods |
| **Tests** | Provider suite |
| **Limitations** | No ERPNext consumers yet |

### Phase 1 — Company Business Calendar

| | |
|--|--|
| **Purpose** | Persist per-company Business Calendar; resolve without Display Calendar |
| **Files** | Custom Field / fixture `Company.business_calendar`; `resolve.py`; engine wiring |
| **Extension** | Field default **Gregorian** |
| **Business logic** | Empty/missing → Gregorian; Display preference ignored |
| **Public APIs** | `get_business_calendar_for_company`, `normalize_business_calendar`, `CalendarEngine.for_company` |
| **Tests** | `calendar/test_resolve.py` |
| **Limitations** | No automatic Jalali enablement; no historical migration |

### Phase 2 — Asset Depreciation

| | |
|--|--|
| **Purpose** | Jalali-correct depreciation schedule stepping for Jalali companies |
| **Files** | `integrations/assets.py`; `docs/asset_business_calendar_integration.md` |
| **Extension** | `override_doctype_class` for Asset Depreciation Schedule, Asset, Asset Shift Allocation; narrow `before_request` patch via `apply_asset_disposal_patch` for `disposal_was_made_on_original_schedule_date` |
| **Business logic** | Provider-based `add_months` / month-end; booked JE rows preserved by stock `clear()` |
| **Public APIs** | `PersianCalendarAssetDepreciationSchedule`, `PersianCalendarAsset`, `PersianCalendarAssetShiftAllocation` |
| **Tests** | `integrations/test_assets.py` (10) |
| **Limitations** | No silent regenerate on migrate |

### Phase 2.5 — Framework Hardening

| | |
|--|--|
| **Purpose** | Stabilize types, fiscal-year interaction, and Asset/FY edge cases before wider ERP adapters (`f8e4891`) |
| **Files** | Hardening across types, engine/resolve, asset integration |
| **Extension** | Same Asset mechanisms; clearer contracts for later phases |
| **Business logic** | Stronger `Period` / calendar-system consistency |
| **Public APIs** | Refined engine/types contracts |
| **Tests** | Expanded provider / asset / resolve coverage |
| **Limitations** | Still no FS / Budget / Trends adapters |

### Phase 3a — Business Period Engine + Financial Statements

| | |
|--|--|
| **Purpose** | Canonical period-list generator; FS `get_period_list` adapter + central patch lifecycle |
| **Files** | `period_engine.py`, `period_labels.py`, `integrations/financial_statements.py`, `patches.py`, `docs/business_period_engine.md` |
| **Extension** | `apply_calendar_patches()` rebinds `get_period_list` + known FS consumers |
| **Business logic** | Monthly / Quarterly / Half-Yearly / Yearly via engine; Gregorian → captured stock |
| **Public APIs** | `BusinessPeriodEngine.generate`; adapter `get_period_list`; `format_period_label` |
| **Tests** | `test_period_engine.py` (30), `test_patches.py` (14) |
| **Limitations** | Console / `bench execute` must call applicator explicitly |

### Phase 3b — Budget + Monthly Distribution

| | |
|--|--|
| **Purpose** | Company Business Calendar for Budget period generation; calendar-neutral Monthly Distribution slots |
| **Files** | `integrations/budget.py`, `monthly_distribution.py`, `docs/budget_business_calendar.md` |
| **Extension** | `override_doctype_class` for Budget and Monthly Distribution; MD free functions via applicator |
| **Business logic** | Budget stores Gregorian Budget Distribution child rows from engine periods; MD uses `idx` 1–12 (not English names for Jalali) |
| **Public APIs** | `PersianCalendarBudget.get_budget_periods`; `resolve_distribution_percentage`; patched `get_periodwise_distribution_data` / `get_percentage` |
| **Tests** | `test_budget.py` (10), `test_monthly_distribution.py` (14) |
| **Limitations** | Submitted Budgets not rewritten; MD remains a company-neutral template |

### Phase 3c — Budget Variance + Trends

| | |
|--|--|
| **Purpose** | Shared Trends period ranges + Budget Variance alignment to Business Calendar and stored Budget Distribution rows |
| **Files** | `integrations/trends.py`, `budget_variance.py`, `patches.py` extensions, `docs/budget_variance_trends.md` |
| **Extension** | Applicator patches `trends.get_period_date_ranges` and Budget Variance `execute` |
| **Business logic** | Jalali periods from engine; Budget Distribution match by dates; GL by inclusive `posting_date`; cumulative in business order |
| **Public APIs** | Adapter drop-ins matching stock signatures (Trends accepts optional `company=`) |
| **Tests** | `test_trends.py` (19), `test_budget_variance.py` (18) |
| **Limitations** | Trends report column labels may still use Gregorian `%b` (presentation debt); Analytics out of scope |

**Why Trends patch alone is insufficient for Budget Variance:** even with Jalali period ranges, stock Budget Variance still allocates amounts by English month names (`strftime("%B")` / MySQL `MONTHNAME`). Phase 3c therefore also replaces report `execute` for Jalali companies.

---

## 4. Patch Architecture

### Why runtime patching exists

ERPNext exposes module-level free functions that consumers import by name binding:

```python
from erpnext.controllers.trends import get_period_date_ranges
from erpnext.accounts.report.financial_statements import get_period_list
```

Replacing only the source module attribute does not update modules that already imported the function object. DocType instance methods can use `override_doctype_class`; free functions cannot. ERPNext does not provide first-class extension points for these report helpers, so the app uses a **process-local, identity-based rebinding** applicator.

### `apply_calendar_patches()`

Single central entry in `persian_calendar.calendar.patches`. Idempotent when successfully applied; retries after `SOURCE_UNAVAILABLE`, `PARTIAL_REBIND`, or `FAILED`.

**Targets registered in the applicator (post-Phase 3d-2):**

| Target | Source module | Adapter |
|--------|---------------|---------|
| `get_period_list` | `erpnext.accounts.report.financial_statements` | `integrations.financial_statements.get_period_list` |
| `get_periodwise_distribution_data` / `get_percentage` | `erpnext.accounts.doctype.monthly_distribution.monthly_distribution` | `integrations.monthly_distribution` |
| `get_period_date_ranges` | `erpnext.controllers.trends` | `integrations.trends.get_period_date_ranges` |
| `execute` | `erpnext.accounts.report.budget_variance_report.budget_variance_report` | `integrations.budget_variance.execute` |
| `Analytics` methods | `erpnext.selling.report.sales_analytics.sales_analytics` | `integrations.sales_analytics` (covers Purchase Analytics) |
| `get_period_date_ranges` / `get_period` / `get_period_columns` | `erpnext.stock.report.stock_analytics.stock_analytics` | `integrations.stock_analytics` |

Stock Analytics consumers rebound by identity: Production Analytics, Work Order Summary, Job Card Summary (`STOCK_ANALYTICS_PERIOD_CONSUMERS`). `round_down_to_nearest_frequency` is captured but **not** replaced (module-global safety for Gregorian delegation).

**Separate from the central applicator (Phase 2):**

| Target | Hook | Function |
|--------|------|----------|
| `disposal_was_made_on_original_schedule_date` | `before_request` → `apply_asset_disposal_patch` | Narrow module attribute replace on `erpnext.assets.doctype.asset.depreciation` |

### `PatchStatus`

| Status | Meaning |
|--------|---------|
| `not_attempted` | Fresh process state |
| `applied` | Capture + replace + known consumers rebound |
| `source_unavailable` | ERPNext module not importable yet; retry later |
| `partial_rebind` | Known loaded consumer still holds stock function |
| `failed` | Unsafe state (e.g. adapter present but original never captured) |

### Original capture and Gregorian delegation

- Capture the real stock function exactly once.
- Never capture the adapter as “original”.
- Gregorian Business Calendar path calls the captured original (no duplicated stock math, no recursion).

### Rebinding

- Known-consumer registries (`GET_PERIOD_LIST_CONSUMERS`, `MD_PERIODWISE_CONSUMERS`, `TRENDS_PERIOD_RANGES_CONSUMERS`, `STOCK_ANALYTICS_PERIOD_CONSUMERS`).
- Replace attribute only when `current is original` (object identity).
- Restricted `erpnext.*` identity scan for unlisted importers of the same attribute (FS / MD / Trends). Stock Analytics rebinds **only** the known manufacturing consumers (no broad name scan).
- Unrelated same-named functions (for example Trends vs Stock `get_period_date_ranges`) are untouched.

### Hook lifecycle

| Hook | Registered path |
|------|-----------------|
| `before_request` | `persian_calendar.calendar.patches.before_request_calendar_bootstrap` (and separately `integrations.assets.apply_asset_disposal_patch`) |
| `before_job` | `persian_calendar.calendar.patches.before_job_calendar_bootstrap` |
| `before_tests` | `persian_calendar.calendar.patches.before_tests_calendar_bootstrap` |

### Console limitation

There is no supported Frappe hook for `bench execute` / console. Call `apply_calendar_patches()` explicitly in those contexts.

### Design constraints

- One applicator for calendar free-function patches — no second `PatchStatus` system.
- Process-local only.
- No global `frappe.utils` monkey-patches (`formatdate`, `add_months`, `strftime`, and similar).

---

## 5. Compatibility Guarantees

### Gregorian companies

- Prefer **delegation to captured stock ERPNext functions**.
- Parity target: identical period lists and report behavior to stock for supported periodicities, within the validated ERPNext version.
- Default / empty `business_calendar` → Gregorian → no intentional behavioral change for typical upgrades of this app alone.

### Jalali companies

- Period boundaries from **BusinessPeriodEngine** + Jalali provider.
- All returned and stored dates remain **Gregorian storage dates**.
- Display Calendar must not change calculations.
- Labels are presentation metadata only.

### Backward compatibility

- No mandatory Jalali enablement on install/migrate.
- Existing companies remain Gregorian unless configured.
- This freeze document does not bump the app version.

### Migration policy

- No automatic rewrite of historical schedules, Budget Distribution rows, or GL.
- Changing Company Business Calendar does **not** migrate historical submitted documents.

### Historical / submitted document policy

| Document state | Policy |
|----------------|--------|
| **Submitted** | Stored boundaries authoritative; not rewritten by calendar change |
| **Draft** | May regenerate under current Business Calendar via stock save flows (Budget, Phase 3b) |
| **Amended** | Follow stock amendment; regenerate/validate as stock requires |
| **Booked depreciation** | Journal Entry–linked rows preserved by stock `clear()` |

---

## Compatibility Matrix

### Platform compatibility

Statuses used below: **Validated**, **Targeted**, **Requires re-audit**, **Not validated**, **Unsupported**.

| Component | Version | Status | Notes |
|-----------|---------|--------|-------|
| Frappe | 16.28.0 | Validated | Installed on validation bench with framework suites |
| Frappe | 16.x later | Requires re-audit | Hooks and import timing may change |
| Frappe | 15.x | Not validated | Framework designed against Frappe v16 |
| ERPNext | 16.29.0 | Validated | Source audit and Business Calendar framework tests |
| ERPNext | 16.x later | Requires re-audit | Free-function signatures and report shapes may change |
| ERPNext | 15.x | Not validated | Architecture implemented for ERPNext v16 |
| Python | ≥ 3.10 (declared) | Targeted | `pyproject.toml` |
| Python | 3.14.2 (runtime) | Validated | Bench environment used for freeze verification |
| `persian_calendar` | 1.7.0 | Validated | App version at Phase 3c tip `b1556bd` |
| MariaDB | 10.11.x (bench host) | Not validated as framework dependency | Present in environment; framework does not claim DB-version-specific behavior |
| Node.js | (Desk build toolchain) | Unsupported for this framework | Business Calendar arithmetic is server-side; Node is irrelevant to period math |

Do not claim compatibility with versions that were not tested.

### Feature compatibility

| Feature | Status | Notes |
|---------|--------|-------|
| Company Business Calendar | Implemented | `Company.business_calendar`; default Gregorian |
| Fiscal Year (Gregorian storage bounds) | Implemented (consumed) | FY DocType unchanged; engine slices by Business Calendar |
| Assets / Depreciation | Implemented | DocType overrides + narrow disposal patch |
| Financial Statements `get_period_list` | Implemented | Central applicator |
| Budget period generation | Implemented | `PersianCalendarBudget` |
| Monthly Distribution | Implemented | Calendar-neutral `idx` slots + free-function patches |
| Budget Variance | Implemented | `execute` adapter for Jalali; Gregorian delegates |
| Trends `get_period_date_ranges` | Implemented | Period boundaries; see presentation limitation |
| Trends report column labels | Presentation limitation | May still use Gregorian `%b` / `get_mon` |
| Sales Analytics | Implemented (Phase 3d-1) | Shared `Analytics` class methods; Weekly → stock |
| Purchase Analytics | Implemented (Phase 3d-1) | Same class as Sales Analytics — no second patch |
| Stock Analytics | Implemented (Phase 3d-2) | Free functions via `integrations/stock_analytics.py`; Weekly → stock; carry-forward preserved |
| Production / WO / Job Card Summary | Implemented (Phase 3d-2) | Identity-rebind of Stock Analytics period helpers only — not core MRP |
| CRM Display Calendar (forms/lists/report filters) | Verified global coverage (Phase 5A-2) | No CRM display adapters; see `docs/CRM_DISPLAY_CALENDAR.md` |
| CRM Pipeline / Issue Analytics (Business Calendar) | Not started | Deferred (5A-3+) |
| Forecast | Not started | Deferred (Phase 3e) |
| Manufacturing (MRP / MPS) | Not started | Deferred (Phase 4) |
| HRMS | Not started | Deferred (Phase 5) |
| Presentation Layer (picker / label consistency) | Partially implemented | Display Calendar exists separately; business-period label consistency deferred (Phase 6) |
| Subscription / Auto Repeat / Maintenance | Not started | Out of freeze scope |

### Upgrade policy

Every ERPNext (and relevant Frappe) upgrade must trigger a re-audit of:

- free-function signatures for all patched targets
- direct-import consumers
- report return shapes and columns
- DocType override compatibility
- Budget Variance month-key assumptions in stock code
- hook lifecycle behavior (`before_request`, `before_job`, `before_tests`)

**Passing unit tests alone does not prove compatibility after an ERPNext upgrade.** Re-audit source and registries first, then re-run the framework suites and representative Script Reports.

---

## 6. Period Engine

### Types

- **`Period`** (`calendar/types.py`): grain, bounds, stable key, calendar-system metadata.
- **`BusinessPeriod`**: `from_date`, `to_date`, `key`, `label` (empty at generation), `periodicity`, `calendar_system`, `year`, `period_number`.
- **`BusinessPeriodEngine.generate(start, end, periodicity, *, company=None, provider=None)`** — canonical list generator.

### Periodicity

| Periodicity | Gregorian intent | Jalali intent |
|-------------|------------------|---------------|
| Monthly | Calendar months in range / FY | Farvardin–Esfand |
| Quarterly | 3-month blocks | Q1 Far–Khordad … Q4 Dey–Esfand |
| Half-Yearly | 6-month blocks | H1 Far–Shahrivar; H2 Mehr–Esfand |
| Yearly | Full range / FY | Full Jalali business / FY range |

### Leap years

Jalali leap Esfand (30 days) is handled by `JalaliCalendarProvider`; non-leap Esfand is 29 days. The engine clamps period ends to the requested range end.

### Fiscal year interaction

- Fiscal Year DocType stores Gregorian `year_start_date` / `year_end_date`.
- The engine consumes those Gregorian bounds and slices with the company provider.
- Non-January Gregorian fiscal years remain correct for Gregorian companies via stock delegation where adapters do so.

### Partial ranges

The engine supports ranges not aligned to full years; periods clamp to `end_date`. Further partial-period needs should extend the engine only with a backward-compatible API—not a second engine.

### Labels

`format_period_label` (English / Persian) — never used as allocation or dictionary keys.

---

## Periodicity Mismatch Policy (Budget Variance)

Stock ERPNext Budget Variance (v16.29) already implements a **flatten-then-regroup** pattern for Gregorian companies:

1. Each Budget Distribution row is split equally across Gregorian months in `[start_date, end_date]` via `get_months_in_range` / `add_months`.
2. Amounts are keyed by English month name + fiscal year.
3. Report periods re-aggregate those month buckets.

For **Jalali** companies, `persian_calendar.calendar.integrations.budget_variance.budget_amount_for_period` implements a **compatibility policy** that mirrors that pattern using **business months** from `BusinessPeriodEngine` instead of Gregorian calendar months and English names:

| Stored frequency vs report | Behavior |
|----------------------------|----------|
| Distribution fully inside report period | Full amount |
| Finer stored periods → coarser report | Aggregate by date inclusion |
| Coarser stored → finer report (overlap) | Equal split across business months spanning the distribution, then take months overlapping the report period |

**Nature of the policy:** combination of (a) inherited stock ERPNext flatten-then-regroup intent and (b) an app-defined Jalali adaptation that preserves the equal-split assumption while switching the month system.

**Limitations:**

- Equal split is an **allocation assumption**. It does not model operational seasonality, custom percentage curves, or non-uniform spend.
- Stock Gregorian path still uses English month names; Jalali path must not.
- Duplicate or overlapping stored Budget Distribution rows are rejected (validation), not silently merged.

Implementation reference: `budget_amount_for_period` in `persian_calendar/calendar/integrations/budget_variance.py`.

---

## 7. Financial Modules

### Assets

| | |
|--|--|
| **Mechanism** | `override_doctype_class` + `apply_asset_disposal_patch` |
| **Engine / provider** | `CalendarEngine` / provider arithmetic |
| **Gregorian** | Stock-compatible stepping |
| **Jalali** | Jalali month/year steps; storage Gregorian |

### Financial Statements

| | |
|--|--|
| **Mechanism** | Patch `get_period_list` + consumer rebind |
| **Engine** | `BusinessPeriodEngine` for Jalali |
| **Gregorian** | Captured stock `get_period_list` |
| **Jalali** | Engine periods mapped to FS period dict shape |

### Budget

| | |
|--|--|
| **Mechanism** | `override_doctype_class` → `PersianCalendarBudget` |
| **Engine** | `get_budget_periods()` → engine for Jalali; `super()` for Gregorian |
| **Storage** | Budget Distribution child: Gregorian `start_date` / `end_date` |

### Monthly Distribution

| | |
|--|--|
| **Mechanism** | DocType override + patched free functions |
| **Mapping** | Calendar-neutral `idx` 1–12; Jalali matches by position |
| **Gregorian** | Stock name matching via captured originals |

### Trends

| | |
|--|--|
| **Mechanism** | Patch `get_period_date_ranges` |
| **Engine** | Jalali → engine; return `list[[start, end], ...]` |
| **Gregorian** | Captured stock |
| **Company** | Not in stock signature; resolve via `company=` / form_dict / Fiscal Year Company links / defaults |

### Budget Variance

| | |
|--|--|
| **Mechanism** | Patch `execute` |
| **Engine** | Jalali periods + `format_period_label`; Budget Distribution by date; GL by `posting_date` |
| **Gregorian** | Captured stock `execute` |

---

## Presentation Debt

- Calculations for Jalali Business Calendar companies already follow business-period boundaries from `BusinessPeriodEngine`.
- Some Trends (and related) report column headers may still use Gregorian abbreviations via stock `get_mon` / `%b` / `formatdate`, even when date ranges are Jalali-correct.
- That is a **presentation limitation**, not a period-boundary error.
- Labels must still not be used as business keys.
- Final presentation consistency is deferred to the Presentation Layer phase (Phase 6). Budget Variance Jalali path already uses `period_labels` for its own columns.

---

## 8. Data Ownership

| Concern | Owner | Notes |
|---------|--------|------|
| **Business Calendar** | Company (`business_calendar`) | Not user Display Calendar |
| **Fiscal Year** | Fiscal Year DocType (Gregorian bounds) | Shared; mixed Business Calendars across FY-linked companies rejected in Trends resolve |
| **Budget Distribution** | Budget document (child rows) | Authoritative for submitted budgets |
| **Monthly Distribution** | Global template (no company) | Positions 1–12; consumer supplies calendar context |
| **Stored period boundaries** | Creating document / save path | Reports must match stored dates for history |
| **Report period generation** | `BusinessPeriodEngine` (via adapters) | Not labels; not Display Calendar |

### Why labels are never business keys

Labels translate, change with locale, and collide across calendars (for example English “March” versus Farvardin overlapping Gregorian March). Matching and aggregation use **Gregorian boundary dates** and/or **stable keys** (`j01_1405`, `period_number` ↔ `idx`).

---

## 9. Validation Rules

| Rule | Where | Behavior |
|------|--------|----------|
| Mixed Business Calendars on one Fiscal Year’s companies | Trends `_resolve_company` | Throw; require a single company or aligned Business Calendars |
| Duplicate Budget Distribution periods | BVR `validate_distribution_integrity` | Throw with budget name and dates |
| Overlapping Budget Distribution periods | BVR integrity | Throw |
| Missing report period | BVR allocation | Amount `0` — not reassigned to the wrong period |
| Stale / non–Jalali-month-start boundaries under Jalali BC | `validate_stale_budget_calendar` helper | **Available but not hooked** into Budget validate/save; tests cover the helper; warn-only semantics if wired later |
| Periodicity mismatch | BVR `budget_amount_for_period` | See Periodicity Mismatch Policy |
| Company resolution | Trends / adapters | Explicit company → form → FY links → defaults; never Display Calendar |
| Invalid Business Calendar name | Engine / resolver | Error or Gregorian normalize per `normalize_business_calendar` |
| Accounting dimension filters | Stock BVR validate | Unchanged |
| Consolidated FS mixed calendars | FS adapter helpers | Helper exists; not all stock consolidated call paths invoke it automatically |

---

## 10. Test Coverage

Verified on site `development.localhost` at Phase 3 Final hardening:

| Suite | Module | Count |
|-------|--------|------:|
| Period Engine (+ labels) | `persian_calendar.calendar.test_period_engine` | 30 |
| Providers | `persian_calendar.calendar.test_providers` | 41 |
| Resolver | `persian_calendar.calendar.test_resolve` | 6 |
| Assets | `persian_calendar.calendar.integrations.test_assets` | 10 |
| Patches / lifecycle | `persian_calendar.calendar.test_patches` | 14 |
| Budget | `persian_calendar.calendar.integrations.test_budget` | 10 |
| Monthly Distribution | `persian_calendar.calendar.integrations.test_monthly_distribution` | 14 |
| Budget Variance | `persian_calendar.calendar.integrations.test_budget_variance` | 18 |
| Trends | `persian_calendar.calendar.integrations.test_trends` | 19 |
| Sales / Purchase Analytics | `persian_calendar.calendar.integrations.test_sales_analytics` | 19 |
| Stock Analytics (+ manufacturing rebinds) | `persian_calendar.calendar.integrations.test_stock_analytics` | 30 |
| **Framework total** | | **211** |

Coverage themes include Gregorian parity and delegation, Jalali boundaries and leap Esfand, patch identity rebind, Display Calendar independence, Budget Distribution matching, cumulative order, mixed-calendar rejection, Sales/Stock stable keys and carry-forward, and absence of global `formatdate` replacement.

### Upstream and unrelated tests

| Category | Status |
|----------|--------|
| Business Calendar Framework suites (211) | All passed at Phase 3 Final verification |
| Installed ERPNext Budget Variance / Trends / Stock Analytics modules | Re-run on upgrade; site fixture noise may block discovery |
| `persian_calendar.utils.test_datetime_coercion` | **2 pre-existing failures** (8 tests run) around `toshamshi` display expectations |

All Business Calendar Framework suites passed. Two pre-existing failures remain in datetime display coercion tests and are not part of the Business Calendar arithmetic framework.

---

## 11. Known Limitations

| Area | Limitation |
|------|------------|
| Console bootstrap | Must call `apply_calendar_patches()` manually |
| Dual `get_period_list` wrappers | Display `formatters.patch_get_period_list` may run before the BC adapter on `before_request`; Gregorian BC boundaries still delegate, but **labels** may follow Display Calendar until Presentation Layer unifies this |
| Sales / Purchase Analytics | Implemented (3d-1); see module note |
| Stock Analytics + manufacturing helper rebinds | Implemented (3d-2); core MRP/MPS not started |
| Forecast | Not redesigned |
| MRP / MPS | Not started |
| HRMS | Not started |
| Subscription / Auto Repeat / Maintenance | Not started |
| CRM Display Calendar | Phase 5A-2 verified (global desk) |
| CRM / Support analytics (BC) | Not started |
| Trends presentation labels | Date ranges may be Jalali-aware while headers still use Gregorian `%b` |
| Date Picker / Desk UI | Display layer; outside Phases 0–3d business arithmetic |
| Historical migration | No auto-convert of submitted Budget Distribution / schedules when Business Calendar changes |
| Budget Variance Script Report | No `override_doctype_class`; Jalali requires `execute` patch |
| Asset disposal patch | Separate from central applicator (intentional Phase 2 narrow patch) |
| Stale budget calendar helper | Not wired to DocType validate (helper + tests only) |
| Sales/Stock quarter snap | Small jdatetime first-day snap before engine generate (debt; not a second period engine) |

---

## 12. Extension Guide

### Mandatory rules for future work

1. **BusinessPeriodEngine is canonical** for business period lists.
2. **Never duplicate Jalali arithmetic** inside consumers.
3. Prefer **`override_doctype_class`** for DocType instance methods.
4. Use **`apply_calendar_patches()`** only for unavoidable free-function interception; extend the same applicator.
5. **Never** globally patch `frappe.utils` (`formatdate`, `add_months`, `strftime`, translations).
6. **Never** use Display Calendar / user locale for business boundaries.
7. **Never** use translated or English month labels as data keys.
8. **Gregorian companies → delegate** to captured stock functions where possible.
9. Capture originals **once**; verify no recursion; identity-rebind known importers.
10. Reject **mixed Business Calendars** explicitly; do not silently pick the first company.
11. Preserve **submitted** stored boundaries; do not silent-migrate history.
12. Keep adapter return shapes compatible with stock callers.

### Suggested adapter checklist

- Audit the installed ERPNext version (do not rely only on older notes).
- Inventory direct imports of the free function.
- Decide: override vs patch vs both.
- Prove Gregorian parity tests before Jalali claims.
- Document company resolution and historical policy.
- Add lifecycle tests if patching.

---

## 13. Roadmap

### Phase 3d — Analytics

| | |
|--|--|
| **Purpose** | Sales / Purchase / Stock Analytics period engines on Business Calendar |
| **Phase 3d-1 (done)** | Sales + Purchase Analytics via `integrations/sales_analytics.py`; Weekly delegates to stock; stable `BusinessPeriod.key` buckets |
| **Phase 3d-2 (done)** | Stock Analytics free functions + Production / WO / Job Card identity rebinds; carry-forward via stable `get_period` keys |
| **Phase 3 Final (done)** | Hardening / validation / release readiness — no new modules |
| **Dependencies** | Period engine + applicator patterns from Phases 3a–3c |
| **Mechanism** | Dedicated adapters; do not confuse with Trends `get_period_date_ranges` (different functions / contracts) |
| **Risks** | Multiple same-named helpers; label-as-key charts on WO/JC; SLE balance carry |

### Phase 3e — Forecast

| | |
|--|--|
| **Purpose** | Forecasting period alignment without redesigning forecast models beyond compatibility |
| **Dependencies** | Period engine; possibly FS / Trends patterns |
| **Expected mechanism** | Prefer engine consumption; patch only if free functions force it |
| **Risks** | Forecast modules may already touch `get_period_list` in some paths |

### Phase 4 — Manufacturing

| | |
|--|--|
| **Purpose** | MRP / MPS and manufacturing reports that bucket by calendar periods |
| **Dependencies** | Stable applicator; Analytics lessons |
| **Expected mechanism** | Audit first; avoid broad patches |
| **Risks** | Planning horizons may differ from accounting fiscal year; performance |

### Phase 5 — HRMS

| | |
|--|--|
| **Purpose** | Leave, payroll, and attendance period semantics where company Business Calendar applies |
| **Dependencies** | Clear product ownership: HR may have separate leave-year concepts |
| **Expected mechanism** | Prefer DocType overrides; do not mix employment calendars with accounting Business Calendar without explicit rules |
| **Risks** | Domain ambiguity; multi-company employees |

### Phase 6 — Presentation Layer

| | |
|--|--|
| **Purpose** | Date picker, Desk labels, Trends column labels, export presentation consistency |
| **Dependencies** | Business layer already correct (storage + periods) |
| **Expected mechanism** | Display Calendar + `period_labels`; still no label-as-key |
| **Risks** | Confusing Display Calendar with Business Calendar; over-patching formatters |

---

## ERPNext Upgrade Checklist

1. Pin and record old and new Frappe / ERPNext versions.
2. Audit all patched source functions (FS, MD, Trends, Budget Variance, Asset disposal helper).
3. Compare function signatures against adapters.
4. Re-run direct-import inventory (AST or equivalent).
5. Verify known-consumer registries still match reality.
6. Confirm original-function capture (original is never the adapter).
7. Run Gregorian parity tests.
8. Run Jalali boundary tests.
9. Run patch lifecycle tests.
10. Verify Script Report output shapes and columns (especially Budget Variance).
11. Verify DocType override paths (Asset, Budget, Monthly Distribution).
12. Review upstream changes to Budget, Budget Variance, and Trends.
13. Test request, worker, and test bootstrap contexts.
14. Test console / `bench execute` with explicit `apply_calendar_patches()`.
15. Update this document’s Compatibility Matrix.

Production upgrades must not proceed if patch status is `partial_rebind`, `failed`, or `source_unavailable` in a context that requires the patch.

---

## 14. Architectural Risks

| Risk | Severity | Mitigation / residual |
|------|----------|------------------------|
| ERPNext upgrades change free-function signatures or Budget Variance month-name logic | High | Version-pin audits; consumer inventory tests; Gregorian delegation |
| Monkey patches | High | Single applicator; no utils globals; lifecycle tests |
| Import rebinding incomplete if new importers appear | Medium | Known registries + identity scan + inventory tests |
| Future Frappe hooks may obsolete `before_request` bootstrap | Low–Medium | Thin wrappers; easy to retarget |
| Performance (engine + rebind scans) | Low today | Rebind at import/apply time; watch Analytics scale |
| Testing without full ERPNext Budget Variance GL fixtures | Medium | Unit tests cover matching and boundaries; integration gaps remain |
| Dual Gregorian paths (delegate vs reimplement) | Medium | Prefer delegate; document when reimplement is forced (Budget Variance Jalali) |
| Console footgun | Medium | Documented; optional future CLI helper |
| Trends label presentation debt | Low–Medium | Phase 6 / Analytics presentation work |

---

## Architecture Decision Records

### ADR-001 — Gregorian Storage Calendar

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Frappe, ERPNext, MariaDB schemas, and public APIs treat date fields as Gregorian/ISO. |
| **Decision** | All persisted dates remain Gregorian/ISO. |
| **Rationale** | Changing storage representation would break the platform and every integration. |
| **Consequences** | Jalali values are converted at system boundaries and never become the database source of truth. |
| **Alternatives** | Native Jalali DB columns — rejected. |

### ADR-002 — Display Calendar Is Presentation-Only

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Users may prefer Jalali UI while the company policy differs, or vice versa. |
| **Decision** | User Display Calendar must never drive business calculations. |
| **Rationale** | Accounting results must not vary by user preference. |
| **Consequences** | Resolvers and adapters ignore Display Calendar; UI remains free to format dates. |
| **Alternatives** | Derive business periods from user locale — rejected. |

### ADR-003 — Business Calendar Is Company-Owned

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Period semantics (fiscal months, depreciation steps) are organizational policy. |
| **Decision** | Business Calendar belongs to Company (`Company.business_calendar`). |
| **Rationale** | Matches how companies operate and how ERPNext scopes accounting entities. |
| **Consequences** | Multi-company reports must resolve calendar per company or reject mixed calendars. |
| **Alternatives** | Global site setting only — too coarse; user setting — unsafe. |

### ADR-004 — BusinessPeriodEngine Is Canonical

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Multiple ERPNext modules need Monthly / Quarterly / Half-Yearly / Yearly lists. |
| **Decision** | All supported business-period generation must use `BusinessPeriodEngine`. |
| **Rationale** | Avoid duplicated Jalali arithmetic and divergent report behavior. |
| **Consequences** | Adapters map engine output to stock shapes; consumers must not invent period math. |
| **Alternatives** | Per-module Jalali helpers — rejected. |

### ADR-005 — Gregorian Paths Delegate to ERPNext

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Most companies remain Gregorian; stock behavior is the compatibility baseline. |
| **Decision** | Where possible, Gregorian companies call the captured original ERPNext implementation. |
| **Rationale** | Maintain parity and reduce upgrade drift. |
| **Consequences** | Adapters must capture originals once; tests assert delegation. |
| **Alternatives** | Reimplement all Gregorian period math — higher drift risk. |

### ADR-006 — Labels Are Never Business Keys

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Stock Budget Variance keys English month names; labels vary by locale and calendar. |
| **Decision** | Translated month names and labels must not be used for matching, allocation, or identity. |
| **Rationale** | Labels are mutable, localized, and calendar-dependent. |
| **Consequences** | Matching uses Gregorian dates and stable keys; Jalali Budget Variance avoids month-name maps. |
| **Alternatives** | Continue English month-name keys for Jalali — incorrect. |

### ADR-007 — Prefer Supported DocType Overrides

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Frappe provides `override_doctype_class` for DocType Python classes. |
| **Decision** | Use `override_doctype_class` before runtime patching. |
| **Rationale** | It is the supported extension mechanism for DocType methods. |
| **Consequences** | Budget, Monthly Distribution, and Asset controllers use overrides; free functions still need patches. |
| **Alternatives** | Patch every method via hooks — less maintainable. |

### ADR-008 — Runtime Patching Is Centralized

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Free-function consumers require capture and identity rebind. |
| **Decision** | All unavoidable calendar free-function patches must use `apply_calendar_patches()`. |
| **Rationale** | Avoid competing monkey-patch lifecycles and inconsistent state. |
| **Consequences** | One `PatchStatus`; shared bootstrap hooks; Phase 2 asset disposal remains a documented narrow exception. |
| **Alternatives** | Ad-hoc per-module patches — rejected for free functions covered by the applicator. |

### ADR-009 — No Global `frappe.utils` Patching

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Temptation to replace `add_months` / `formatdate` globally for Jalali. |
| **Decision** | Never globally patch functions such as `add_months`, `formatdate`, or `strftime`. |
| **Rationale** | Global changes could corrupt unrelated ERPNext workflows. |
| **Consequences** | Calendar math stays in providers/engine; presentation stays local. |
| **Alternatives** | Global utils patch — rejected. |

### ADR-010 — Submitted Historical Boundaries Are Authoritative

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Company Business Calendar may change after budgets or schedules were submitted. |
| **Decision** | Submitted schedules and Budget Distribution rows are not automatically reinterpreted after Business Calendar changes. |
| **Rationale** | Historical accounting documents must remain stable and auditable. |
| **Consequences** | Reports match stored dates; amend/regenerate is explicit; optional stale warnings only. |
| **Alternatives** | Silent migration of historical rows — rejected. |

### ADR-011 — Mixed Business Calendars Must Be Explicit

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Fiscal Years and reports can span multiple companies. |
| **Decision** | Multi-company operations with incompatible Business Calendars must be rejected unless a defined common-calendar contract exists. |
| **Rationale** | Silently selecting one company’s calendar produces incorrect periods. |
| **Consequences** | Trends resolve throws on mixed FY company calendars; FS consolidated helpers validate where applicable. |
| **Alternatives** | Use first company — rejected. |

### ADR-012 — Patch Rebinding Uses Object Identity

| | |
|--|--|
| **Status** | Accepted |
| **Context** | Many modules define similarly named helpers. |
| **Decision** | Already imported consumers are rebound only when they hold the exact captured original function object. |
| **Rationale** | Avoid modifying unrelated functions with identical names. |
| **Consequences** | Stock Analytics’ own `get_period_date_ranges` is not rebound by the Trends patch. |
| **Alternatives** | Rebind by attribute name alone — unsafe. |

---

## 15. Final Architecture Review

### Strengths

- Clear three-calendar separation; Display Calendar cannot corrupt accounting math.
- Single period engine prevents divergent Jalali implementations across modules.
- Gregorian delegation preserves stock parity for the default majority.
- Pragmatic extension mix: DocType overrides where possible; one patch applicator where ERPNext forces free functions.
- Lifecycle discipline: capture-once, identity rebind, `PatchStatus`, hook coverage, inventory tests.
- Historical safety: submitted documents and stored Budget Distribution rows treated as authoritative.

### Weaknesses

- Runtime patching is brittle under ERPNext refactors.
- Budget Variance Jalali path reimplements substantial report assembly because stock keys month names—higher maintenance than Trends-only patching.
- Company resolution for Trends without a `company` argument relies on form_dict / Fiscal Year links / defaults—correct but subtle for multi-company Fiscal Years.
- Presentation still lags calculation for some Trends labels.
- Console bootstrap requires explicit applicator calls.

### Technical debt

- Dual knowledge of stock Budget Variance (month-name map) versus Jalali date-range path.
- Asset disposal patch lives outside `apply_calendar_patches` (narrow Phase 2 exception).
- Analytics same-named `get_period_date_ranges` functions will tempt incorrect patching if registries are not kept strict.
- Display-layer `formatters.patch_get_period_list` may wrap FS `get_period_list` before the BC adapter (label presentation debt).
- `validate_stale_budget_calendar` / consolidated FS mixed-calendar helpers are not fully wired to stock save/report paths.
- Sales/Stock `_snap_jalali_start` still uses small jdatetime quarter/half first-day snaps.
- `test_datetime_coercion` failures remain noise adjacent to the framework.

### Suggested future improvements (non-binding)

1. Unify FS `get_period_list` with Display formatters so Gregorian BC never inherits Display label wrapping (Presentation / Phase 6 adjacent).
2. Reduce Budget Variance debt if upstream ERPNext ever keys by dates instead of month names.
3. Optional explicit `company` plumbing into Trends callers where ERPNext allows without breaking stock.
4. Presentation Phase 6 for Trends labels without touching business keys.
5. Keep rejecting proposals to patch `frappe.utils` or to drive periods from user Display Calendar.

### Objective verdict

The framework is **fit for frozen use** through Phase 3d-2 as the accounting-period foundation for this app: layered correctly, tested at the unit and lifecycle level (~211 framework tests), and constrained enough to extend without a second architecture. The main cost is **ERPNext free-function patching** and the **Budget Variance dual-path**—acceptable given ERPNext v16 constraints, but they remain the primary long-term maintenance and upgrade risks. Phase 3 Final assessment: **Ready with caveats** (see `docs/BUSINESS_CALENDAR_PHASE3_RELEASE.md`).

---

## Related documents

| Document | Role |
|----------|------|
| `docs/business_calendar_phases_0_2.md` | Early phase notes |
| `docs/asset_business_calendar_integration.md` | Asset call graph |
| `docs/business_period_engine.md` | Period engine + patch primer |
| `docs/budget_business_calendar.md` | Phase 3b Budget / Monthly Distribution |
| `docs/budget_variance_trends.md` | Phase 3c Trends / Budget Variance |
| `docs/sales_purchase_analytics.md` | Phase 3d-1 Sales / Purchase Analytics |
| `docs/stock_analytics.md` | Phase 3d-2 Stock Analytics + manufacturing rebinds |
| `docs/BUSINESS_CALENDAR_PHASE3_RELEASE.md` | Phase 3 Final hardening / release readiness |
| `docs/UPGRADE_GUIDE.md` | Phase 4a upgrade safety, diagnostics, contract recovery |
| `docs/SDK.md` | Phase 4b extension SDK |
| `docs/API_REFERENCE.md` | Public API (`persian_calendar.api`) |

This Architecture Freeze is the authoritative overview; module docs remain detailed companions.
