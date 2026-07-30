# Manufacturing + Stock Business Calendar Audit (Phase 6B)

**Status:** Audit complete — **no new adapters**  
**Platform:** Frappe **16.28.0** · ERPNext **16.29.0**  
**Policy:** Document findings only unless a report genuinely needs BusinessPeriodEngine and is not already deferred.

---

## 1. Verdict

| Question | Answer |
|----------|--------|
| Remaining MFG/Stock reports with SQL `MONTH()` / `QUARTER()` / `DATE_FORMAT()`? | **None** |
| Remaining independent period engines outside Stock/Trends/FS? | **None in-scope** |
| New Phase 6B implementations? | **None** |
| Gaps? | **Forecast** (Exponential Smoothing — company not passed) and **MRP bucket view** — both already **deferred** |

All non-deferred Manufacturing/Stock **business-period analytics** reports are already covered by prior phases.

---

## 2. Manufacturing — 17 Script Reports

| Report | Path | Period logic | Company | Classification |
|--------|------|--------------|---------|----------------|
| BOM Explorer | `bom_explorer` | — | — | Not applicable |
| BOM Operations Time | `bom_operations_time` | — | — | Not applicable |
| BOM Stock Analysis | `bom_stock_analysis` | — | — | Display / snapshot |
| BOM Variance | `bom_variance_report` | — | — | Display / variance |
| Cost of Poor Quality | `cost_of_poor_quality_report` | Date range filter | Yes | Display only |
| Downtime Analysis | `downtime_analysis` | Chart by workstation (not months) | — | Not applicable |
| **Exponential Smoothing Forecasting** | `exponential_smoothing_forecasting` | `get_period_list` Monthly–Yearly | Yes (reqd) | **Needs BC → Deferred (Forecast 3e)** |
| **Job Card Summary** | `job_card_summary` | Stock `get_period*` | Yes | **Implemented** (3d-2 rebind) |
| **Material Requirements Planning** | `material_requirements_planning_report` | Daily/Weekly/Monthly **planning buckets** (`get_first_day` / `add_months`) | Yes | **Deferred** (MRP/MPS) |
| Process Loss | `process_loss_report` | Date filters | Yes | Display only |
| **Production Analytics** | `production_analytics` | Stock `get_period*` | Yes | **Implemented** (3d-2 rebind) |
| Production Plan Summary | `production_plan_summary` | — | — | Not applicable |
| Production Planning Report | `production_planning_report` | Planning filters | Yes | Not applicable / planning |
| Quality Inspection Summary | `quality_inspection_summary` | Status chart | — | Not applicable |
| Work Order Consumed Materials | `work_order_consumed_materials` | — | Yes | Display only |
| Work Order Stock Report | `work_order_stock_report` | — | — | Display / snapshot |
| **Work Order Summary** | `work_order_summary` | Stock `get_period*` | Yes | **Implemented** (3d-2 rebind) |

### Already covered (manufacturing)

Identity-rebind via `STOCK_ANALYTICS_PERIOD_CONSUMERS`:

- `production_analytics` → `get_period`, `get_period_columns`, `get_period_date_ranges`
- `work_order_summary` → `get_period`, `get_period_date_ranges`
- `job_card_summary` → `get_period`, `get_period_date_ranges`

### Deferred detail — Exponential Smoothing Forecasting

```text
get_period_list(from_date, to_date, from_date, to_date, "Date Range", periodicity,
                ignore_fiscal_year=True)
# company NOT passed → FS Business Calendar always Gregorian
```

- Module is already listed in `GET_PERIOD_LIST_CONSUMERS` (Gregorian path / rebind OK).
- Jalali Company Business Calendar cannot activate until `company=filters.company` is passed (same pattern as Vehicle Expenses).
- Remains **Forecast Phase 3e** — not implemented in 6B.

### Deferred detail — MRP Report

`get_dates()` builds Daily / Weekly / Monthly **planning** columns with Gregorian `get_first_day` / `add_months` / `formatdate(..., "MMM YYYY")`. This is MPS/MRP horizon bucketing, not FS-style accounting period lists. Remains **MRP / MPS deferred**.

---

## 3. Stock — 42 Script Reports

### Period / analytics consumers

| Report | Period mechanism | Classification |
|--------|------------------|----------------|
| **Stock Analytics** | Own `get_period_date_ranges` / `get_period` / `get_period_columns` | **Implemented** (3d-2) |
| **Delivery Note Trends** | `erpnext.controllers.trends` | **Implemented** (Trends 3c) |
| **Purchase Receipt Trends** | `erpnext.controllers.trends` | **Implemented** (Trends 3c) |
| warehouse_wise_item_balance_age_and_value | Imports Stock Analytics **data** helpers only (`get_items`, SLE, item details) | Display / balance — **not** a period consumer |

### SQL / formatter scan (entire `erpnext/stock` + `erpnext/manufacturing`)

| Pattern | Hits in reports |
|---------|-----------------|
| `MONTH(` / `QUARTER(` / `DATE_FORMAT` | **0** |
| `get_period_list` | Forecasting only (manufacturing) |
| `get_period_date_ranges` | Stock Analytics + 3 MFG rebind consumers |

### Display-only / not applicable (Stock)

Ledger, balance, ageing, batch/serial, projected qty, shortage, landed cost, COGS by item group, incorrect-* diagnostics, BOM search, reserved stock, item prices, etc. — Date filters/columns only; inherit Display Calendar. No Monthly/Quarterly business-period engines.

---

## 4. Coverage math (Manufacturing + Stock)

**Business-period analytics reports** (period lists / Trends / Stock helpers):

| # | Report | Status |
|---|--------|--------|
| 1 | Stock Analytics | Implemented |
| 2 | Production Analytics | Implemented (rebind) |
| 3 | Work Order Summary | Implemented (rebind) |
| 4 | Job Card Summary | Implemented (rebind) |
| 5 | Delivery Note Trends | Implemented (Trends) |
| 6 | Purchase Receipt Trends | Implemented (Trends) |
| 7 | Exponential Smoothing Forecasting | Deferred (Forecast 3e) |
| 8 | MRP Report (bucket view) | Deferred (MRP/MPS) |

| Metric | Value |
|--------|------:|
| Non-deferred covered | **6 / 6 = 100%** |
| Including deferred candidates | **6 / 8 = 75%** |
| New adapters in Phase 6B | **0** |

---

## 5. Contracts / diagnostics / registry

No new contracts. Existing:

- `stk.*` + manufacturing consumer identity checks
- Trends consumers include stock Trends reports
- `GET_PERIOD_LIST_CONSUMERS` includes Exponential Smoothing (rebind only)

Registry notes updated for Phase 6B audit; MRP / Forecast remain `deferred`.

---

## 6. Explicit non-goals (unchanged)

- Speculative Jalali weeks for Stock Weekly
- Redesigning MRP/MPS planning calendars
- Forecast model redesign (Phase 3e)
- Trends presentation-label cleanup (Presentation Layer)

---

## Related

- [`stock_analytics.md`](stock_analytics.md) — Phase 3d-2
- [`budget_variance_trends.md`](budget_variance_trends.md) — Trends
- [`ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) — Compatibility Matrix
