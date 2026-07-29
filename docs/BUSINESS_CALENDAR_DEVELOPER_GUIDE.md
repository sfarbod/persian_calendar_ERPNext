# Business Calendar Framework — Developer Guide

**How to extend the framework after the Architecture Freeze**

| Field | Value |
|-------|--------|
| Audience | Maintainers, new contributors, reviewers, custom-app developers |
| Companion | [`docs/ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) |
| Scope | Implementation practice for Phases 0–3c and future integrations |

---

## 1. Introduction

### Purpose

This guide tells you **how** to add or change a Business Calendar integration without breaking Gregorian parity, historical documents, or the frozen architecture.

It is a working handbook: decision trees, recipes, checklists, and copy-paste patterns.

### Relationship to the Architecture document

| Document | Answers |
|----------|---------|
| [`ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) | **Why** the framework exists, what is frozen, ADRs, compatibility matrix, risks |
| **This Developer Guide** | **How** to extend it correctly day to day |

Read the Architecture document first (at least sections 1–2, 4–5, 12, and the ADRs). This guide assumes those decisions are fixed.

Do not invent a parallel period engine, a second patch applicator, or Display-Calendar-driven business math. If a change conflicts with an ADR, update design and documentation deliberately—do not “just make it work.”

---

## 2. Mental Model

```text
Storage  →  always Gregorian dates in DB/API
Display  →  per-user UI only
Business →  per-company period semantics

CalendarEngine / Providers
        ↓
BusinessPeriodEngine          ← canonical period lists
        ↓
Adapters (Gregorian delegate / Jalali map)
        ↓
ERPNext consumers (DocTypes, reports, free functions)
        ↑
apply_calendar_patches()      ← only for unavoidable free functions
override_doctype_class        ← prefer for DocType methods
```

| Concept | Responsibility | Ownership |
|---------|----------------|-----------|
| **Storage Calendar** | Persist ISO/Gregorian dates | Platform / ERPNext |
| **Display Calendar** | Format and pick dates in Desk | User preference (UI) |
| **Business Calendar** | Which calendar owns period arithmetic | `Company.business_calendar` |
| **CalendarProvider** | Pure `add_months` / month bounds | Framework library |
| **CalendarEngine** | Resolve provider for a company | Framework library |
| **BusinessPeriodEngine** | Ordered period lists | Framework — **canonical** |
| **period_labels** | Human-readable strings | Presentation only |
| **Adapter** | Map engine ↔ ERPNext shapes | `calendar/integrations/` |
| **Patch applicator** | Capture + rebind free functions | `calendar/patches.py` |
| **Consumer** | Stock ERPNext DocType/report | ERPNext (unchanged source) |

**Rule of thumb:** business boundaries come from the engine; labels come from `period_labels`; storage stays Gregorian; Display Calendar stays out of resolvers.

---

## 3. Golden Rules

Use this as a pre-merge checklist:

1. **`BusinessPeriodEngine` is canonical** for Monthly / Quarterly / Half-Yearly / Yearly business lists.
2. **Never duplicate Jalali arithmetic** inside reports or DocTypes (`jdatetime` loops, hand-rolled Farvardin tables, etc.).
3. **Never globally patch** `frappe.utils` (`add_months`, `formatdate`, `get_last_day`, `strftime`, …).
4. **Display Calendar never affects business calculations.**
5. **Prefer Gregorian delegation** to the captured stock ERPNext function / `super()`.
6. **Labels are presentation only** — never allocation keys or match keys.
7. **Match periods using Gregorian `start_date` / `end_date`** (or stable `BusinessPeriod.key`), not month names.
8. **Preserve submitted documents** — do not rewrite historical Budget Distribution rows or booked schedules on calendar change.
9. **Prefer `override_doctype_class`** for DocType instance methods.
10. **Use `apply_calendar_patches()` only** when a module-level free function must be intercepted; extend the **same** applicator.
11. **Reject mixed Business Calendars** explicitly in multi-company contexts.
12. **Add Gregorian parity tests** before claiming Jalali correctness.
13. **Do not edit ERPNext source** in this app’s integrations.
14. **Call `apply_calendar_patches()` explicitly** in `bench execute` / console (no auto hook there).

