# Phase 5A Design Audit — CRM Jalali Coverage & Conversion API

**Status:** Audit only (no behavioral implementation in this document’s companion commit)  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0** · `persian_calendar` **1.7.0**  
**Date:** 2026-07-29

This audit separates:

1. **Display / conversion** (`toshamshi` and Desk Display Calendar)
2. **Business-period grouping** (`BusinessPeriodEngine` + Company Business Calendar)

---

## 1. Naming finding (critical)

There is **no** function named `toshamsi` in this bench or app.

The production helper is spelled:

**`toshamshi`** (with an **h**)

| Search term | Result |
|-------------|--------|
| `toshamsi` / `to_shamsi` / `toShamsi` | **Zero definitions** in `persian_calendar`, Frappe, ERPNext |
| `toshamshi` | Canonical implementation + Jinja + brace templates + docs + tests |

All Print Format / Jinja / brace-template documentation already uses **`toshamshi`**.  
Phase 5A must **preserve `toshamshi`**. A `toshamsi` alias may be added later for typo tolerance, but must not replace the existing name.

---

## 2. `toshamshi` definition

| Field | Value |
|-------|--------|
| File | `persian_calendar/utils/jalali.py` |
| Line | ~104 |
| Import path | `persian_calendar.utils.jalali.toshamshi` |
| Re-export | `persian_calendar.utils` (`__all__`) |
| Public API today | **Not** on `persian_calendar.api` (Phase 4b) — gap |
| Whitelisted | No (not required for Jinja methods) |
| Jinja | Yes — `hooks.py` → `jinja.methods = ["persian_calendar.utils.jalali"]` |

### Signature (verified)

```python
def toshamshi(
    value: Any,
    include_time: bool = False,
    format: str = "YYYY-MM-DD",
    persian_digits: bool = False,
) -> str:
```

Positional usage in the wild (erpnext_extensions):  
`toshamshi(posting, format="YYYY/MM/DD")` — **keyword `format=` is used**; changing arity/order would break callers.

### Behaviour (verified from source + tests)

| Concern | Behaviour |
|---------|-----------|
| None / `""` | `""` |
| `date` / `datetime` / ISO strings | Convert Gregorian → Jalali via `jdatetime` |
| Microseconds in strings | Stripped |
| Timezone | **None** — uses calendar parts as stored; no zone conversion |
| Locale | Not used; digits only via `persian_digits` |
| Persian digits | Optional `persian_digits=True` → ۰–۹ |
| Year heuristic | Years **1200–1600** treated as already Jalali (pass-through format) |
| Years ≥ 1700 | Treated as Gregorian |
| Ambiguous years | Outside heuristics → parse may fail → `""` |
| Invalid input | Returns `""` (no throw) |
| Display Calendar | **Not consulted** — pure conversion |
| BusinessPeriodEngine | **Not used** (correct for display) |

### Related helpers (same module)

| Symbol | Role |
|--------|------|
| `to_persian_digits` | Digit map only |
| `gregorian_to_jalali_for_export` | Thin wrapper over `toshamshi` for Data Import/Export |
| `coerce_gregorian_datetime` / `jalali_to_gregorian_datetime` | Storage coercion (inverse path) |

### Duplicate conversion algorithms (not named toshamshi)

| Location | Notes |
|----------|--------|
| `jalali_support/formatters.py` → `gregorian_to_jalali(gy,gm,gd)` | Separate algorithm for FS period **labels** under Display Calendar |
| `jalali_support/api.py` → `convert_to_jalali` | Whitelisted API returning dict parts |
| Desk Display Calendar JS | Client formatters (frozen Display architecture) |

These must **not** be merged into `toshamshi` without an explicit Display-layer design; they serve different contracts.

---

## 3. `toshamshi` call sites (verified)

### In `persian_calendar`

| Area | Path |
|------|------|
| Definition | `utils/jalali.py` |
| Package export | `utils/__init__.py` |
| Brace templates | `utils/template_format.py` |
| Notification context | `jalali_support/template_hooks.py` |
| Data export | `utils/data_io.py` via `gregorian_to_jalali_for_export` |
| Tests | `utils/test_jalali.py`, `test_template_format.py`, `test_datetime_coercion.py`, `test_data_io.py` |
| Docs | `docs/print_format_jalali_helper.md`, `docs/jalali_template_syntax.md` |

### Outside app (same bench)

| Area | Path |
|------|------|
| Voucher GL print | `erpnext_extensions/.../voucher_gl_layout.py` |
| Print fixtures/tests | `erpnext_extensions/.../voucher_gl_print_fixtures.py`, `test_voucher_gl_print_language.py` |

### Jinja / Print / Email

