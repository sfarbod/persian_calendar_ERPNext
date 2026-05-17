# Jalali date syntax: Print Formats vs brace templates

## Where each syntax works

| Context | Syntax | Engine |
|---------|--------|--------|
| **Print Format** (PDF/HTML) | `{{ toshamshi(doc.field) }}` | Full Jinja (`hooks.py` → `jinja.methods`) |
| **Email Notification** (message/subject) | `{{ toshamshi(doc.field) }}` or `{{ toshamshi(field) }}`* | Full Jinja |
| **PDC / JE remark templates** (erpnext_extensions) | `{field}` and `{toshamshi(field)}` | `str.format_map` via `render_brace_template` |
| **Document title** (`title` field options/default) | `{field}` and `{toshamshi(field)}` | Same brace renderer |
| **Assignment / timeline / Comment** | Usually fixed translated strings in code | Not user templates unless custom app uses brace templates |

\*After `persian_calendar` loads, Notification context also exposes top-level field names from `doc` so `{{ toshamshi(cheque_due_date) }}` works without `doc.`.

## Brace template examples (User Remark / JE narration / PDC settings)

```
ثبت چک دریافتنی {cheque_no} — {party}
{toshamshi(cheque_due_date)}
```

With time:

```
{toshamshi(creation, include_time=True)}
```

Persian digits:

```
{toshamshi(cheque_due_date, persian_digits=True)}
```

Rules:

- Normal `{cheque_no}` still works (unchanged).
- `{toshamshi(fieldname)}` reads `fieldname` from the same context dict as other placeholders.
- No `eval` / no arbitrary code — only registered `toshamshi` helper.
- Gregorian values in the database are unchanged; output is display-only.

## Print Format examples (Jinja)

```jinja
{{ toshamshi(doc.date_of_birth) }}
{{ toshamshi(doc.posting_date) }}
{{ toshamshi(doc.creation, include_time=True) }}
{{ toshamshi(doc.cheque_due_date, persian_digits=True) }}
```

See also: [print_format_jalali_helper.md](./print_format_jalali_helper.md)

## Implementation

- `persian_calendar.utils.jalali.toshamshi` — conversion
- `persian_calendar.utils.template_format.render_brace_template` — `{field}` + `{toshamshi(...)}`
- `persian_calendar.jalali_support.template_hooks.apply_template_patches` — patches title field, notifications, erpnext_extensions `render_description_template`

## Tests

```bash
cd apps/persian_calendar
../env/bin/python -m unittest persian_calendar.utils.test_jalali persian_calendar.utils.test_template_format -v
```

## Bench console

```python
from persian_calendar.utils.template_format import render_brace_template

render_brace_template(
    "چک {cheque_no} — {party}\n{toshamshi(cheque_due_date)}",
    {"cheque_no": "2323211", "party": "آلاشت فارمد", "cheque_due_date": "2026-05-13"},
)
```