---

## 4. Decision Tree

```text
What do you need?

┌─ Change DocType instance method behaviour
│     → override_doctype_class → subclass → Gregorian: super() / stock
│                                         → Jalali: BusinessPeriodEngine or provider
│
├─ Replace module-level helper already imported by consumers
│     → apply_calendar_patches() target + identity rebind
│     → NOT a new ad-hoc monkey patch module
│
├─ Generate business period date ranges
│     → BusinessPeriodEngine.generate(...)
│
├─ Show Jalali text to a user (picker / format only)
│     → Display Calendar / existing Desk JS
│     → NOT BusinessPeriodEngine for math you will store/key on
│
├─ Column / chart axis caption for a BusinessPeriod
│     → format_period_label(period, locale=...)
│     → NOT use label as dict key
│
├─ “Just patch add_months everywhere”
│     → STOP — forbidden (ADR-009)
│
└─ Store Jalali strings in Date fields
      → STOP — forbidden (ADR-001)
```

### Quick map to existing modules

| Need | Pattern already used |
|------|----------------------|
| Budget periods | `override_doctype_class` → `PersianCalendarBudget` |
| Asset schedule stepping | DocType overrides + narrow disposal patch |
| FS `get_period_list` | Central applicator |
| Trends `get_period_date_ranges` | Central applicator |
| Budget Variance (month-name keys) | Central applicator on `execute` + Jalali adapter |
| Monthly Distribution free functions | Central applicator |

---

## 5. How to Add a New Module

### Step-by-step workflow

1. **Audit installed ERPNext** (version-pin; do not trust old notes alone).
2. **Identify the extension point** (DocType method vs free function vs Script Report `execute`).
3. **Prefer override** when the logic lives on a DocType class.
4. **Write a thin adapter** under `persian_calendar/calendar/integrations/`.
5. **Gregorian path:** call captured original or `super()`.
6. **Jalali path:** `BusinessPeriodEngine` (or provider for single-date stepping); map to stock return shape.
7. **Company resolution:** explicit company from document/filters; never Display Calendar.
8. **Tests:** Gregorian parity, Jalali boundaries, patch lifecycle if patched, Display independence.
9. **Docs:** update Architecture companion notes and this guide’s “related” list if behaviour is user-visible.
10. **Upgrade checklist:** if you add a patch target, update registries and Compatibility Matrix notes.

### By consumer type

#### DocType

```python
# hooks.py — override_doctype_class entry
# "My DocType": "persian_calendar.calendar.integrations.my_mod.PersianCalendarMyDocType"

class PersianCalendarMyDocType(MyDocType):
	def get_periods(self):
		from persian_calendar.calendar.resolve import (
			BUSINESS_CALENDAR_GREGORIAN,
			get_business_calendar_for_company,
		)
		if get_business_calendar_for_company(self.company) == BUSINESS_CALENDAR_GREGORIAN:
			return super().get_periods()
		# Jalali: BusinessPeriodEngine → stock-shaped return
		...
```

Reference: `integrations/budget.py`.

#### Free function

1. Implement adapter with `set_original_…` / Gregorian delegation.
2. Register capture + replace + consumer list inside `apply_calendar_patches()`.
3. Add lifecycle tests (import-before / import-after / unrelated same name).

Reference: `integrations/trends.py`, `patches.py`.

#### Script Report

- If the report only needs period **ranges**, patching a shared helper (e.g. Trends) may be enough.
- If the report **keys amounts by English month names**, Trends ranges alone are insufficient — you need a narrow report adapter (Budget Variance pattern).
- Prefer reusing stock helpers for data fetch; replace only the calendar-sensitive part.

#### Query Report / utility module

- Prefer calling `BusinessPeriodEngine` from your app code without patching ERPNext.
- Patch only if ERPNext code path cannot be reached otherwise.

---

## 6. Patch Guidelines

### When patching is allowed

- Target is a **module-level free function** consumed via `from x import f`.
- No supported Frappe override covers the call site.
- You can capture the original once and prove Gregorian delegation.

### When patching is forbidden

- Global `frappe.utils.*` replacement.
- Patching “because it is easier” when `override_doctype_class` works.
- A second independent applicator / `PatchStatus` system.
- Rebinding by attribute name alone (would hit unrelated `get_period_date_ranges` in Analytics).

