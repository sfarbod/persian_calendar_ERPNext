(async function() {
  let jalaliEnabled = false;

  try {
    const result = await frappe.call({ method: "persian_calendar.jalali_support.api.is_jalali_enabled" });
    jalaliEnabled = result && result.message;
  } catch (e) {
    jalaliEnabled = false;
  }

  if (!jalaliEnabled) {
    return;
  }

  let EFFECTIVE_CALENDAR = {
    display_calendar: "Jalali",
    week_start: 6,
    week_end: 5,
  };

  try {
    const r = await frappe.call({ method: "persian_calendar.jalali_support.api.get_effective_calendar" });
    if (r && r.message) {
      EFFECTIVE_CALENDAR = r.message;
    }
  } catch (e) {
    /* keep defaults */
  }

  function U() {
    return window.jalaliDateUtils;
  }

  function g2j_str(value, fieldtype) {
    if (!value || !U()) return value;
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

  function shouldConvertToJalali() {
    return EFFECTIVE_CALENDAR && EFFECTIVE_CALENDAR.display_calendar === "Jalali";
  }

  const dt = frappe.datetime;
  const orig_str_to_user = dt.str_to_user?.bind(dt);
  const orig_str_to_user_with_default = dt.str_to_user_with_default?.bind(dt);
  const orig_user_to_str = dt.user_to_str?.bind(dt);
  const orig_format_date = dt.format_date?.bind(dt);
  const orig_format_datetime = dt.format_datetime?.bind(dt);

  if (orig_str_to_user) {
    dt.str_to_user = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_str_to_user(value);
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
        return orig_str_to_user_with_default(value);
      }
      return dt.str_to_user(value);
    };
  }
  if (orig_user_to_str) {
    dt.user_to_str = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_user_to_str(value);
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
        return orig_format_date(date_str);
      }
      return g2j_str(date_str);
    };
  }
  if (orig_format_datetime) {
    dt.format_datetime = function (value) {
      if (!value) return value;
      if (!shouldConvertToJalali()) {
        return orig_format_datetime(value);
      }
      return g2j_str(value);
    };
  }

  const orig_date_formatter = frappe.form.formatters.date;
  const orig_datetime_formatter = frappe.form.formatters.datetime;

  frappe.form.formatters.date = function (value, df, options, doc) {
    if (!value) return value;
    if (!shouldConvertToJalali()) {
      if (orig_date_formatter) {
        return orig_date_formatter(value, df, options, doc);
      }
      return value;
    }
    return g2j_str(value, "Date");
  };

  frappe.form.formatters.datetime = function (value, df, options, doc) {
    if (!value) return value;
    if (!shouldConvertToJalali()) {
      if (orig_datetime_formatter) {
        return orig_datetime_formatter(value, df, options, doc);
      }
      return value;
    }
    return g2j_str(value, "Datetime");
  };
})();
