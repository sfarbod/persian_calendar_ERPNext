# Persian Calendar 2.1.3 — Report View Export Fix

## Summary

Fixes Report View CSV/Excel export failures caused by forwarding the unsupported
`export_dates_as_jalali` request parameter into Frappe’s `DatabaseQuery.execute()`.

## Root cause

The Persian Calendar Report View `_export_query` wrapper read
`export_dates_as_jalali` but left it on `form_params`. Frappe v16 then called:

```python
ret = db_query.execute(**form_params)
```

`DatabaseQuery.execute` has a fixed signature and rejected the unexpected
keyword, raising:

```text
TypeError: DatabaseQuery.execute() got an unexpected keyword argument 'export_dates_as_jalali'
```

Desk clients often saw a secondary `BrokenPipeError` while the error handler
tried to print the traceback after the download connection closed.

Query Report exports were unaffected (they do not kwargs-spread `form_params`
into `DatabaseQuery.execute`).

## Fix

After `_read_jalali_flag(form_params)`, pop `export_dates_as_jalali` from
`form_params` before calling the stock `_export_query`. Jalali conversion hooks
and ON/OFF behavior are unchanged. Report View patch version is now **4**.

## Upgrade

```bash
bench build --app persian_calendar
bench --site <site> clear-cache
```

No migrate required. Restart workers if the Report View patch does not re-bind
to v4.

## Compatibility

| Component | Validated |
|-----------|-----------|
| Frappe | 16.54.0 |
| ERPNext | 16.53.0 |