### How `apply_calendar_patches()` works

```text
apply_calendar_patches()
  → capture stock fn once (never capture adapter)
  → set_original_* on adapter module
  → replace source module attribute with adapter
  → identity-rebind known consumers (and erpnext.* scan)
  → PatchStatus: applied | partial_rebind | failed | source_unavailable
```

Hooks (request / job / tests) call the applicator. **Console does not** — call it yourself:

```python
from persian_calendar.calendar.patches import apply_calendar_patches
apply_calendar_patches()
```

### Common mistakes

| Mistake | Fix |
|---------|-----|
| Capturing adapter as “original” | Reset in tests; capture only stock |
| Forgetting rebind of early imports | Known consumer registry + lifecycle test |
| Patching Analytics’ same-named helper | Identity check; keep registries tight |
| Ignoring `partial_rebind` in prod | Do not ship until rebound |

Architecture detail: Architecture doc §4 and ADR-008 / ADR-012.

---

## 7. BusinessPeriodEngine

### Inputs

| Argument | Meaning |
|----------|---------|
| `start_date` / `end_date` | Gregorian `date` or ISO string |
| `periodicity` | `"Monthly"` \| `"Quarterly"` \| `"Half-Yearly"` \| `"Yearly"` |
| `company` | Resolve Business Calendar (ignored if `provider` set) |
| `provider` | Explicit `CalendarProvider` |

### Outputs

`list[BusinessPeriod]` — each with Gregorian `from_date` / `to_date`, stable `key`, empty `label` at generation, `calendar_system`, `year`, `period_number`.

### Example

```python
from persian_calendar.calendar.period_engine import BusinessPeriodEngine
from persian_calendar.calendar.period_labels import format_period_label

periods = BusinessPeriodEngine.generate(
	start_date="2026-03-21",
	end_date="2027-03-20",
	periodicity="Monthly",
	company="My Company",
)

for p in periods:
	# Use p.from_date / p.to_date / p.key for logic
	caption = format_period_label(p, locale="en")  # presentation only
```

### Partial ranges

If `end_date` cuts mid-period, the last period’s `to_date` is clamped to `end_date`. Prefer extending the engine API over copying clamp logic into a report.

### Labels

```python
from persian_calendar.calendar.period_labels import format_period_label

format_period_label(period, locale="fa")  # or "en"
```

Never: `amounts[format_period_label(p)] = …`.

---

## 8. Adapter Design

### Responsibilities

| Adapter should | Adapter must not |
|----------------|------------------|
| Resolve Business Calendar from **company** | Read Display Calendar |
| Delegate Gregorian to stock | Reimplement Gregorian period math “for convenience” |
| Call `BusinessPeriodEngine` for Jalali lists | Embed Farvardin/Esfand tables |
| Return **exact stock shapes** | Expose `BusinessPeriod` to stock code that does not expect it |
| Validate mixed calendars when multi-company | Silently pick `companies[0]` |

### Canonical branch

```text
if business_calendar == "Gregorian":
    return original_stock_function(...)
else:
    periods = BusinessPeriodEngine.generate(...)
    return map_to_stock_shape(periods)
```

Reference implementations:

- DocType: `integrations/budget.py`
- Free function: `integrations/trends.py`, `integrations/financial_statements.py`
- Report replace: `integrations/budget_variance.py`

---

## 9. Company Resolution

### Preferred order

1. Explicit company on the document or report filters.
2. Adapter keyword (e.g. Trends optional `company=`) when safely plumbed.
3. `frappe.local.form_dict.company` when the report posts filters that way.
4. Fiscal Year Company links — **all must share one Business Calendar** or throw.
5. User default company / Global Defaults (CalendarEngine / resolver fallback).
6. Gregorian safe default.

API: `get_business_calendar_for_company(company)` in `calendar/resolve.py`.

### Why Display Calendar is ignored

Accounting must not change when two users with different UI calendars open the same company. See Architecture ADR-002 / ADR-003.

### Mixed companies

```text
Companies A=Jalali, B=Gregorian on one Fiscal Year / consolidated report
  → throw with company names and detected calendars
  → do not average, do not pick first
```