| Surface | Status |
|---------|--------|
| Print Format Jinja | Registered via `hooks.jinja.methods` |
| PDF | Same Jinja env as print |
| Email Notification | Jinja + top-level field expose via `template_hooks` |
| Brace `{toshamshi(field)}` | `render_brace_template` (not full Jinja) |

---

## 4. Recommended canonical conversion contract

**Keep name:** `toshamshi` (compatibility).

**Stable public export (Phase 5a-1):**

```python
from persian_calendar.api import toshamshi
# legacy still works:
from persian_calendar.utils.jalali import toshamshi
```

**Do not change** default signature or defaults without a compatibility wrapper.

Optional later aliases (explicit contract only):

- `toshamsi` → alias of `toshamshi` (typo tolerance)
- `to_jalali_date` / `format_jalali_date` — only if they wrap the same implementation

**Non-goals for this API:** period boundaries, SQL filters, Business Calendar.

---

## 5. CRM DocType inventory (ERPNext 16.29)

Module `erpnext.crm` DocTypes include: Lead, Opportunity, Prospect (+ Lead/Opportunity children), Appointment (+ booking settings/slots), Campaign, Campaign Email Schedule, Email Campaign, CRM Note, CRM Settings, Sales Stage, Opportunity Type/Item/Lost Reason, Market Segment, Competitor, Contract (+ templates), etc.

### Date / Datetime fields (representative)

| DocType | Company field? | Notable date fields | Classification |
|----------|----------------|---------------------|----------------|
| Lead | Yes | `qualified_on`; also `creation`/`modified` in reports | B/G display; D filter on creation |
| Opportunity | Yes | `expected_closing`, `transaction_date`; `first_response_time` Duration | C candidate via pipeline; B/G display |
| Prospect | Yes | mostly links | Display |
| Appointment | **No** | `scheduled_time` Datetime | E scheduling (Gregorian time); B display |
| Campaign | **No** | — | Display / config |
| Email Campaign | **No** | `start_date`, `end_date` | E schedule windows; B display |
| CRM Note | **No** | `added_on` | B display |

**Company resolution:** Lead / Opportunity / Prospect have `company`. Appointment / Campaign / Email Campaign / CRM Note do **not** — Business Calendar grouping is **blocked** without an explicit report filter or linked Opportunity/Customer company.

---

## 6. CRM report inventory

### Under `erpnext/crm/report/`

| Report | Period grouping? | Company filter? | Engine / notes | Phase 5A class |
|--------|------------------|-----------------|----------------|----------------|
| **Sales Pipeline Analytics** | **Yes** — Monthly / Quarterly via SQL `Month` / `Quarter` / `MonthName` on `expected_closing` | Yes (default user company) | Own class `SalesPipelineAnalytics`; English month names as keys | **Business-period candidate** (hard: SQL Gregorian extract) |
| Opportunity Summary by Sales Stage | No (stage columns) | Yes | Date range on `transaction_date` | Display + filter only |
| Lost Opportunity | No | Yes | `modified` between dates | Display + filter |
| Lead Details | No | Yes | `creation` between dates | Display + filter |
| Lead Owner Efficiency | No | — | from/to dates | Display + filter |
| Lead Conversion Time | No | — | creation windows | Ageing / display |
| First Response Time for Opportunity | Daily buckets by `date(creation)` | No | Chart by calendar day | Display / daily (not M/Q/Y engine) |
| Campaign Efficiency | No | — | `date(creation)` filters | Display + filter |
| Prospects Engaged but Not Converted | No | — | Lead age via creation | Display / ageing |

### CRM-adjacent (Selling)

| Report | Notes | Class |
|--------|-------|-------|
| Customer Acquisition and Loyalty | Monthly view uses Gregorian month buckets + company | Business-period candidate (separate selling adapter; deferred or 5a-4) |
| Sales Analytics / Quotation Trends | Already covered by Phase 3d (not CRM module) | Done |

### Dashboard charts / number cards (CRM)

Examples: `opportunity_trends`, `incoming_leads`, `won_opportunities`, `territory_wise_opportunity_count`, number cards “last 1 month”.  

These use Frappe timespan filters (Gregorian). Classify as **display / timespan** unless a chart source is reimplemented — **deferred** for Business Calendar; Display Calendar may already format axis labels where Desk supports it.

---

## 7. Sales Pipeline Analytics — verified call graph

```text
execute(filters)
  → SalesPipelineAnalytics(filters).run()
       → validate_filters (from_date, to_date mandatory)
       → get_columns → set_range_columns (English month names or Q1–Q4)
       → get_data → get_fields
            → Month(opp.expected_closing) / Quarter(...)  # SQL Gregorian
            → MonthName(...).as_("month")                 # English labels as keys
       → get_periodic_data / append_data
       → get_chart_data
```

**Supported UI ranges:** Monthly, Quarterly only (no Weekly / Half-Yearly / Yearly).

