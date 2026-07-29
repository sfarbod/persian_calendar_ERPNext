# `toshamshi` — Canonical Jalali Conversion API

**Phase:** 5A-1  
**Status:** Public, stable, backward-compatible  

This document describes the **display/conversion** helper used in Print Formats,
Jinja, PDF HTML, emails, and Python callers. It is **not** a Business Calendar
period engine.

---

## 1. Purpose

Convert a **Gregorian** (or already-Jalali) date/datetime value to a Jalali
**display string** for print, PDF, email, and custom scripts.

Storage remains Gregorian/ISO. Do **not** use this function for:

- SQL / report period boundaries
- Business period grouping (`BusinessPeriodEngine`)
- Company Business Calendar resolution
- User Display Calendar preference (Desk formatters)

---

## 2. Canonical implementation path

```text
persian_calendar.utils.jalali.toshamshi
```

Single conversion algorithm. No copies.

---

## 3. Public API path

```python
from persian_calendar.api import toshamshi
from persian_calendar.api import toshamsi   # identity alias
```

---

## 4. Legacy import path

```python
from persian_calendar.utils.jalali import toshamshi
from persian_calendar.utils.jalali import toshamsi  # same alias
```

Also re-exported from `persian_calendar.utils`.

Existing callers (including `erpnext_extensions` GL print) keep working without changes.

---

## 5. `toshamsi` alias

```python
toshamsi = toshamshi   # identity: toshamsi is toshamshi
```

| Name | Role |
|------|------|
| `toshamshi` | **Canonical legacy public name** (do not deprecate) |
| `toshamsi` | Correctly spelled **compatibility alias** (same callable) |

There is only one implementation.

---

## 6. Signature

```python
def toshamshi(
    value,
    include_time: bool = False,
    format: str = "YYYY-MM-DD",
    persian_digits: bool = False,
) -> str:
```

Identical for `toshamsi`. Positional and keyword calls are supported.

---

## 7. Accepted input types

| Input | Behaviour |
|-------|-----------|
| `None` | `""` |
| `""` / whitespace-only | `""` |
| `datetime.date` | Convert Gregorian → Jalali |
| `datetime.datetime` (naive or aware) | Convert using **wall-clock components** (see Timezone) |
| ISO-like string `YYYY-MM-DD` | Parsed; Gregorian if year ≥ 1700 |
| ISO-like datetime `YYYY-MM-DD HH:mm:ss` | Microseconds stripped; optional time in output |
| Strings with year **1200–1600** | Treated as **already Jalali** (pass-through format) |
| Unparseable / invalid objects | `""` |

Frappe Date/Datetime field values that arrive as strings or Python date/datetime
are supported the same way.

---

## 8. Return type

Always `str`. Never returns a date/datetime object.

---

## 9. Default format

`"YYYY-MM-DD"` (Moment-style token replacement, **not** `strftime`).

Supported tokens (custom replace):

| Token | Meaning |
|-------|---------|
| `YYYY` | Jalali year (4 digits) |
| `MM` | Jalali month (2 digits) |
| `DD` | Jalali day (2 digits) |
| `HH` / `mm` / `ss` | Hour / minute / second when `include_time` and present in `format` |

If `include_time` is true and the format has no `HH`/`mm`/`ss`, time is appended
as ` HH:mm:ss`.

Representative formats in the wild: `YYYY-MM-DD`, `YYYY/MM/DD`.

---

## 10. `include_time`

- Default `False`: date-only string.
- `True`: append time when the source has a time component, **or** the input is a
  `datetime` instance (including midnight).

---

## 11. Persian digits

- Default `False`: ASCII `0–9`.
- `True`: map digits to `۰–۹` via `to_persian_digits`.

---

## 12. Null behaviour

`None` and empty / whitespace strings → `""`.

---

## 13. Invalid-input behaviour

Unparseable strings and non-date objects → `""` (no raise, no log).

**Technical debt (preserved, not “fixed” in 5A-1):**

- Some out-of-range month/day strings (e.g. `2026-13-40`) may **overflow** through
  `jdatetime` instead of returning `""`.
- Years **1601–1699** fall outside the Jalali heuristic and are treated as Gregorian.