---

## 10. Testing

### Minimum matrix for a new integration

| Case | Intent |
|------|--------|
| Gregorian parity | Adapter output equals stock / captured original |
| Jalali monthly / quarterly / … | Boundaries match Farvardin–Esfand expectations |
| Leap Esfand | 30-day Esfand in leap years |
| Storage dates | Returned dates are `datetime.date` Gregorian |
| Display independence | Changing user lang / display preference does not change boundaries |
| Patch lifecycle | Import-before rebound; import-after gets adapter; unrelated same name untouched |
| Historical | Submitted stored dates still match; no silent rewrite |
| Mixed calendar | Clear validation error |
| Labels | Not used as keys |

### Running framework suites

```bash
cd /path/to/frappe-bench
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app persian_calendar --module persian_calendar.calendar.test_period_engine
# likewise: test_providers, test_resolve, test_patches,
# integrations.test_assets, test_budget, test_monthly_distribution,
# test_trends, test_budget_variance, test_sales_analytics, test_stock_analytics
```

See Architecture §10 and `docs/BUSINESS_CALENDAR_PHASE3_RELEASE.md` for the verified suite list.

### Test hygiene

- Use `reset_calendar_patches_for_tests()` around patch tests.
- Do not rely on accidental import order.
- Prefer stubs over full GL fixtures when testing allocation pure functions.

---

## 11. Common Mistakes

| Mistake | Why it fails | Do this instead |
|---------|--------------|-----------------|
| `amounts[row.month_name]` / `strftime("%B")` for Jalali | Wrong bucket; locale drift | Match `start_date`/`end_date` |
| `frappe.db.get_value("User", …, "calendar")` for periods | User-dependent books | `get_business_calendar_for_company` |
| Copy-paste `jdatetime` loops in a report | Divergent calendars | `BusinessPeriodEngine` |
| `frappe.utils.add_months = my_jalali_add` | Corrupts unrelated code | Provider / engine |
| Regenerating submitted Budget rows on Company calendar change | Breaks audit trail | Keep stored rows; amend explicitly |
| Skipping Gregorian tests “because Jalali is the feature” | Silent regressions for default sites | Always test both |
| New `apply_my_patches()` beside the central applicator | Split brain PatchStatus | Extend `apply_calendar_patches` |
| Assuming Trends patch fixes Budget Variance | Stock still keys English months | Narrow `execute` adapter if needed |

---

## 12. Code Review Checklist

Reviewers can paste this into the PR:

```text
Business Calendar PR checklist

Design
□ Extension point audited on installed ERPNext version
□ override_doctype_class preferred over free-function patch when possible
□ If patched: target registered in apply_calendar_patches only
□ No second patch applicator / PatchStatus

Arithmetic
□ BusinessPeriodEngine (or provider) used for Jalali period lists / steps
□ No duplicated Jalali month tables in the consumer
□ Gregorian path delegates to stock / super() / captured original

Calendar ownership
□ Company Business Calendar drives calculations
□ Display Calendar not consulted for boundaries
□ Mixed-company calendars rejected or explicitly contracted

Data safety
□ Labels not used as match/allocation keys
□ Submitted / historical boundaries preserved
□ Returned/stored dates remain Gregorian

Quality
□ Gregorian parity tests
□ Jalali boundary + leap tests where applicable
□ Patch lifecycle tests if patching
□ Docs updated (module note and/or this guide / Architecture matrix)
□ No ERPNext source edits
□ No global frappe.utils patch
□ App version not bumped unless requested
```

---

## 13. FAQ

**Q1. Why not patch `add_months`?**  
Because it is used across ERPNext. A global Jalali replacement would corrupt Gregorian companies and unrelated workflows (ADR-009).

**Q2. Why not store Jalali dates in the database?**  
Frappe/ERPNext Date fields and SQL assume Gregorian/ISO. Jalali is a business interpretation of the same stored instant/date (ADR-001).

**Q3. Why not use translated month names as keys?**  
They change with language and calendar. “March” is not Farvardin. Use dates or stable keys (ADR-006).

**Q4. Why runtime patches at all?**  
Many ERPNext helpers are free functions imported by binding. DocType overrides cannot replace them; identity rebind is required (Architecture §4).

