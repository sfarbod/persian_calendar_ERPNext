# CRM Display Calendar Coverage (Phase 5A-2)

**Status:** Verified — Outcome **A** (global coverage; tests/docs only)  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0** · `persian_calendar` **1.8.0**  
**Related:** [`CRM_JALALI_TOSHAMSHI_AUDIT.md`](CRM_JALALI_TOSHAMSHI_AUDIT.md) · [`TOSHAMSHI.md`](TOSHAMSHI.md)

This phase is **Display Calendar only**. Sales Pipeline **business** period
grouping is Phase 5A-3 — see [`CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md`](CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md).

---

## 1. Scope

Make CRM date/datetime **presentation** follow the existing Desk Display Calendar
architecture when the user’s preference is Jalali, without changing storage,
SQL grouping, or business-period semantics.

| In scope | Out of scope |
|----------|----------------|
| Form / List / Report View typed Date & Datetime | Sales Pipeline month/quarter **business** buckets |
| Query Report filters typed Date | `BusinessPeriodEngine` adapters |
| Explicit Print/Jinja via `toshamshi` / `toshamsi` | Scheduling / recurrence / SLA |
| Save-path Gregorian normalization | Stored Jalali values |
| Documentation + verification tests | Portal anonymous Display Calendar inference |

---

## 2. Display versus Business Calendar

| Calendar | Role in CRM |
|----------|-------------|
| **Storage** | Always Gregorian/ISO in DB and API |
| **Display** | User preference → desk formatters + Jalali datepicker |
| **Business** | Company `business_calendar` → period reports (deferred for CRM) |
| **Explicit** | `toshamshi` / `toshamsi` — always Jalali string; ignores Display & Business |

Do **not** use `toshamshi` as a substitute for global Display Calendar formatting
on Desk forms/lists. Prefer standard field rendering there.

Do **not** use Display Calendar formatters for query boundary arithmetic — the
client `user_to_str` path already converts Jalali picker input to Gregorian
before filters hit the server.

---

## 3. Audited DocTypes

### CRM module (`erpnext.crm`)

| DocType | Date / Datetime fields | Classification |
|---------|------------------------|----------------|
| Lead | `qualified_on` (Date) | **A** globally covered |
| Opportunity | `transaction_date`, `expected_closing` (Date) | **A** |
| Prospect | (links; child Prospect Opportunity has `expected_closing`) | **A** |
| Appointment | `scheduled_time` (Datetime) | **A** form/list; email args **E** (see §11) |
| Campaign | no Date fields in meta | **A** / N/A |
| Email Campaign | `start_date`, `end_date` | **A** |
| Campaign Email Schedule | schedule config | **D** operational times stay Gregorian storage |
| CRM Note | `added_on` (Datetime) | **A** |
| Contract | `start_date`, `end_date`, `signed_on`, `fulfilment_deadline` | **A** |
| Sales Stage / Opportunity Type / … | no dates | N/A |

### Related Desk / Selling (CRM context)

| DocType | Fields | Classification |
|---------|--------|----------------|
| Communication | `communication_date`, … | **A** |
| Event | `starts_on`, `ends_on` | **A** (Appointment syncs Event) |
| ToDo | `date` | **A** |
| Customer / Contact / Address | no Date fields in stock meta | N/A |
| Quotation (from Opportunity) | posting/transaction dates | **A** via Selling DocTypes + global desk |

**List view JS** (`lead_list.js`, `opportunity_list.js`, …): status indicators only —
**no** custom date formatters → **A**.

---

## 4. Audited reports

| Report | Date filters | Date columns | Display notes | Business period |
|--------|--------------|--------------|---------------|-----------------|
| Sales Pipeline Analytics | Date from/to | Month/Q labels (not Date cols) | Filters **A**; Jalali BC periods in 5A-3 | Implemented 5A-3 |
| Opportunity Summary by Sales Stage | Date | none | **A** filters | N/A |
| Lost Opportunity | Date | none | **A** | N/A |
| Lead Details | Date | none | **A** | N/A |
| Lead Owner Efficiency | Date | none | **A** | N/A |
| Lead Conversion Time | Date | durations | **A** filters; ageing stays Gregorian math | N/A |
| First Response Time | Date | `creation_date` **Date** | Grid **A**; chart axis raw ISO **E** | N/A |
| Campaign Efficiency | Date | none | **A** | N/A |
| Prospects Engaged | — | `last_communication_date` Date; `last_communication` Data | Date col **A**; Data text **E** | N/A |

---

## 5. Globally covered surfaces

Desk JS (`jalali_support.bundle.js`):

- `frappe.datetime.str_to_user` / `user_to_str` / `format_date` / `format_datetime`
- `frappe.form.formatters.Date` / `Datetime`
- `frappe.format` coerce wrapper
- `ControlDate` / `ControlDatetime` → Jalali picker

Server:

- `doc_events["*"].validate` → `datetime_normalizer` (Gregorian storage)
- Boot: `extend_bootinfo` → `persian_calendar.display_calendar`
- **No** monkey-patch of `frappe.utils.formatdate` / `format_datetime`

CRM inherits all of the above for standard typed Date/Datetime fields.

---

## 6. CRM-specific fixes

**None in Phase 5A-2.**

No CRM `doctype_js` overrides, no CRM display adapters, no SQL/report grouping
changes. Inventory + tests document that global coverage is sufficient for
typed fields.

---

## 7. Form behavior

When Display Calendar = Jalali:

- Date/Datetime controls show Jalali and open the Jalali picker.
- Save path coerces accidental Jalali strings to Gregorian via normalizer.
- Read-only / formatted values use patched formatters.

When Display Calendar = Gregorian: upstream Frappe controls unchanged.

Verified representative fields: Opportunity `transaction_date` /
`expected_closing`, Appointment `scheduled_time`, Lead `qualified_on`, Email
Campaign dates, CRM Note `added_on`, Contract dates.

---

## 8. List behavior

Absolute Date/Datetime columns use `frappe.format` → Display Calendar.

Relative labels (“2 days ago”) remain upstream.

Filter chip **values** remain Gregorian machine strings after `user_to_str`.

---

## 9. Report behavior

- Filters with `fieldtype: "Date"` → Jalali picker; queries receive Gregorian.
- Columns typed Date/Datetime → Jalali cell display.
- Sales Pipeline Monthly/Quarterly **business** labels follow Company Business
  Calendar when Jalali (Phase 5A-3). Gregorian companies keep upstream English
  month / Q labels. Display Calendar still does not drive those buckets.

---

## 10. Print / PDF behavior

| Mechanism | Behaviour |
|-----------|-----------|
| Standard `formatdate` / print field rendering | Remains Gregorian (by architecture) |
| `{{ toshamshi(...) }}` / `{{ toshamsi(...) }}` | Explicit Jalali (independent of Display Calendar) |
| Brace `{toshamshi(field)}` | Non-Jinja templates |

**Recommended pattern**

- Desk UX → Display Calendar (automatic).
- Print/PDF that must be Jalali regardless of viewer → explicit `toshamsi` /
  `toshamshi`.

---

## 11. Email / Notification behavior

| Path | Behaviour |
|------|-----------|
| Notification Jinja with `toshamshi` | Explicit Jalali |
| Appointment `send_appointment_confirmed_email` | Uses `frappe.utils.format_datetime` → **Gregorian** (limitation) |
| Background jobs without user session | Prefer explicit `toshamshi` in templates; do not infer Company BC |

Do not apply Company Business Calendar to emails.

---

## 12. Timeline / Communication

Form timeline and Communication DocType Datetime fields use desk formatters
where Frappe renders absolute timestamps via `frappe.format` / datetime helpers.

Relative timeline labels may stay upstream.

Do **not** rewrite free-text comment bodies.

---

## 13. Export behavior

| Export | Policy |
|--------|--------|
| Query Report / List Excel (`make_xlsx`) | Gregorian by design |
| Data Export with Jalali flag | Global `data_import_export` → `toshamshi` |
| CRM-specific export code | None |

---

## 14. Portal / web

Appointment portal and public pages: **no** inferred Display Calendar for
anonymous users. Template authors may call `toshamsi` explicitly. Deferred /
unsupported for automatic preference.

---

## 15. Timezone notes

- Desk Display Calendar and `toshamshi` use wall-clock components; no site TZ
  redesign in this phase.
- Appointment scheduling comparisons remain Gregorian datetime semantics.

---

## 16. Known limitations

1. Sales Pipeline Gregorian companies still show English month / Q labels (upstream).
2. First Response chart X-axis raw ISO dates (grid column is fine).
3. Appointment confirmed email `format_datetime` Gregorian.
4. Standard Print `formatdate` Gregorian unless template uses `toshamshi`.
5. Prospects `last_communication` Data column (untyped text).
6. Relative time strings unchanged.
7. Anonymous portal Display Calendar not inferred.

---

## 17. Deferred Business Calendar work

- ~~Sales Pipeline Analytics Monthly/Quarterly → `BusinessPeriodEngine` (5A-3)~~ **done** — see [`CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md`](CRM_SALES_PIPELINE_BUSINESS_CALENDAR.md)
- Customer Acquisition Monthly (Selling, CRM-adjacent) — later slice
- Dashboard chart business-period axes

CRM Display remains independent of those.

---

## 18. Testing matrix

Module: `persian_calendar.jalali_support.test_crm_display_calendar`

| Area | Coverage |
|------|----------|
| Form Date / Datetime meta | Inventory asserts |
| Input round-trip (storage) | Normalizer coerce Farvardin 1 / Esfand 30 / Datetime |
| List JS | No custom date formatters |
| Report filters | Date fieldtype |
| Pipeline BC deferred | No `crm_pipeline.py` adapter |
| Print/Jinja | `toshamshi` / `toshamsi` render |
| Display vs BC | Preference + company BC independence |
| Architecture | No `formatdate` patch; global bundle + normalizer |
| Registry | `CRM Display Calendar` = `display_covered` |

Client picker UI E2E remains Cypress / manual desk verification (existing desk
bundle tests).

---

## 19. Upgrade risks

| Risk | Level | Guidance |
|------|-------|----------|
| Upstream CRM listview adds custom date formatters | WARNING | Re-run inventory tests; prefer fixing via global helpers |
| Pipeline month labels mistaken for Display Calendar | Process | Keep 5A-3 separate |
| Someone patches `formatdate` globally | FAIL | Forbidden by architecture |
| Appointment email still Gregorian | WARNING | Document; optional template/`toshamshi` later |

`release_check` does not FAIL solely for limitation rows above.

---

## Classification legend

| Code | Meaning |
|------|---------|
| **A** | Covered globally |
| **B** | Needs CRM-specific display adapter (none in 5A-2) |
| **C** | Explicit `toshamshi` appropriate |
| **D** | Must remain Gregorian operationally (storage/scheduling) |
| **E** | Unsupported / deferred / documented limitation |