---

## 14. Already-Jalali year behaviour

Years **1200–1600** are formatted as Jalali without Gregorian conversion
(pass-through of Y/M/D parts).

---

## 15. Timezone behaviour

- **No** conversion to site timezone.
- **No** UTC shift.
- Aware `datetime` inputs use `.year/.month/.day/.hour/.minute/.second` as given
  (wall clock of that aware value’s calendar fields).
- Date-only inputs never shift by timezone.
- Print/PDF output does **not** depend on session timezone for this helper.

---

## 16. Display Calendar independence

`toshamshi` / `toshamsi` **do not** read User Display Calendar or Jalali Settings.
Changing Display Calendar does not change explicit conversion results.

Desk form/list formatting uses a separate Display Calendar JS/Python path.

---

## 17. Business Calendar independence

Does **not** import or call `BusinessPeriodEngine`, Company Business Calendar, or
analytics adapters. Lightweight display only.

---

## 18. Python examples

```python
from persian_calendar.api import toshamshi, toshamsi

toshamshi("2026-05-13")
# '1405-02-23'

toshamshi("2026-03-18 13:36:04", include_time=True)
# '1404-12-27 13:36:04'

toshamshi("2026-05-13", format="YYYY/MM/DD")
# '1405/02/23'

toshamshi("1990-01-02", persian_digits=True)
# '۱۳۶۸-۱۰-۱۲'

assert toshamsi("2026-05-13") == toshamshi("2026-05-13")
assert toshamsi is toshamshi
```

---

## 19. Jinja examples

Registered via `hooks.py`:

```python
jinja = {"methods": ["persian_calendar.utils.jalali"]}
```

Frappe loads **all public functions** from that module into the Jinja environment
(Print Formats, PDF HTML, email/notification templates that use the same registry).

```jinja
{{ toshamshi(doc.posting_date) }}
{{ toshamsi(doc.posting_date) }}
{{ toshamshi(doc.creation, include_time=True) }}
{{ toshamshi(doc.posting_date, format="YYYY/MM/DD") }}
{{ toshamshi(doc.birthdate, persian_digits=True) }}
```

---

## 20. Print Format examples

```jinja
<p>تاریخ: {{ toshamshi(doc.posting_date, format="YYYY/MM/DD") }}</p>
```

Legacy name `toshamshi` must keep working; `toshamsi` is available as an alias.

---

## 21. Email / Notification examples

```jinja
موعد: {{ toshamshi(doc.cheque_due_date) }}
موعد: {{ toshamsi(cheque_due_date) }}
```

(`persian_calendar` may also expose doc fields at top level for notifications —
see `jalali_support/template_hooks.py`.)

Brace templates (non-Jinja) still use `{toshamshi(field)}` only; they are a
separate renderer (`render_brace_template`).

---

## 22. Compatibility notes

- Do **not** rename or remove `toshamshi`.
- `erpnext_extensions` may continue importing `persian_calendar.utils.jalali.toshamshi`.
- Public `persian_calendar.api` re-exports the **same** callable (no second algorithm).
- Hook path unchanged in 5A-1.

---

## 23. Known limitations

- Not a full i18n locale formatter (no month names).
- Custom token set only (`YYYY`/`MM`/`DD`/`HH`/`mm`/`ss`).
- Invalid calendar overflow debt (above).
- Brace templates do not expand `{toshamsi(...)}` (Jinja does).

---

## 24. Migration guidance

| Old | New (optional) |
|-----|----------------|
| `from persian_calendar.utils.jalali import toshamshi` | Still valid — preferred for Print-era code |
| — | `from persian_calendar.api import toshamshi` for new app code |
| Typo `toshamsi` in templates | Now works (alias) |

No migration required for existing Print Formats.

---

## Related

- Audit: [`CRM_JALALI_TOSHAMSHI_AUDIT.md`](CRM_JALALI_TOSHAMSHI_AUDIT.md)
- Print helper notes: [`print_format_jalali_helper.md`](print_format_jalali_helper.md)
- Template syntax: [`jalali_template_syntax.md`](jalali_template_syntax.md)
- API reference: [`API_REFERENCE.md`](API_REFERENCE.md)