**Company:** Optional filter; used in conditions + currency.

**Patch strategy risk:** High — grouping is in **SQL** (`Month`/`Quarter`), not a Python period helper like Stock/Sales Analytics. Jalali Business Calendar needs either:

- fetch raw rows and bucket in Python with `BusinessPeriodEngine`, or  
- a dedicated query rewrite adapter  

**Not** a Trends/Stock helper rebind.

---

## 8. Company resolution policy (proposed)

| Context | Policy |
|---------|--------|
| Reports with `company` filter (Pipeline, Lead Details, …) | Use filter company → `get_business_calendar_for_company` |
| DocType with `company` (Lead, Opportunity) | Document company for BC when period math exists |
| Appointment / Campaign / Email Campaign | No BC period math without explicit company argument |
| Mixed companies | Reject or keep Gregorian (same as Sales Analytics) |
| Missing company on Pipeline | Preserve stock (may still run); Jalali engine path requires company |

---

## 9. Classification summary

### Business-period candidates

1. **Sales Pipeline Analytics** (primary CRM) — Monthly/Quarterly; company available; SQL Gregorian month/quarter  
2. **Customer Acquisition and Loyalty** (Selling, CRM-adjacent) — Monthly; company available  

### Display-only / filter-only (use Display Calendar + `toshamshi` in print)

- Opportunity Summary by Sales Stage  
- Lost Opportunity, Lead Details, Lead Owner Efficiency, Lead Conversion Time  
- Campaign Efficiency, Prospects Engaged  
- Forms / List / Report View / Number Cards / most Dashboard Charts  
- Appointment schedules (time semantics stay Gregorian storage)  

### Blocked / deferred

- Full Jalali Weekly CRM (not exposed upstream)  
- Pipeline Half-Yearly / Yearly (not in UI)  
- Company-agnostic Appointment period reports  
- SQL `MonthName` English keys without adapter rewrite  
- HRMS / MRP (non-goals)  

---

## 10. Suggested implementation slices

| Slice | Scope | Commit style |
|-------|--------|--------------|
| **5a-0** | This audit documentation | `docs(calendar): audit crm jalali coverage and toshamshi usage` |
| **5a-1** | Export `toshamshi` on `persian_calendar.api`; docs `TOSHAMSI.md`; optional `toshamsi` alias; tests; **no signature break** | `refactor(calendar): expose canonical toshamshi conversion api` |
| **5a-2** | CRM display verification matrix (forms/list/print); no BC math | `feat(calendar): add jalali display support for crm` |
| **5a-3** | Sales Pipeline Analytics BC adapter (Python bucketing or proven safe patch) | `feat(calendar): support business calendar in crm analytics` |
| **5a-4** | Customer Acquisition / remaining period reports if justified | same family |
| **5a-5** | Contracts, registry, diagnostics, release_check | `test(calendar): add crm jalali compatibility coverage` |

Do **not** bump app version until approved slices complete.

---

## 11. Files expected to change (later slices — not this audit)

| Slice | Likely paths |
|-------|----------------|
| 5a-1 | `persian_calendar/api/__init__.py`, `docs/TOSHAMSI.md`, `docs/API_REFERENCE.md`, `docs/SDK.md`, tests |
| 5a-2 | Possibly none if Display already covers Desk; CRM_JALALI.md verification notes |
| 5a-3 | `calendar/integrations/crm_pipeline.py` (new), `patches.py`, `contracts.py`, `registry.py` |
| 5a-5 | `diagnostics.py`, contract tests |

---

## 12. Initial audit answers (checklist)

1. **Definition path:** `persian_calendar.utils.jalali.toshamshi` (not `toshamsi`)  
2. **Signature:** `(value, include_time=False, format="YYYY-MM-DD", persian_digits=False) -> str`  
3. **Users:** print/Jinja, brace templates, data export, erpnext_extensions GL print, tests  
4. **Jinja/Print:** Registered; documented; PDF via same env  
5. **Duplicates:** No second `toshamshi`; separate `gregorian_to_jalali` in formatters/api  
6. **Canonical API:** Keep `toshamshi`; add to `persian_calendar.api`; optional `toshamsi` alias  
7. **CRM modules:** Full `erpnext.crm` DocType set listed above  
8. **CRM reports:** 9 script reports under `crm/report` + charts/cards  
9. **Business-period candidates:** Sales Pipeline Analytics; (adjacent) Customer Acquisition  
10. **Display-only candidates:** Most other CRM reports + Desk/print  
11. **Company risks:** Pipeline OK; Appointment/Campaign lack company  
12. **Plan:** 5a-0…5a-5 as above  

PHASE 5A CRM AND TOSHAMSI DESIGN AUDIT COMPLETED
