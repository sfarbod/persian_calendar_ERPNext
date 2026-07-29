# Business Calendar — Public API Reference (Phase 4b)

Import from **`persian_calendar.api`**.

Symbols not listed here are internal unless documented otherwise.

---

## Core calendar

| Symbol | Role |
|--------|------|
| `CalendarEngine` | Provider façade (`gregorian`, `jalali`, `for_company`) |
| `CalendarProvider` | Provider ABC |
| `BusinessPeriod` | Immutable period DTO (Gregorian bounds + stable `key`) |
| `BusinessPeriodEngine` | Canonical period-list generator |
| `format_period_label` | Presentation labels only |

## Resolve

| Symbol | Role |
|--------|------|
| `BUSINESS_CALENDAR_GREGORIAN` / `JALALI` | Constants |
| `VALID_BUSINESS_CALENDARS` | Allowed names |
| `get_business_calendar_for_company` | Company → BC (never Display) |
| `normalize_business_calendar` | Safe normalize |
| `clear_business_calendar_cache` | Tests / Company save |

## Patches

| Symbol | Role |
|--------|------|
| `apply_calendar_patches` | Central lifecycle |
| `PatchStatus` | Enum |
| `get_patch_state` | Diagnostics |

## Compatibility / diagnostics

| Symbol | Role |
|--------|------|
| `detect_compatibility` | Version matrix |
| `CompatibilityStatus` | Enum |
| `VALIDATED_FRAPPE` / `VALIDATED_ERPNEXT` | Matrix anchors |
| `run_diagnostics` | Full report (`diagnostics.run`) |
| `release_check` | PASS / WARNING / FAIL |
| `report_as_dict` | Machine payload |
| `ReleaseLevel` | Enum |

## Registry

| Symbol | Role |
|--------|------|
| `INTEGRATED_MODULES` | Tuple of `IntegratedModule` |
| `implemented_modules` | Filter helper |
| `registry_as_dict` | Serialisable inventory |

## Adapter helpers

| Symbol | Role |
|--------|------|
| `should_use_jalali_engine` | BC + range gate |
| `resolve_business_calendar` | Thin BC resolve |
| `snap_jalali_range_start` | Floor before generate |
| `build_jalali_periods` | Snap + engine |
| `period_bounds_index` / `lookup_period_key` | Inclusive key map |
| `report_locale` | Label locale only |

## Patch SDK

| Symbol | Role |
|--------|------|
| `capture_original` | Capture-once stock callable |
| `install_adapter` | Module attribute replace |
| `rebind_consumers` | Identity rebind |

## Display conversion (Phase 5A-1)

| Symbol | Role |
|--------|------|
| `toshamshi` | Canonical Jalali display conversion (legacy public name) |
| `toshamsi` | Identity alias of `toshamshi` (correct spelling) |

Implementation: `persian_calendar.utils.jalali` (single algorithm).  
See [`TOSHAMSHI.md`](TOSHAMSHI.md). These are **not** Business Calendar period APIs.

CRM Desk Date/Datetime presentation uses the global Display Calendar (see
[`CRM_DISPLAY_CALENDAR.md`](CRM_DISPLAY_CALENDAR.md)), not these helpers, unless
a Print/email template explicitly calls them.

---

See `docs/SDK.md` for extension workflow.
