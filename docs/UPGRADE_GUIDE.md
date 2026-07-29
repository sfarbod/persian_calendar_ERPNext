# Business Calendar — ERPNext Upgrade Guide

How to validate the Business Calendar Framework after upgrading Frappe or ERPNext.

This guide is **upgrade safety only**. It does not describe new calendar features.

Validated matrix (Phase 3 Final / Phase 4a):

| Component | Version |
|-----------|---------|
| ERPNext | **16.29.0** |
| Frappe | **16.28.0** |
| `persian_calendar` | see `persian_calendar.__version__` |

---

## 1. Quick validation after an upgrade

```bash
cd /path/to/frappe-bench

# Apply patches in this process, then print the full diagnostic report
bench --site <site> execute persian_calendar.calendar.diagnostics.run

# Machine-oriented PASS / WARNING / FAIL
bench --site <site> execute persian_calendar.calendar.diagnostics.release_check
```

Interpret the overall line:

| Result | Meaning |
|--------|---------|
| **PASS** | Exact or acceptable state: contracts, registry, and import graph OK |
| **WARNING** | Usually version matrix is `PARTIALLY_VERIFIED` or `UNKNOWN_VERSION` — re-test before production |
| **FAIL** | Signature drift, missing targets, failed rebind, or patches not applied — **do not deploy** |

---

## 2. Compatibility statuses

From `persian_calendar.calendar.compatibility.detect_compatibility()`:

| Status | Meaning |
|--------|---------|
| `SUPPORTED` | Exact match with the validated Frappe/ERPNext versions |
| `PARTIALLY_VERIFIED` | Same major (16.x) but not the exact validated patch versions |
| `UNKNOWN_VERSION` | Different major (or unparseable) — treat as high risk |
| `UNAVAILABLE` | Frappe/ERPNext not importable in this process |

Unknown / partial versions **emit warnings**; they do not silently claim safety.

---

## 3. PatchStatus

From `apply_calendar_patches()` / diagnostics:

| Status | Meaning | Action |
|--------|---------|--------|
| `applied` | Capture + replace + known rebinds OK | Continue testing |
| `source_unavailable` | ERPNext module not importable yet | Retry after apps load |
| `partial_rebind` | A known loaded consumer still holds the stock function | Fix import/rebind; fail release |
| `failed` | Unsafe capture state (e.g. adapter present, no original) | Restart process; inspect hook order |
| `not_attempted` | Applicator never ran | Call `apply_calendar_patches()` |

Console / `bench execute` must call the applicator (or `diagnostics.run`, which applies patches) explicitly. Desk/request paths use `before_request`.

---

## 4. Contract tests

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app persian_calendar \
  --module persian_calendar.calendar.test_contracts
```

Contracts live in `persian_calendar/calendar/contracts.py` and lock:

- module path
- callable / class method existence
- parameter names and defaults
- selected return annotations
- Budget / Monthly Distribution / Analytics class presence

If ERPNext renames a parameter or changes arity, the test **fails with the contract id and recovery guidance**.

Also run the full Business Calendar suite (~211 + Phase 4a tests) before production.

---

## 5. Recovering from signature changes

1. Read the failing contract id (e.g. `stk.get_period_date_ranges`).
2. Open the corresponding ERPNext source and the adapter under `persian_calendar/calendar/integrations/`.
3. Update the adapter to the new signature **without** changing BusinessPeriodEngine semantics.
4. Update the `CallableContract` entry in `contracts.py` to the new expected shape.
5. Update consumer registries in `patches.py` if import paths changed.
6. Re-run `diagnostics.release_check` and `test_contracts`.
7. Document the new validated ERPNext version in Architecture / this guide when the matrix is intentionally advanced.

Do **not** patch `frappe.utils`. Do **not** merge Trends and Stock same-named helpers into one registry.

---

## 6. Production deployment checklist

- [ ] `diagnostics.release_check` is `PASS` (or `WARNING` with documented acceptance)
- [ ] `test_contracts` green
- [ ] Full `persian_calendar.calendar*` framework suites green
- [ ] Spot-check Gregorian company: FS / Trends / Sales / Stock unchanged vs stock ERPNext
- [ ] Spot-check Jalali company: Monthly Farvardin–Esfand + leap Esfand
- [ ] Confirm `hooks.py` still registers `before_request_calendar_bootstrap`
- [ ] Confirm Stock `round_down_to_nearest_frequency` is **not** replaced
- [ ] Confirm Purchase Analytics still shares `sales_analytics.Analytics`
- [ ] No new CRM / HRMS / MRP scope mixed into this upgrade PR

---

## 7. CI readiness

No in-repo GitHub Actions existed at Phase 4a authoring time. A workflow template is provided at:

`.github/workflows/calendar-upgrade-safety.yml`

Wire it to a bench image or self-hosted runner that can execute:

```text
persian_calendar.calendar.diagnostics.release_check
persian_calendar.calendar.test_contracts
```

Treat `FAIL` as a hard CI failure. Treat `WARNING` as optional fail (recommended for release branches).

---

## Related documents

| Doc | Role |
|-----|------|
| [`ARCHITECTURE_BUSINESS_CALENDAR.md`](ARCHITECTURE_BUSINESS_CALENDAR.md) | Frozen architecture + upgrade checklist |
| [`BUSINESS_CALENDAR_PHASE3_RELEASE.md`](BUSINESS_CALENDAR_PHASE3_RELEASE.md) | Phase 3 readiness |
| [`BUSINESS_CALENDAR_DEVELOPER_GUIDE.md`](BUSINESS_CALENDAR_DEVELOPER_GUIDE.md) | Extension recipes |
| [`SDK.md`](SDK.md) | Phase 4b public API / adapter workflow |
| [`API_REFERENCE.md`](API_REFERENCE.md) | `persian_calendar.api` symbols |
| [`TOSHAMSHI.md`](TOSHAMSHI.md) | Canonical Jalali conversion (`toshamshi` / `toshamsi`) |

### Print Format conversion guard (Phase 5A-1)

`release_check` includes a **conversion_api** check. Missing `toshamshi` /
`toshamsi` (or a broken Jinja module hook) is a **FAIL** because Print Formats
depend on them. This is independent of Business Calendar patch health.
