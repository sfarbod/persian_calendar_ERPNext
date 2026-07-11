(async function() {
  const rt = () => frappe.persian_calendar?.runtime;

  function U() {
    return window.jalaliDateUtils;
  }

  function g2j_str(value, fieldtype) {
    if (!shouldConvertToJalali()) {
      traceFmt("g2j_str skipped (Gregorian)", { value, fieldtype });
      return value;
    }
    if (!value || !U()) return value;
    traceFmt("g2j_str", { value, fieldtype });
    const ft = fieldtype === "Datetime" ? "Datetime" : "Date";
    if (U().valueToJalaliDisplay) {
      return U().valueToJalaliDisplay(value, ft);
    }
    const stripped = U().stripMicroseconds(value);
    const dateOnly = stripped.slice(0, 10);
    if (U().isLikelyJalaliISO(dateOnly) || U().isLikelyJalaliDateTime(stripped)) {
      if (U().isLikelyJalaliDateTime(stripped)) {
        const p = U().parseDateTimeParts(stripped);
        if (p) {
          return `${U().formatJalaliParts(p.y, p.m, p.d)} ${U().formatTimeHMS(p.h, p.i, p.s)}`;
        }
      }
      return dateOnly;
    }
    if (stripped.length > 10 && U().isLikelyGregorianDateTime(stripped)) {
      return U().gregorianDateTimeToJalali(stripped) || stripped;
    }
    if (!U().isLikelyGregorianISO(dateOnly)) {
      return value;
    }
    return U().gregorianToJalaliISO(dateOnly) || value;
  }

  function j2g_str(value) {
    if (!value || !U()) return value;
    const stripped = U().stripMicroseconds(value);
    if (U().coerceToGregorianDateTime) {
      const coerced = U().coerceToGregorianDateTime(stripped);
      if (coerced) {
        return coerced;
      }
    }
    if (U().isLikelyGregorianDateTime(stripped)) {
      return U().normalizeModelDateTime(stripped);
    }
    if (U().isLikelyJalaliDateTime(stripped)) {
      return U().jalaliDateTimeToGregorian(stripped) || value;
    }
    if (U().isLikelyJalaliISO(stripped.slice(0, 10))) {
      return U().jalaliToGregorianISO(stripped.slice(0, 10)) || value;
    }
    return value;
  }

  function traceFmt(fn, detail) {
    try {
      if (localStorage.getItem("persian_calendar_trace") === "1") {
        console.warn("[persian_calendar trace]", fn, detail);
      }
    } catch (e) {
      /* ignore */
    }
  }

  function shouldConvertToJalali() {
    if (rt()?.shouldConvertToJalaliSync) {
      const r = rt().shouldConvertToJalaliSync();
      traceFmt("shouldConvertToJalali", { result: r, boot: frappe.boot?.persian_calendar });
      return r;
    }
    if (rt()?.getEffectiveCalendarModeSync) {
      return rt().getEffectiveCalendarModeSync() === "Jalali";
    }
    return rt()?.getEffectiveCalendarModeSync?.() === "Jalali";
  }

  const dt = frappe.datetime;
  const orig_str_to_user = dt.str_to_user?.bind(dt);
  const orig_str_to_user_with_default = dt.str_to_user_with_default?.bind(dt);
  const orig_user_to_str = dt.user_to_str?.bind(dt);
  const orig_format_date = dt.format_date?.bind(dt);
  const orig_format_datetime = dt.format_datetime?.bind(dt);

  function isTimeOnlyString(value) {
    return /^\d{1,2}:\d{2}(:\d{2})?$/.test(String(value || "").trim());
  }

  function looksLikeCsvGregorianDateTime(value) {
    const s = String(value || "").trim();
    return /^\d{1,2}\/\d{1,2}\/\d{4}(\s+\d{1,2}:\d{2}(:\d{2})?)?/.test(s);
  }

  function looksLikeNonIsoGregorianDisplay(value) {
    const s = String(value || "").trim();
    if (!s || looksLikeCsvGregorianDateTime(s)) {
      return !!s && looksLikeCsvGregorianDateTime(s);
    }
    if (/^\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2}(:\d{2})?)?$/.test(s)) {
      return false;
    }
    return /^\d{1,2}-\d{1,2}-\d{4}(\s+\d{1,2}:\d{2}(:\d{2})?)?$/.test(s);
  }

  function coerceGregorianDisplayValue(value, fieldtype) {
    const utils = U();
    if (!value || !utils?.coerceToGregorianDateTime) {
      return value;
    }
    const s = String(value).trim();
    if (!looksLikeCsvGregorianDateTime(s) && !looksLikeNonIsoGregorianDisplay(s)) {
      if (utils.isLikelyGregorianISO?.(s.slice(0, 10)) || utils.isLikelyGregorianDateTime?.(s)) {
        return fieldtype === "Date" ? s.slice(0, 10) : utils.normalizeModelDateTime?.(s) || s;
      }
      return value;
    }
    const coerced = utils.coerceToGregorianDateTime(s);
    if (!coerced) {
      return value;
    }
    return fieldtype === "Date" ? coerced.slice(0, 10) : coerced;
  }

  function coerceImportValueForDisplay(value, only_date) {
    return coerceGregorianDisplayValue(value, only_date ? "Date" : "Datetime");
  }

  if (orig_str_to_user) {
    dt.str_to_user = function (value, only_time = false, only_date = false) {
      if (!value) return value;
      if (isTimeOnlyString(value)) {
        return orig_str_to_user(value, true);
      }
      if (!shouldConvertToJalali()) {
        if (!only_time) {
          value = coerceImportValueForDisplay(value, only_date);
        }
        return orig_str_to_user(value, only_time, only_date);
      }
      if (!U()) {
        return orig_str_to_user(value);
      }
      const stripped = U().stripMicroseconds(value);
      const is_datetime = stripped.length > 10 && stripped.includes(" ");
      if (is_datetime) {
        return g2j_str(stripped);
      }
      return g2j_str(stripped);
    };
  }
  if (orig_str_to_user_with_default) {
    dt.str_to_user_with_default = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_str_to_user_with_default(coerceImportValueForDisplay(value, false));
      }
      return dt.str_to_user(value);
    };
  }
  if (orig_user_to_str) {
    dt.user_to_str = function (value, only_time = false) {
      if (!value) return value;
      if (only_time || isTimeOnlyString(value)) {
        return orig_user_to_str(value, true);
      }
      if (!shouldConvertToJalali()) {
        return orig_user_to_str(value, only_time);
      }
      if (!U()) {
        return orig_user_to_str(value);
      }
      return j2g_str(value);
    };
  }
  if (orig_format_date) {
    dt.format_date = function (date_str) {
      if (!shouldConvertToJalali()) {
        return orig_format_date(coerceGregorianDisplayValue(date_str, "Date"));
      }
      return g2j_str(date_str);
    };
  }
  if (orig_format_datetime) {
    dt.format_datetime = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_format_datetime(coerceGregorianDisplayValue(value, "Datetime"));
      }
      return g2j_str(value);
    };
  }

  // Frappe resolves formatters via frappe.form.get_formatter(fieldtype) using PascalCase
  // keys (Date, Datetime). Lowercase .date / .datetime are never invoked from list view.
  if (!frappe.form.formatters._pcJalaliPatched) {
    const orig_date_formatter = frappe.form.formatters.Date;
    const orig_datetime_formatter = frappe.form.formatters.Datetime;

    frappe.form.formatters.Date = function (value, df, options, doc) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        const safe = coerceGregorianDisplayValue(value, "Date");
        if (orig_date_formatter) {
          return orig_date_formatter(safe, df, options, doc);
        }
        return safe;
      }
      return g2j_str(value, "Date");
    };

    frappe.form.formatters.Datetime = function (value, df, options, doc) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        const safe = coerceGregorianDisplayValue(value, "Datetime");
        traceFmt("form.formatters.Datetime (Gregorian)", { in: value, safe });
        if (orig_datetime_formatter) {
          return orig_datetime_formatter(safe, df, options, doc);
        }
        return safe;
      }
      return g2j_str(value, "Datetime");
    };

    frappe.form.formatters._pcJalaliPatched = true;
  }

  if (frappe.format && !frappe.format._pcCoercePatched) {
    const origFrappeFormat = frappe.format;
    frappe.format = function (value, df, options, doc) {
      if (df?.fieldtype === "Datetime") {
        value = coerceGregorianDisplayValue(value, "Datetime");
      } else if (df?.fieldtype === "Date") {
        value = coerceGregorianDisplayValue(value, "Date");
      }
      return origFrappeFormat(value, df, options, doc);
    };
    frappe.format._pcCoercePatched = true;
  }

  if (rt()?.fetchCalendarSettings) {
    rt()
      .fetchCalendarSettings()
      .catch(function () {
        /* keep boot defaults */
      });
  }
})();