**Q5. Why is Business Calendar on Company?**  
Period semantics are an organizational accounting policy, not a personal UI choice (ADR-003).

**Q6. Why Gregorian delegation instead of one engine for everyone?**  
Default sites must match stock ERPNext exactly; delegation minimizes upgrade drift (ADR-005).

**Q7. When is Trends patch not enough?**  
When the consumer re-buckets by Gregorian month names after receiving ranges (Budget Variance). Fix the consumer path, do not only change ranges.

**Q8. Why must I call the applicator in console?**  
There is no Frappe hook for `bench execute`. Request/job/tests bootstrap automatically; console does not.

**Q9. Can I add a new periodicity (e.g. Weekly)?**  
Only by extending `BusinessPeriodEngine` with tests and Architecture/Compatibility updates—do not special-case one report.

**Q10. Where do I put new code?**  
Adapters: `persian_calendar/calendar/integrations/`. Engine/providers: `persian_calendar/calendar/`. Do not put Jalali math under `public/js` for accounting.

**FAQ count: 10**

---

## 14. Recipes

### Recipe A — Integrate a new Script Report

1. Audit `execute` and how periods/amounts are keyed.
2. If only ranges matter and a shared helper exists → extend Trends-style adapter carefully (confirm same function object).
3. If month-name keys → write report adapter; register in `apply_calendar_patches`.
4. Gregorian → captured `execute`.
5. Jalali → engine periods + date matching + inclusive GL dates.
6. Tests + docs.

### Recipe B — Integrate a DocType method

1. Confirm method is on the DocType class (not a free function).
2. Subclass + `override_doctype_class` in `hooks.py`.
3. `super()` for Gregorian; engine for Jalali.
4. Keep child table storage as Gregorian dates.

### Recipe C — Integrate a utility free function

1. Inventory `from module import fn` consumers.
2. Adapter + `set_original_*`.
3. Register in applicator with known-consumer tuple.
4. Lifecycle tests for rebind.

### Recipe D — Add labels for a new report column

```python
from persian_calendar.calendar.period_labels import format_period_label

columns.append({
	"label": format_period_label(bp, locale=locale),
	"fieldname": bp.key,  # stable key, not the label
	"fieldtype": "Currency",
})
```

### Recipe E — Add tests for a new adapter

Mirror `integrations/test_trends.py` / `test_budget.py`: parity with stock mirror or captured original; Jalali `_j(y,m,d)` helpers via `jdatetime`; patch `get_business_calendar_for_company` in unit tests.

### Recipe F — Explicit applicator in console

```python
from persian_calendar.calendar.patches import apply_calendar_patches, get_patch_state
print(apply_calendar_patches())
print(get_patch_state().status)
```

### Recipe G — Resolve calendar without Display

```python
from persian_calendar.calendar.resolve import get_business_calendar_for_company
from persian_calendar.calendar.engine import CalendarEngine

bc = get_business_calendar_for_company(company)
provider = CalendarEngine.for_company(company)
```

### Recipe H — Sales / Purchase Analytics (Phase 3d-1)

Shared class `erpnext.selling.report.sales_analytics.sales_analytics.Analytics`:

1. Patch class methods via `apply_calendar_patches` (`get_period_date_ranges`, `get_period`, `get_columns`, `get_chart_data`, `update_company_list_for_parent_company`).
2. Gregorian + Weekly → captured originals.
3. Jalali Monthly/Quarterly/Yearly → `BusinessPeriodEngine`; bucket id = `BusinessPeriod.key`.
4. Chart must read `fieldname`, not `scrub(label)`.
5. Purchase Analytics imports the same class — no duplicate adapter.

See `integrations/sales_analytics.py` and `test_sales_analytics.py`.

### Recipe I — Stock Analytics + manufacturing rebinds (Phase 3d-2)

Free functions on `erpnext.stock.report.stock_analytics.stock_analytics`:

1. Patch `get_period_date_ranges`, `get_period`, `get_period_columns` via `apply_calendar_patches`.
2. Do **not** patch `round_down_to_nearest_frequency` (captured original must remain on the module so Gregorian delegation via module globals stays correct).
3. Identity-rebind Production Analytics, Work Order Summary, Job Card Summary.
4. Gregorian + Weekly → captured originals; Jalali Monthly/Quarterly/Half-Yearly/Yearly → `BusinessPeriodEngine`.
5. Leave `get_periodic_data` unpatched — carry-forward uses stable `get_period` keys.
6. This is **not** core MRP/MPS.

See `integrations/stock_analytics.py`, `docs/stock_analytics.md`, and `test_stock_analytics.py`.

### Recipe J — Public SDK / new adapter (Phase 4b)

```python
from persian_calendar.api import (
    apply_calendar_patches,
    build_jalali_periods,
    should_use_jalali_engine,
    release_check,
)
```

1. Prefer `persian_calendar.api` over deep imports.
2. Use `adapter_helpers` + `patch_sdk` for new free-function adapters.
3. Register contracts, registry row, and `apply_calendar_patches` wiring.
4. See `docs/SDK.md` and `calendar/adapter_template.py`.

### Recipe K — Print / Jinja Jalali conversion (Phase 5A-1)

```python
from persian_calendar.api import toshamshi, toshamsi

toshamshi(doc.posting_date, format="YYYY/MM/DD")
assert toshamsi is toshamshi
```

```jinja
{{ toshamshi(doc.posting_date) }}
{{ toshamsi(doc.posting_date, include_time=True) }}
```

1. Use for **display conversion only** (Print / PDF HTML / email / scripts).
2. Do **not** use for business period boundaries or SQL grouping.
3. Canonical docs: [`TOSHAMSHI.md`](TOSHAMSHI.md).
4. Legacy path `persian_calendar.utils.jalali.toshamshi` remains supported.

**Recipes count: 11**

---

## 15. Contribution Policy

Every Business Calendar change must include:

| Requirement | Expectation |
|-------------|-------------|
| **Design** | Audited extension point; ADR-compatible; decision tree followed |
| **Tests** | Gregorian parity + Jalali (as applicable) + lifecycle if patched |
| **Documentation** | Module note and/or Architecture Compatibility Matrix / this guide |
| **Gregorian parity** | Default companies unchanged vs stock for the delegated path |
| **Historical safety** | No silent rewrite of submitted boundaries |
| **Scope** | No drive-by refactors; no version bump unless requested |
| **ERPNext** | App code only — do not vendor-edit ERPNext in the same change |

Pull requests that patch `frappe.utils`, key on translated month names, or derive periods from Display Calendar should be rejected unless there is an explicit Architecture ADR change.

---

## Related reading

| Doc | Use when |
|-----|----------|
| [`ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) | Why / freeze / ADRs / upgrade checklist |
| [`business_period_engine.md`](business_period_engine.md) | Engine + patch primer |
| [`budget_business_calendar.md`](budget_business_calendar.md) | Budget / Monthly Distribution |
| [`budget_variance_trends.md`](budget_variance_trends.md) | Trends / Budget Variance |
| [`sales_purchase_analytics.md`](sales_purchase_analytics.md) | Sales / Purchase Analytics |
| [`stock_analytics.md`](stock_analytics.md) | Stock Analytics + manufacturing rebinds |
| [`BUSINESS_CALENDAR_PHASE3_RELEASE.md`](BUSINESS_CALENDAR_PHASE3_RELEASE.md) | Phase 3 Final release readiness |
| [`UPGRADE_GUIDE.md`](UPGRADE_GUIDE.md) | Phase 4a upgrade safety / diagnostics |
| [`SDK.md`](SDK.md) | Phase 4b extension SDK |
| [`API_REFERENCE.md`](API_REFERENCE.md) | Public `persian_calendar.api` surface |
| [`asset_business_calendar_integration.md`](asset_business_calendar_integration.md) | Asset call graph |

---

## Quick import map

```text
persian_calendar.calendar.engine.CalendarEngine
persian_calendar.calendar.resolve.get_business_calendar_for_company
persian_calendar.calendar.period_engine.BusinessPeriodEngine
persian_calendar.calendar.period_labels.format_period_label
persian_calendar.calendar.patches.apply_calendar_patches
persian_calendar.calendar.integrations.*   # adapters only
```
