# Compatibility Matrix — persian_calendar 1.8.0

**Validated:** Frappe **16.28.0** · ERPNext **16.29.0** · HRMS **16.14.0** (optional) · Python **≥ 3.10**

Legend: **I** = Implemented · **D** = Deferred · **Disp** = Display only · **N/A** = Not applicable · **Reb** = Helper rebind only

| Module / Report | Doc | Display | Business Cal. | BusinessPeriodEngine | Gregorian delegate | Contracts | Diagnostics | Registry | Tests | Status |
|-----------------|-----|---------|---------------|----------------------|--------------------|-----------|-------------|----------|-------|--------|
| Calendar Providers / Engine | ARCH / SDK | — | — | Provider only | — | — | release_check | — | providers | **I** |
| BusinessPeriodEngine | business_period_engine | — | — | **Yes** | N/A | — | release_check | — | period_engine | **I** |
| Display Calendar (desk) | jalali_support | **Yes** | No | No | N/A | — | conversion_api | — | preference / normalizer | **I** |
| toshamshi / toshamsi | TOSHAMSHI | Explicit | No | No | N/A | api.*, utils.* | conversion_api | public_utility | toshamshi_api | **I** |
| Financial Statements (`get_period_list`) | business_period_engine | Labels* | **Yes** | **Yes** | **Yes** | fs.get_period_list | fs.* | implemented | patches / FS | **I** |
| Assets / Depreciation | asset_business_calendar | Disp | CalendarEngine step | No lists | **Yes** | — | hierarchies | implemented | test_assets | **I** |
| Budget | budget_business_calendar | — | **Yes** | **Yes** | **Yes** | budget.Budget.get_budget_periods | budget.* | implemented | test_budget | **I** |
| Monthly Distribution | budget_business_calendar | — | idx slots | No | **Yes** | md.* | md.* | implemented | test_monthly_distribution | **I** |
| Trends | budget_variance_trends | Labels* | **Yes** | **Yes** | **Yes** | trends.get_period_date_ranges | trends.* | implemented | test_trends | **I** |
| Budget Variance | budget_variance_trends | — | **Yes** | **Yes** | **Yes** | bvr.execute | bvr.* | implemented | test_budget_variance | **I** |
| Sales Analytics | sales_purchase_analytics | — | **Yes** | **Yes** | **Yes** | sa.Analytics.* | sa.* | implemented | test_sales_analytics | **I** |
| Purchase Analytics | sales_purchase_analytics | — | **Yes** | **Yes** | **Yes** | (shared sa.*) | sa.* | implemented | (shared) | **I** |
| Stock Analytics | stock_analytics | — | **Yes** | **Yes** | **Yes** | stk.* | stk.* | implemented | test_stock_analytics | **I** |
| Production Analytics | stock_analytics / 6B audit | — | via Stock | via Stock | **Yes** | stk.* | mfg consumers | helper_rebind | stock tests | **Reb** |
| Work Order Summary | stock_analytics / 6B | — | via Stock | via Stock | **Yes** | stk.* | mfg consumers | helper_rebind | stock tests | **Reb** |
| Job Card Summary | stock_analytics / 6B | — | via Stock | via Stock | **Yes** | stk.* | mfg consumers | helper_rebind | stock tests | **Reb** |
| DN / PR Trends | budget_variance_trends | Labels* | via Trends | via Trends | **Yes** | trends.* | trends.* | (Trends) | trends | **I** |
| CRM Display | CRM_DISPLAY_CALENDAR | **Yes** | No | No | N/A | — | — | display_covered | test_crm_display | **Disp** |
| CRM Sales Pipeline Analytics | CRM_SALES_PIPELINE_… | Filters Disp | **Yes** | **Yes** | **Yes** | spa.execute | spa.* | implemented | test_sales_pipeline | **I** |
| HRMS Display | HRMS_BUSINESS_CALENDAR | **Yes** | No | No | N/A | — | — | display_covered | VE inventory | **Disp** |
| HRMS Vehicle Expenses | HRMS_BUSINESS_CALENDAR | Date col Disp | Chart **Yes** | via FS | **Yes** | hrms.vehicle_expenses.* (optional) | VE when HRMS | implemented | test_vehicle_expenses | **I** |
| Stock / MFG Display (ledger etc.) | 6B audit | **Yes** | No | No | N/A | — | — | display_covered | — | **Disp** |
| Exponential Smoothing Forecasting | 6B audit | — | Blocked (no company) | Would use FS | Partial rebind | — | deferred list | deferred | — | **D** |
| MRP Report buckets | 6B audit | Labels | No | No | N/A | — | deferred list | deferred | — | **D** |
| HRMS Payroll / Attendance periods | HRMS_… | Partial | No | No | N/A | — | deferred list | deferred | — | **D** |
| Issue Analytics | — | — | — | — | — | — | deferred list | deferred | — | **D** |
| Customer Acquisition BC | — | — | — | — | — | — | deferred list | deferred | — | **D** |
| Subscription / Auto Repeat / Maintenance | — | — | — | — | — | — | deferred list | deferred | — | **D** |
| Trends presentation-label cleanup | — | — | — | — | — | — | deferred list | — | — | **D** |

\* Display-layer label wrappers may still affect FS/Trends presentation; business **bounds** follow Business Calendar.

---

## Framework invariants (1.8.0)

| Invariant | Status |
|-----------|--------|
| Storage Calendar always Gregorian | **Pass** |
| Display Calendar presentation only | **Pass** |
| Business Calendar from Company | **Pass** |
| Single BusinessPeriodEngine | **Pass** |
| CalendarEngine = provider resolver only | **Pass** |
| No duplicate Jalali period arithmetic in adapters | **Pass** |
| No `frappe.utils` global monkey-patches | **Pass** |
| Free-function patches via `apply_calendar_patches` | **Pass** (Asset disposal narrow exception documented) |

---

## Orphan / scaffold inventory

| Path | Role |
|------|------|
| `calendar/integrations/*.py` | All mapped in registry |
| `calendar/adapter_template.py` | Scaffold only — not imported at runtime |
| `docs/business_calendar_phases_0_2.md` | Historical phase notes — superseded by Architecture + Developer Guide |

No orphan runtime adapters detected in Phase 7 audit.

---

## Related

- Registry: `persian_calendar/calendar/registry.py`
- Contracts: `persian_calendar/calendar/contracts.py`
- Release notes: [`RELEASE_NOTES_1.8.0.md`](RELEASE_NOTES_1.8.0.md)
- Known limitations: [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)
