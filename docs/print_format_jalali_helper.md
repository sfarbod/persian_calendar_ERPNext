# Jalali print format helpers (`toshamshi`)

The **persian_calendar** app registers Jinja methods for ERPNext/Frappe **Print Formats** so Gregorian field values can be shown in Jalali (Shamsi) on PDFs and print views.

## Setup

- Dependency: `jdatetime` (installed with the app).
- After install or code changes: `bench --site <site> clear-cache`.

## Usage in Print Format HTML

```jinja
{{ toshamshi(doc.date_of_birth) }}
{{ toshamshi(doc.posting_date) }}
{{ toshamshi(doc.creation, include_time=True) }}
{{ toshamshi(doc.expected_start_date, include_time=True) }}
{{ toshamshi(doc.birthdate, persian_digits=True) }}
{{ to_persian_digits("1404-12-28") }}
```

## `toshamshi(value, include_time=False, format="YYYY-MM-DD", persian_digits=False)`

| Argument | Description |
|----------|-------------|
| `value` | `date`, `datetime`, or string (`YYYY-MM-DD` or `YYYY-MM-DD HH:mm:ss`, optional microseconds) |
| `include_time` | Include `HH:mm:ss` when the source has a time part |
| `format` | Output template: `YYYY`, `MM`, `DD`, and optionally `HH`, `mm`, `ss` |
| `persian_digits` | Use ۰–۹ instead of 0–9 |

**Behaviour**

- Empty / `None` → `""`
- Gregorian values → converted with `jdatetime` (no timezone shift; uses calendar date/time parts as stored)
- Values that already look Jalali (year 1200–1600) → returned unchanged (normalized formatting)
- Microseconds in strings are stripped

**Examples**

| Input | Call | Output |
|-------|------|--------|
| `"1990-01-02"` | `toshamshi(...)` | `1368-10-12` |
| `"2026-05-13"` | `toshamshi(...)` | `1405-02-23` |
| `"2026-03-18 13:36:04"` | `toshamshi(...)` | `1404-12-27` |
| `"2026-03-18 13:36:04"` | `toshamshi(..., include_time=True)` | `1404-12-27 13:36:04` |

## `to_persian_digits(value)`

Replaces ASCII digits with Persian digits. Empty → `""`.

## Bench console check

```python
bench --site <site> console
```

```python
from persian_calendar.utils.jalali import toshamshi, to_persian_digits

toshamshi("1990-01-02")
toshamshi("2026-05-13")
toshamshi("2026-03-18 13:36:04", include_time=True)
toshamshi("1404-12-28")
to_persian_digits("1404-12-28 13:36:04")
```

## Unit tests

From the app directory:

```bash
python -m unittest persian_calendar.utils.test_jalali
```

Or on the bench:

```bash
bench --site <site> run-tests --app persian_calendar
```

## Brace templates (`{field}` / `{toshamshi(field)}`)

For **User Remark**, **PDC journal narration**, **title field options**, and similar `str.format` templates (not Jinja), use:

```
{toshamshi(cheque_due_date)}
```

See [jalali_template_syntax.md](./jalali_template_syntax.md) for where each syntax applies.

## Implementation

- Module: `persian_calendar/utils/jalali.py`
- Hook: `hooks.py` → `jinja.methods` includes this module so all public functions are available in print Jinja.
- Brace templates: `persian_calendar/utils/template_format.py` + `jalali_support/template_hooks.py`
